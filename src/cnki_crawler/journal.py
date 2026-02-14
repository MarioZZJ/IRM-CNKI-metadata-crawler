from __future__ import annotations

import math
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .browser import CnkiBrowser
from .utils import logger, random_delay

BASE_NAVI = "https://navi.cnki.net"


def get_all_year_issues(
    browser: CnkiBrowser,
    pykm: str,
    time_token: str,
    target_years: set[str],
) -> list[dict]:
    """获取指定年份的所有刊期信息。

    返回: [{"year": "2024", "issue": "No.06", "issue_id": "yq202406", "value": "加密值"}, ...]
    """
    # 先获取第一页，得到总年份数
    html = _fetch_year_list(browser, pykm, time_token, page_idx=0)
    soup = BeautifulSoup(html, "lxml")

    total_cnt_el = soup.find("input", id="totalCnt")
    total_cnt = int(total_cnt_el["value"]) if total_cnt_el else 20
    total_pages = math.ceil(total_cnt / 20)
    logger.info("期刊 %s 共 %d 个年份, %d 页", pykm, total_cnt, total_pages)

    results = _parse_year_issues(soup, target_years)

    for page_idx in range(1, total_pages):
        found_years = {r["year"] for r in results}
        if target_years and target_years.issubset(found_years):
            logger.info("已找到所有目标年份，跳过剩余页")
            break
        random_delay(1.0, 2.0)
        html = _fetch_year_list(browser, pykm, time_token, page_idx=page_idx)
        soup = BeautifulSoup(html, "lxml")
        results.extend(_parse_year_issues(soup, target_years))

    logger.info("期刊 %s 目标年份共 %d 个刊期", pykm, len(results))
    return results


def _fetch_year_list(browser: CnkiBrowser, pykm: str, time_token: str, page_idx: int) -> str:
    """通过浏览器 AJAX 调用 yearList API。"""
    url = f"{BASE_NAVI}/knavi/journals/{pykm}/yearList"
    data = {
        "pIdx": str(page_idx),
        "time": time_token,
        "isEpublish": "0",
        "pcode": "CJFD,CCJD",
    }
    return browser.post_ajax(url, data)


def _parse_year_issues(soup: BeautifulSoup, target_years: set[str]) -> list[dict]:
    """从 yearList 响应 HTML 中解析刊期信息。"""
    results = []
    for dl in soup.find_all("dl"):
        dl_id = dl.get("id", "")
        match = re.match(r"(\d{4})_Year_Issue", dl_id)
        if not match:
            continue
        year = match.group(1)
        if target_years and year not in target_years:
            continue

        for a in dl.find_all("a"):
            issue_id = a.get("id", "")
            value = a.get("value", "")
            issue_text = a.get_text(strip=True)
            if value:
                results.append({
                    "year": year,
                    "issue": issue_text,
                    "issue_id": issue_id,
                    "value": value,
                })
    return results


def get_papers_list(
    browser: CnkiBrowser, pykm: str, year_issue_value: str
) -> list[dict]:
    """获取某一刊期的所有论文基础信息。

    返回: [{"title": "...", "url": "...", "authors_preview": "...", "pages": "...", "column": "..."}, ...]
    """
    html = _fetch_papers(browser, pykm, year_issue_value, page_idx=0)
    return _parse_papers_html(html)


def _fetch_papers(browser: CnkiBrowser, pykm: str, year_issue_value: str, page_idx: int) -> str:
    """通过浏览器 AJAX 调用 papers API。"""
    encoded_value = quote(year_issue_value, safe="")
    url = (
        f"{BASE_NAVI}/knavi/journals/{pykm}/papers"
        f"?yearIssue={encoded_value}&pageIdx={page_idx}"
        f"&pcode=CJFD,CCJD&isEpublish=0"
    )
    return browser.get_ajax(url)


def _parse_papers_html(html: str) -> list[dict]:
    """从 papers 响应 HTML 中解析论文列表。"""
    soup = BeautifulSoup(html, "lxml")
    results = []
    current_column = ""

    for element in soup.find_all(["dt", "dd"]):
        if element.name == "dt" and "tit" in element.get("class", []):
            current_column = element.get_text(strip=True)
            for prefix in ("专栏:", "专栏：", "栏目:", "栏目："):
                if current_column.startswith(prefix):
                    current_column = current_column[len(prefix):]
                    break
            continue

        if element.name == "dd" and "row" in element.get("class", []):
            name_span = element.find("span", class_="name")
            if not name_span:
                continue
            a_tag = name_span.find("a")
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            url = a_tag.get("href", "")

            author_span = element.find("span", class_="author")
            authors_preview = author_span.get("title", "") if author_span else ""

            page_span = element.find("span", class_="company")
            pages = page_span.get("title", "") if page_span else ""

            results.append({
                "title": title,
                "url": url,
                "authors_preview": authors_preview,
                "pages": pages,
                "column": current_column,
            })

    return results
