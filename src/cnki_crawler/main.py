from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from .article import parse_article_detail
from .browser import CnkiBrowser
from .exporter import export_csv, export_json
from .journal import get_all_year_issues, get_papers_list
from .models import Article, JournalInfo
from .progress import CrawlProgress
from .utils import logger, random_delay, setup_logging

SIGNED_DETAIL_FLAG = "/knavi/detail?p="
FALLBACK_DETAIL_TEMPLATE = "https://navi.cnki.net/knavi/journals/{pykm}/detail?uniplatform=NZKPT&language=CHS"


def parse_years(year_str: str) -> set[str]:
    """解析年份参数。支持 '2024'、'2020-2025' 格式。"""
    if "-" in year_str:
        parts = year_str.split("-")
        start, end = int(parts[0]), int(parts[1])
        return {str(y) for y in range(start, end + 1)}
    return {year_str}


def load_journals(csv_path: str) -> list[JournalInfo]:
    """从 CSV 文件加载期刊列表。"""
    pykm_fallback = _load_pykm_fallback()
    journals = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["source"].strip()
            url = row["url"].strip()
            pykm = ""
            if SIGNED_DETAIL_FLAG in url:
                pykm = pykm_fallback.get(name, "")
                if pykm:
                    url = FALLBACK_DETAIL_TEMPLATE.format(pykm=pykm)
                    logger.debug("期刊 %s 使用稳定详情页 URL 回退", name)
            journals.append(JournalInfo(
                name=name,
                url=url,
                pykm=pykm,
            ))
    return journals


def _load_pykm_fallback(cache_path: str = "paper_urls.json") -> dict[str, str]:
    """从历史 paper_urls.json 提取 journal -> pykm 映射，用于失效详情页回退。"""
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    mapping: dict[str, str] = {}
    for item in data:
        journal = item.get("journal", "").strip()
        pykm = item.get("pykm", "").strip()
        if journal and pykm and journal not in mapping:
            mapping[journal] = pykm
    return mapping


# ── 单阶段爬取 ──────────────────────────────────────────────


def crawl(
    journals: list[JournalInfo],
    target_years: set[str],
    headless: bool = False,
    output_dir: str = "output",
    port: int | None = None,
) -> None:
    """单阶段爬取：获取论文列表后立即爬取详情页。"""
    progress = CrawlProgress()
    progress.set_target_years(target_years)

    with CnkiBrowser(headless=headless, port=port) as browser:
        for journal in journals:
            _crawl_journal(browser, journal, target_years, progress)

    # 导出结果
    _export_results(progress, output_dir)


def _crawl_journal(
    browser: CnkiBrowser,
    journal: JournalInfo,
    target_years: set[str],
    progress: CrawlProgress,
) -> None:
    """爬取单个期刊的所有目标刊期。"""
    logger.info("=" * 60)
    logger.info("期刊: %s", journal.name)

    # 导航到期刊详情页，获取 time_token + pykm
    try:
        html = browser.navigate(journal.url)
    except Exception as e:
        logger.error("访问期刊详情页失败: %s", e)
        return

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    time_input = soup.find("input", id="time")
    time_token = time_input["value"] if time_input and time_input.get("value") else ""
    if not time_token:
        logger.warning("未找到 time 令牌")

    pykm_input = soup.find("input", id="pykm")
    pykm = pykm_input["value"] if pykm_input and pykm_input.get("value") else ""
    if not pykm:
        logger.error("无法获取 pykm，跳过期刊 %s", journal.name)
        return

    journal.pykm = pykm
    logger.info("pykm=%s, time_token长度=%d", pykm, len(time_token))

    progress.ensure_journal(pykm, journal.name)

    # 获取目标年份的刊期列表
    try:
        year_issues = get_all_year_issues(browser, pykm, time_token, target_years)
    except Exception as e:
        logger.error("获取年份列表失败: %s", e)
        return

    # 遍历每个刊期
    for yi in year_issues:
        year, issue, value = yi["year"], yi["issue"], yi["value"]
        issue_key = f"{year}_{issue}"

        if not browser.is_alive:
            logger.error("浏览器已关闭，终止爬取")
            return

        if progress.is_issue_completed(pykm, issue_key):
            logger.info("  跳过已完成: %s", issue_key)
            continue

        logger.info("  获取 %s 论文列表...", issue_key)
        try:
            random_delay(1.0, 2.0)
            papers = _get_papers_with_retry(browser, journal.url, pykm, value)
        except Exception as e:
            logger.error("  获取论文列表失败: %s", e)
            if not browser.is_alive:
                logger.error("浏览器已关闭，终止爬取")
                return
            continue

        logger.info("  该期共 %d 篇论文", len(papers))

        # 立即逐篇爬取详情
        all_success = True
        for idx, paper in enumerate(papers):
            url = paper["url"]
            title = paper["title"]

            if not url:
                continue

            if not browser.is_alive:
                logger.error("浏览器已关闭，终止爬取")
                return

            if progress.is_article_crawled(pykm, url):
                logger.debug("  跳过已爬取: %s", title[:40])
                continue

            logger.info("  [%d/%d] %s", idx + 1, len(papers), title[:50])
            random_delay(3.0, 6.0)

            try:
                html, is_captcha = browser.get_article_html(url)

                if is_captcha:
                    logger.error("  验证码未能解决，跳过此论文")
                    all_success = False
                    continue

                detail = parse_article_detail(html)

                article_data = {
                    "journal": journal.name,
                    "pykm": pykm,
                    "year": year,
                    "issue": issue,
                    "title": detail.get("title") or title,
                    "url": url,
                    "authors": detail.get("authors", []),
                    "institutions": detail.get("institutions", []),
                    "abstract": detail.get("abstract", ""),
                    "keywords": detail.get("keywords", []),
                    "funds": detail.get("funds", []),
                    "clc_code": detail.get("clc_code", ""),
                    "column": paper.get("column", ""),
                    "detail_crawled": True,
                }
                progress.add_article(pykm, article_data)

            except Exception as e:
                logger.error("  爬取失败: %s", e)
                all_success = False
                if not browser.is_alive:
                    logger.error("浏览器已关闭，终止爬取")
                    return
                # 记录失败但不阻塞后续
                progress.add_article(pykm, {
                    "journal": journal.name,
                    "pykm": pykm,
                    "year": year,
                    "issue": issue,
                    "title": title,
                    "url": url,
                    "detail_crawled": False,
                    "crawl_error": str(e),
                })

        if all_success:
            progress.mark_issue_completed(pykm, issue_key)


