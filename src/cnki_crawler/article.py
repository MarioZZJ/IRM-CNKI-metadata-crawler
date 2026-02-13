from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from .models import Article
from .utils import logger


def parse_article_detail(html: str) -> dict:
    """解析论文详情页 HTML，返回元信息字典。

    返回的字段: title, authors, institutions, abstract, keywords, funds, clc_code
    """
    soup = BeautifulSoup(html, "lxml")
    result: dict = {}

    # 标题
    result["title"] = _parse_title(soup)

    # 作者
    result["authors"] = _parse_authors(soup)

    # 单位
    result["institutions"] = _parse_institutions(soup)

    # 摘要
    result["abstract"] = _parse_abstract(soup)

    # 关键词
    result["keywords"] = _parse_keywords(soup)

    # 基金
    result["funds"] = _parse_funds(soup)

    # 分类号
    result["clc_code"] = _parse_clc_code(soup)

    return result


def _parse_title(soup: BeautifulSoup) -> str:
    wx_tit = soup.find("div", class_="wx-tit")
    if not wx_tit:
        return ""
    h1 = wx_tit.find("h1")
    if not h1:
        return ""
    # 移除隐藏的 span 标签（如"附视频"）
    for span in h1.find_all("span", style=re.compile(r"display\s*:\s*none")):
        span.decompose()
    return h1.get_text(strip=True)


def _parse_authors(soup: BeautifulSoup) -> list[str]:
    author_part = soup.find("h3", id="authorpart")
    if not author_part:
        return []
    authors = []
    for a in author_part.find_all("a"):
        # 作者名在 <a> 的直接文本中，<sup> 是单位编号
        name_parts = []
        for child in a.children:
            if isinstance(child, str):
                name_parts.append(child.strip())
            elif isinstance(child, Tag) and child.name == "sup":
                break  # sup 之后不再有姓名
            # 跳过 i (email icon) 等标签
        name = "".join(name_parts).strip()
        if name:
            authors.append(name)
    return authors


def _parse_institutions(soup: BeautifulSoup) -> list[str]:
    wx_tit = soup.find("div", class_="wx-tit")
    if not wx_tit:
        return []
    # 单位在第二个 h3.author（不含 id="authorpart"）
    h3_list = wx_tit.find_all("h3", class_="author")
    for h3 in h3_list:
        if h3.get("id") == "authorpart":
            continue
        institutions = []
        for a in h3.find_all("a"):
            text = a.get_text(strip=True)
            # 去掉开头的编号（如 "1." "2."）
            text = re.sub(r"^\d+\.\s*", "", text)
            if text:
                institutions.append(text)
        if institutions:
            return institutions
    return []


def _parse_abstract(soup: BeautifulSoup) -> str:
    summary = soup.find(id="ChDivSummary")
    if summary:
        return summary.get_text(strip=True)
    return ""


def _parse_keywords(soup: BeautifulSoup) -> list[str]:
    kw_p = soup.find("p", class_="keywords")
    if not kw_p:
        return []
    keywords = []
    for a in kw_p.find_all("a"):
        text = a.get_text(strip=True)
        text = text.rstrip(";；").strip()
        if text:
            keywords.append(text)
    return keywords


def _parse_funds(soup: BeautifulSoup) -> list[str]:
    funds_p = soup.find("p", class_="funds")
    if not funds_p:
        return []
    funds = []
    for a in funds_p.find_all("a"):
        text = a.get_text(strip=True)
        text = text.rstrip(";；").strip()
        if text:
            funds.append(text)
    # 如果没有 <a> 标签，尝试直接获取文本
    if not funds:
        text = funds_p.get_text(strip=True)
        if text:
            funds = [f.strip() for f in re.split(r"[;；]", text) if f.strip()]
    return funds


def _parse_clc_code(soup: BeautifulSoup) -> str:
    clc = soup.find("p", class_="clc-code")
    if clc:
        return clc.get_text(strip=True)
    return ""
