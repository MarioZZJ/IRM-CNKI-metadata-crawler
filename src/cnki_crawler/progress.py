from __future__ import annotations

import json
import os
import tempfile

from .utils import logger

PROGRESS_FILE = "crawl_progress.json"


class CrawlProgress:
    """分层进度管理：期刊 -> 刊期 -> 论文。

    结构:
    {
      "target_years": ["2025"],
      "journals": {
        "DXTS": {
          "name": "大学图书馆学报",
          "completed_issues": ["2025_No.01", "2025_No.02"],
          "articles": [{ "title": "...", "detail_crawled": true, ... }]
        }
      }
    }
    """

    def __init__(self, filepath: str = PROGRESS_FILE):
        self._filepath = filepath
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self._filepath):
            return {"target_years": [], "journals": {}}
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("进度文件损坏，重新开始")
            return {"target_years": [], "journals": {}}

    def save(self) -> None:
        """原子写入进度文件（写临时文件 -> rename）。"""
        dir_name = os.path.dirname(self._filepath) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._filepath)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def set_target_years(self, years: set[str]) -> None:
        self._data["target_years"] = sorted(years)

    def ensure_journal(self, pykm: str, name: str) -> None:
        """确保期刊条目存在。"""
        if pykm not in self._data["journals"]:
            self._data["journals"][pykm] = {
                "name": name,
                "completed_issues": [],
                "articles": [],
            }

    def is_issue_completed(self, pykm: str, issue_key: str) -> bool:
        """检查刊期是否已完成。issue_key 格式: '2025_No.01'"""
        journal = self._data["journals"].get(pykm, {})
        return issue_key in journal.get("completed_issues", [])

    def mark_issue_completed(self, pykm: str, issue_key: str) -> None:
        """标记刊期已完成。"""
        journal = self._data["journals"].get(pykm, {})
        completed = journal.get("completed_issues", [])
        if issue_key not in completed:
            completed.append(issue_key)
        self.save()
        logger.info("刊期 %s 已标记完成", issue_key)

    def is_article_crawled(self, pykm: str, url: str) -> bool:
        """检查论文是否已爬取。"""
        journal = self._data["journals"].get(pykm, {})
        for art in journal.get("articles", []):
            if art.get("url") == url and art.get("detail_crawled"):
                return True
        return False

    def add_article(self, pykm: str, article_data: dict) -> None:
        """添加或更新论文记录，立即保存。"""
        journal = self._data["journals"].get(pykm)
        if not journal:
            return

        articles = journal["articles"]
        url = article_data.get("url", "")

        # 查找是否已存在
        for i, art in enumerate(articles):
            if art.get("url") == url:
                articles[i] = article_data
                self.save()
                return

        articles.append(article_data)
        self.save()

    def get_articles(self, pykm: str) -> list[dict]:
        """获取期刊的所有论文记录。"""
        journal = self._data["journals"].get(pykm, {})
        return journal.get("articles", [])

    def get_all_articles(self) -> list[dict]:
        """获取所有期刊的所有论文记录。"""
        articles = []
        for journal_data in self._data["journals"].values():
            articles.extend(journal_data.get("articles", []))
        return articles

    def get_stats(self) -> dict:
        """获取统计信息。"""
        total = 0
        crawled = 0
        for journal_data in self._data["journals"].values():
            for art in journal_data.get("articles", []):
                total += 1
                if art.get("detail_crawled"):
                    crawled += 1
        return {"total": total, "crawled": crawled, "remaining": total - crawled}
