from __future__ import annotations

import csv
import json
import os
from datetime import datetime

from .models import Article
from .utils import logger


def export_json(
    articles: list[Article],
    journal_name: str,
    pykm: str,
    year: str,
    output_dir: str = "output",
) -> str:
    """导出单个期刊某年的论文为 JSON 文件。返回文件路径。"""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{pykm}_{year}.json"
    filepath = os.path.join(output_dir, filename)

    data = {
        "journal": journal_name,
        "pykm": pykm,
        "year": year,
        "crawl_time": datetime.now().isoformat(),
        "total_articles": len(articles),
        "articles": [a.to_dict() for a in articles],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("已导出 JSON: %s (%d 篇)", filepath, len(articles))
    return filepath


def export_csv(
    all_articles: list[Article],
    output_dir: str = "output",
    filename: str = "all_articles.csv",
) -> str:
    """导出所有论文为 CSV 文件。返回文件路径。"""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    fieldnames = [
        "journal", "year", "issue", "title", "authors", "institutions",
        "abstract", "keywords", "funds", "clc_code", "url",
    ]

    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for a in all_articles:
            row = a.to_dict()
            # 列表字段用分号连接
            for key in ("authors", "institutions", "keywords", "funds"):
                if isinstance(row[key], list):
                    row[key] = ";".join(row[key])
            writer.writerow(row)

    logger.info("已导出 CSV: %s (%d 篇)", filepath, len(all_articles))
    return filepath


def save_failed_items(failed: list[dict], filepath: str = "failed_items.json") -> None:
    """保存爬取失败的条目。"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)
    logger.info("已保存 %d 个失败条目到 %s", len(failed), filepath)


def load_failed_items(filepath: str = "failed_items.json") -> list[dict]:
    """加载之前失败的条目。"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
