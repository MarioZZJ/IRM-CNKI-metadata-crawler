from __future__ import annotations

from http.cookiejar import Cookie

import requests
from bs4 import BeautifulSoup

from .utils import logger, random_ua


class CnkiSession:
    """管理与 CNKI 的 HTTP 会话，维持 Cookie 和 time 令牌。"""

    BASE_NAVI = "https://navi.cnki.net"
    BASE_KNS = "https://kns.cnki.net"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self.time_token: str = ""
        self.referer: str = ""

    def load_cookies_from_string(self, cookie_str: str, domain: str) -> None:
        """从浏览器导出的 cookie 字符串加载 cookie。"""
        for item in cookie_str.split(";"):
            item = item.strip()
            if not item or "=" not in item:
                continue
            name, value = item.split("=", 1)
            c = Cookie(
                version=0, name=name.strip(), value=value.strip(),
                port=None, port_specified=False,
                domain=domain, domain_specified=True, domain_initial_dot=False,
                path="/", path_specified=True,
                secure=True, expires=None, discard=True,
                comment=None, comment_url=None, rest={}, rfc2109=False,
            )
            self.session.cookies.set_cookie(c)
        logger.info("已加载 %s 的浏览器 Cookie", domain)

    def _ajax_headers(self) -> dict[str, str]:
        return {
            "X-Requested-With": "XMLHttpRequest",
            "language": "CHS",
            "uniplatform": "NZKPT",
            "Referer": self.referer,
        }

    def init_session(self, detail_url: str) -> str:
        """访问期刊详情页，获取 time 令牌和 pykm。返回 pykm。"""
        logger.info("初始化会话: %s", detail_url)
        resp = self.session.get(detail_url, timeout=30)
        resp.raise_for_status()
        self.referer = detail_url
        soup = BeautifulSoup(resp.text, "lxml")

        time_input = soup.find("input", id="time")
        if time_input and time_input.get("value"):
            self.time_token = time_input["value"]
            logger.info("获取 time 令牌成功 (长度=%d)", len(self.time_token))
        else:
            logger.warning("未找到 time 令牌")

        pykm_input = soup.find("input", id="pykm")
        pykm = pykm_input["value"] if pykm_input and pykm_input.get("value") else ""
        if pykm:
            logger.info("获取 pykm: %s", pykm)
        return pykm

    def refresh_token(self, detail_url: str) -> None:
        """重新获取 time 令牌（令牌过期时调用）。"""
        logger.info("刷新 time 令牌...")
        self.init_session(detail_url)

    def get_year_list(self, pykm: str, page_idx: int = 0) -> str:
        """调用 yearList API，返回 HTML 响应文本。"""
        url = f"{self.BASE_NAVI}/knavi/journals/{pykm}/yearList"
        data = {
            "pIdx": str(page_idx),
            "time": self.time_token,
            "isEpublish": "0",
            "pcode": "CJFD,CCJD",
        }
        headers = self._ajax_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = self.session.post(url, data=data, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text

    def get_papers(self, pykm: str, year_issue_value: str, page_idx: int = 0) -> str:
        """调用 papers API，返回 HTML 响应文本。"""
        url = (
            f"{self.BASE_NAVI}/knavi/journals/{pykm}/papers"
            f"?yearIssue={year_issue_value}&pageIdx={page_idx}"
            f"&pcode=CJFD,CCJD&isEpublish=0"
        )
        headers = self._ajax_headers()
        resp = self.session.post(url, data="", headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text

    def get_article_page(self, article_url: str) -> tuple[str, bool]:
        """获取论文详情页 HTML。返回 (html, is_captcha)。"""
        resp = self.session.get(article_url, timeout=30)
        resp.raise_for_status()
        # 检测是否被重定向到验证码页面
        is_captcha = "/verify/" in resp.url or "captchaType" in resp.url
        return resp.text, is_captcha