def _get_papers_with_retry(
    browser: CnkiBrowser,
    journal_url: str,
    pykm: str,
    year_issue_value: str,
) -> list[dict]:
    """获取论文列表，必要时重回期刊页重试一次。

    详情页在 kns 域名，论文列表接口在 navi 域名。若当前页面已切到详情页，
    run_js(fetch) 可能触发跨域失败，因此重回期刊页后再试。
    """
    try:
        return get_papers_list(browser, pykm, year_issue_value)
    except Exception as err:
        if "Failed to fetch" not in str(err):
            raise
        logger.warning("  论文列表请求跨域失败，回到期刊页后重试一次")
        browser.navigate(journal_url)
        random_delay(0.8, 1.5)
        return get_papers_list(browser, pykm, year_issue_value)


def _export_results(progress: CrawlProgress, output_dir: str) -> None:
    """将已爬取的论文导出为 JSON 和 CSV。"""
    all_data = progress.get_all_articles()
    crawled = [p for p in all_data if p.get("detail_crawled")]
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

    pykm_map = {p["journal"]: p.get("pykm", "") for p in all_data}

    for jy_key, arts in journal_year_groups.items():
        j_name = arts[0].journal
        y = arts[0].year
        pykm = pykm_map.get(j_name, "UNKNOWN")
        export_json(arts, j_name, pykm, y, output_dir)

    # 导出汇总 CSV
    export_csv(articles, output_dir)

    stats = progress.get_stats()
    logger.info("导出完成: %d 篇已爬取, %d 篇剩余", stats["crawled"], stats["remaining"])


# ── CLI 入口 ────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CNKI 期刊论文元信息爬虫（单阶段执行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 标准用法（浏览器窗口可见，可手动解决验证码）
  uv run python -m cnki_crawler --year 2025

  # 指定期刊
  uv run python -m cnki_crawler --year 2025 --journal "大学图书馆学报"

  # 指定年份范围
  uv run python -m cnki_crawler --year 2020-2025

  # 接管已运行的 Chrome
  uv run python -m cnki_crawler --year 2025 --port 9222

  # 仅导出（不爬取）
  uv run python -m cnki_crawler --export-only

  # 无头模式
  uv run python -m cnki_crawler --year 2025 --headless

  # 显示详细日志
  uv run python -m cnki_crawler --year 2025 -v
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
        "--port", type=int, default=None,
        help="接管已运行 Chrome 的调试端口（如 9222）",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="无头模式（无浏览器窗口）",
    )
    parser.add_argument(
        "--export-only", action="store_true",
        help="仅导出已有进度，不执行爬取",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="显示详细日志",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.export_only:
        progress = CrawlProgress()
        _export_results(progress, args.output_dir)
        return

    if not args.year:
        parser.error("请指定 --year 参数（如 --year 2025 或 --year 2020-2025）")

    journals = load_journals(args.journals_csv)
    logger.info("已加载 %d 个期刊", len(journals))

    if args.journal:
        journals = [j for j in journals if args.journal in j.name]
        if not journals:
            logger.error("未找到匹配的期刊: %s", args.journal)
            sys.exit(1)
        logger.info("已过滤为 %d 个期刊", len(journals))

    target_years = parse_years(args.year)
    logger.info("目标年份: %s", sorted(target_years))

    crawl(journals, target_years, headless=args.headless, output_dir=args.output_dir, port=args.port)


if __name__ == "__main__":
    main()
