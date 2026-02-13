from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime

from .article import parse_article_detail
from .exporter import export_csv, export_json
from .journal import get_all_year_issues, get_papers_list
from .models import Article, JournalInfo
from .session import CnkiSession
from .utils import logger, random_delay, setup_logging

URLS_FILE = "paper_urls.json"


def parse_years(year_str: str) -> set[str]:
    """解析年份参数。支持 '2024'、'2020-2025' 格式。"""
    if "-" in year_str:
        parts = year_str.split("-")
        start, end = int(parts[0]), int(parts[1])
        return {str(y) for y in range(start, end + 1)}
    return {year_str}


def load_journals(csv_path: str) -> list[JournalInfo]:
    """从 CSV 文件加载期刊列表。"""
    journals = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            journals.append(JournalInfo(
                name=row["source"].strip(),
                url=row["url"].strip(),
            ))
    return journals


# ── 第一阶段：收集论文 URL 列表 ──────────────────────────────


def phase1_collect_urls(
    journals: list[JournalInfo],
    target_years: set[str],
    output_file: str = URLS_FILE,
) -> None:
    """第一阶段：遍历期刊刊期，收集所有论文的 URL 列表。"""
    cnki = CnkiSession()

    # 初始化会话
    first_url = journals[0].url
    journals[0].pykm = cnki.init_session(first_url)

    all_papers: list[dict] = []

    # 如果已有中间文件，加载已完成的期刊
    existing = _load_urls_file(output_file)
    done_keys = {(p["journal"], p["year"], p["issue"]) for p in existing}
    if existing:
        logger.info("已有中间文件，包含 %d 条记录，将跳过已完成的刊期", len(existing))
        all_papers.extend(existing)

    for journal in journals:
        if not journal.pykm:
            random_delay()
            journal.pykm = cnki.init_session(journal.url)
            if not journal.pykm:
                logger.error("无法获取期刊 %s 的 pykm，跳过", journal.name)
                continue

        pykm = journal.pykm
        logger.info("=" * 60)
        logger.info("[阶段1] 期刊: %s (pykm=%s)", journal.name, pykm)

        try:
            random_delay()
            year_issues = get_all_year_issues(cnki, pykm, target_years)
        except Exception as e:
            logger.error("获取年份列表失败: %s", e)
            continue

        for yi in year_issues:
            year, issue, value = yi["year"], yi["issue"], yi["value"]

            # 跳过已完成的刊期
            if (journal.name, year, issue) in done_keys:
                logger.info("  跳过已完成: %s %s", year, issue)
                continue

            logger.info("  获取 %s 年 %s 期论文列表", year, issue)
            try:
                random_delay()
                papers = get_papers_list(cnki, pykm, value)
            except Exception as e:
                logger.error("  获取论文列表失败: %s", e)
                continue

            logger.info("  该期共 %d 篇论文", len(papers))
            for p in papers:
                all_papers.append({
                    "journal": journal.name,
                    "pykm": pykm,
                    "year": year,
                    "issue": issue,
                    "title": p["title"],
                    "url": p["url"],
                    "authors_preview": p.get("authors_preview", ""),
                    "pages": p.get("pages", ""),
                    "column": p.get("column", ""),
                    "detail_crawled": False,
                })

        # 每处理完一个期刊就保存中间结果
        _save_urls_file(all_papers, output_file)

    logger.info("=" * 60)
    logger.info("[阶段1] 完成! 共收集 %d 篇论文 URL", len(all_papers))
    logger.info("结果已保存到 %s", output_file)
    logger.info("请运行 --phase2 开始爬取论文详情")


# ── 第二阶段：爬取论文详情 ──────────────────────────────────


def phase2_crawl_details(
    urls_file: str = URLS_FILE,
    output_dir: str = "output",
) -> None:
    """第二阶段：逐个访问论文详情页，解析元信息。"""
    papers = _load_urls_file(urls_file)
    if not papers:
        logger.error("未找到论文 URL 文件: %s", urls_file)
        logger.error("请先运行 --phase1 收集论文 URL")
        sys.exit(1)

    pending = [p for p in papers if not p.get("detail_crawled")]
    logger.info("[阶段2] 共 %d 篇论文待爬取 (总 %d 篇)", len(pending), len(papers))

    if not pending:
        logger.info("所有论文详情已爬取完毕，直接导出")
        _export_results(papers, output_dir)
        return

    cnki = CnkiSession()
    # 用任意一个期刊URL初始化会话（只需要cookie）
    first_url = pending[0]["url"]
    # 访问 kns.cnki.net 的文章页获取该域名的 cookie
    try:
        cnki.session.get("https://kns.cnki.net/", timeout=30)
    except Exception:
        pass

    captcha_count = 0
    success_count = 0

    for i, paper in enumerate(papers):
        if paper.get("detail_crawled"):
            continue

        title = paper["title"]
        url = paper["url"]
        logger.info("[%d/%d] %s", i + 1, len(papers), title[:50])

        if not url:
            paper["detail_crawled"] = True
            paper["crawl_error"] = "无详情 URL"
            continue

        if captcha_count >= 3:
            logger.warning("连续触发验证码 %d 次，暂停爬取", captcha_count)
            logger.warning("请在浏览器中访问 kns.cnki.net 完成验证码后重新运行 --phase2")
            break

        try:
            random_delay()
            html, is_captcha = cnki.get_article_page(url)

            if is_captcha or _is_captcha_page(html):
                captcha_count += 1
                logger.warning("  检测到验证码 (连续第%d次)", captcha_count)
                continue  # 不标记为已爬取，下次重试

            captcha_count = 0  # 重置连续验证码计数
            detail = parse_article_detail(html)

            if not detail.get("title") and not detail.get("abstract"):
                logger.warning("  详情页解析为空")
                paper["crawl_error"] = "详情页解析为空"
                continue

            # 写入详情信息
            paper["detail_crawled"] = True
            paper["title"] = detail.get("title") or title
            paper["authors"] = detail.get("authors", [])
            paper["institutions"] = detail.get("institutions", [])
            paper["abstract"] = detail.get("abstract", "")
            paper["keywords"] = detail.get("keywords", [])
            paper["funds"] = detail.get("funds", [])
            paper["clc_code"] = detail.get("clc_code", "")
            success_count += 1

        except Exception as e:
            logger.error("  爬取失败: %s", e)
            paper["crawl_error"] = str(e)

        # 每 20 篇保存一次中间结果
        if success_count > 0 and success_count % 20 == 0:
            _save_urls_file(papers, urls_file)
            logger.info("  已保存中间结果 (%d 篇成功)", success_count)

    # 最终保存
    _save_urls_file(papers, urls_file)

    crawled = sum(1 for p in papers if p.get("detail_crawled"))
    remaining = len(papers) - crawled
    logger.info("=" * 60)
    logger.info("[阶段2] 本次成功: %d 篇, 已完成: %d/%d, 剩余: %d",
                success_count, crawled, len(papers), remaining)

    if remaining > 0:
        logger.info("仍有 %d 篇未完成，可重新运行 --phase2 继续", remaining)
    else:
        logger.info("所有论文详情已爬取完毕!")

    # 导出结果
    _export_results(papers, output_dir)


def _export_results(papers: list[dict], output_dir: str) -> None:
    """将已爬取的论文导出为 JSON 和 CSV。"""
    crawled = [p for p in papers if p.get("detail_crawled")]
    if not crawled:
        logger.info("没有已完成的论文可导出")
        return

    articles = []
    for p in crawled:
        articles.append(Article(
            journal=p["journal"],
            year=p["year"],
            issue=p["issue"],
            title=p["title"],
            authors=p.get("authors", []),
            institutions=p.get("institutions", []),
            abstract=p.get("abstract", ""),
            keywords=p.get("keywords", []),
            funds=p.get("funds", []),
            clc_code=p.get("clc_code", ""),
            url=p["url"],
        ))

    # 按期刊+年份分组导出 JSON
    journal_year_groups: dict[str, list[Article]] = {}
    for a in articles:
        jy_key = f"{a.journal}_{a.year}"
        journal_year_groups.setdefault(jy_key, []).append(a)

    pykm_map = {p["journal"]: p.get("pykm", "") for p in papers}

    for jy_key, arts in journal_year_groups.items():
        j_name = arts[0].journal
        y = arts[0].year
        pykm = pykm_map.get(j_name, "UNKNOWN")
        export_json(arts, j_name, pykm, y, output_dir)

    # 导出汇总 CSV
    export_csv(articles, output_dir)


# ── 工具函数 ────────────────────────────────────────────────


def _save_urls_file(papers: list[dict], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)


def _load_urls_file(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_captcha_page(html: str) -> bool:
    """检测页面是否为验证码页面。"""
    captcha_indicators = [
        "TJCaptcha.js",
        "拖动下方拼图完成验证",
        "tencentSlide",
        "turing.captcha.qcloud.com",
        "captchaType",
        "clickWord",
        "verify/home",
    ]
    return any(indicator in html for indicator in captcha_indicators)


# ── CLI 入口 ────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CNKI 期刊论文元信息爬虫（两阶段执行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 阶段1: 收集论文 URL 列表
  uv run python -m cnki_crawler --phase1 --year 2024

  # 阶段2: 爬取论文详情（可多次运行直到完成）
  uv run python -m cnki_crawler --phase2

  # 仅爬取指定期刊
  uv run python -m cnki_crawler --phase1 --year 2024 --journal "中国图书馆学报"

  # 一次性执行两个阶段
  uv run python -m cnki_crawler --year 2024
        """,
    )
    parser.add_argument(
        "--year", type=str, default=None,
        help="目标年份，如 '2024' 或 '2020-2025'",
    )
    parser.add_argument(
        "--journal", type=str, default=None,
        help="仅爬取指定期刊（按名称匹配）",
    )
    parser.add_argument(
        "--journals-csv", type=str, default="journals.csv",
        help="期刊列表 CSV 文件路径 (默认: journals.csv)",
    )
    parser.add_argument(
        "--output-dir", type=str, default="output",
        help="输出目录 (默认: output)",
    )
    parser.add_argument(
        "--phase1", action="store_true",
        help="仅执行阶段1: 收集论文 URL 列表",
    )
    parser.add_argument(
        "--phase2", action="store_true",
        help="仅执行阶段2: 爬取论文详情",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="显示详细日志",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # 确定执行模式
    run_phase1 = args.phase1 or (not args.phase1 and not args.phase2)
    run_phase2 = args.phase2 or (not args.phase1 and not args.phase2)

    if run_phase1:
        if not args.year:
            parser.error("阶段1需要指定 --year")

        journals = load_journals(args.journals_csv)
        logger.info("已加载 %d 个期刊", len(journals))

        if args.journal:
            journals = [j for j in journals if args.journal in j.name]
            if not journals:
                logger.error("未找到匹配的期刊: %s", args.journal)
                sys.exit(1)
            logger.info("已过滤为 %d 个期刊", len(journals))

        target_years = parse_years(args.year)
        phase1_collect_urls(journals, target_years)

    if run_phase2:
        phase2_crawl_details(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
