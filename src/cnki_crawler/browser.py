from __future__ import annotations

import os
import time
from urllib.parse import urlencode

from DrissionPage import Chromium, ChromiumOptions

from .utils import logger

CAPTCHA_URL_INDICATORS = ("/verify/", "captchaType")
CAPTCHA_HTML_INDICATORS = (
    "TJCaptcha.js",
    "拖动下方拼图完成验证",
    "tencentSlide",
    "turing.captcha.qcloud.com",
    "captchaType",
    "clickWord",
    "verify/home",
)
BLOCKED_URLS = ["*.woff", "*.woff2", "*.ttf", "*.otf", "*.mp4", "*.webm", "*.mp3"]


class CnkiBrowser:
    """基于 DrissionPage 的 CNKI 浏览器管理器。"""

    def __init__(self, headless: bool = False, port: int | None = None):
        self._closed = False
        self._port_mode = port is not None
        self._headless = headless and port is None
        self._browser = self._create_browser(headless=headless, port=port)
        self._tab = self._create_tab()
        self._configure_tab()

    def _create_browser(self, headless: bool, port: int | None) -> Chromium:
        opts = ChromiumOptions(read_file=False)
        opts.set_timeouts(base=10, page_load=30, script=30)
        opts.set_argument("--disable-blink-features", "AutomationControlled")

        if port is not None:
            opts.set_local_port(port)
            opts.existing_only(True)
            logger.info("接管模式：连接到已运行 Chrome (127.0.0.1:%s)", port)
            if headless:
                logger.warning("接管模式下忽略 --headless 参数")
        else:
            opts.auto_port()
            proxy = (
                os.environ.get("https_proxy")
                or os.environ.get("HTTPS_PROXY")
                or os.environ.get("all_proxy")
                or os.environ.get("ALL_PROXY")
                or os.environ.get("http_proxy")
                or os.environ.get("HTTP_PROXY")
            )
            if proxy:
                opts.set_proxy(proxy)
                logger.info("自启动模式启用代理: %s", proxy)
            if headless:
                opts.headless(True)
                logger.info("自启动模式：无头运行")
            else:
                logger.info("自启动模式：有头运行")

        return Chromium(opts)

    def _create_tab(self):
        if self._port_mode:
            return self._browser.new_tab()
        try:
            return self._browser.latest_tab
        except Exception:
            return self._browser.new_tab()

    def _configure_tab(self) -> None:
        try:
            self._tab.set.blocked_urls(BLOCKED_URLS)
        except Exception as e:
            logger.debug("设置资源屏蔽失败: %s", e)

    @staticmethod
    def _to_seconds(timeout_ms: int | None) -> float | None:
        if timeout_ms is None:
            return None
        return max(timeout_ms / 1000.0, 0.1)

    def _ensure_alive(self) -> None:
        if not self.is_alive:
            raise RuntimeError("浏览器已关闭")

    def _safe_html(self) -> str:
        try:
            return self._tab.html
        except Exception:
            return ""

    def navigate(self, url: str, timeout: int = 30000) -> str:
        """导航到指定 URL，检测并处理验证码。返回页面 HTML。"""
        self._ensure_alive()
        ok = self._tab.get(url, timeout=self._to_seconds(timeout), show_errmsg=False)
        if ok is False:
            logger.warning("导航返回非成功状态，可能触发风控或重定向: %s", url)
        self._handle_captcha()
        return self._safe_html()

    def post_ajax(self, url: str, data: dict | str) -> str:
        """在浏览器 JS 上下文中执行 fetch POST 请求。"""
        self._ensure_alive()
        body = urlencode(data) if isinstance(data, dict) else data
        script = """
const url = arguments[0];
const body = arguments[1];
return fetch(url, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'language': 'CHS',
        'uniplatform': 'NZKPT',
    },
    body: body,
}).then(resp => resp.text());
"""
        result = self._tab.run_js(script, url, body)
        return result or ""

    def get_ajax(self, url: str) -> str:
        """在浏览器 JS 上下文中执行 AJAX（接口要求 POST 空 body）。"""
        self._ensure_alive()
        script = """
const url = arguments[0];
return fetch(url, {
    method: 'POST',
    headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'language': 'CHS',
        'uniplatform': 'NZKPT',
    },
    body: '',
}).then(resp => resp.text());
"""
        result = self._tab.run_js(script, url)
        return result or ""

    @property
    def is_alive(self) -> bool:
        """检查浏览器和页面是否仍然可用。"""
        if self._closed:
            return False
        try:
            return bool(self._browser.states.is_alive and self._tab.states.is_alive)
        except Exception:
            return False

    def get_article_html(self, url: str, timeout: int = 30000) -> tuple[str, bool]:
        """获取论文详情页 HTML。自动处理验证码。返回 (html, is_captcha)。"""
        self._ensure_alive()
        ok = self._tab.get(url, timeout=self._to_seconds(timeout), show_errmsg=False)
        if ok is False:
            logger.warning("详情页返回非成功状态，继续检测验证码: %s", url)
        self._handle_captcha()

        html = self._safe_html()
        if self._is_captcha(html):
            return html, True

        return html, False

    def close(self) -> None:
        """关闭浏览器资源。"""
        if self._closed:
            return
        self._closed = True

        if self._port_mode:
            # 接管模式只关闭当前新建标签页，不关闭用户浏览器
            try:
                self._tab.close()
            except Exception:
                pass
            return

        try:
            self._browser.quit()
        except Exception:
            pass

    def _is_captcha(self, html: str | None = None) -> bool:
        """检测当前页面是否为验证码页面。"""
        try:
            current_url = self._tab.url
        except Exception:
            current_url = ""
        if any(token in current_url for token in CAPTCHA_URL_INDICATORS):
            return True

        content = html if html is not None else self._safe_html()
        return any(indicator in content for indicator in CAPTCHA_HTML_INDICATORS)

    def _handle_captcha(self) -> None:
        """检测验证码并暂停等待用户手动解决。"""
        if not self._is_captcha():
            return

        if self._headless:
            raise RuntimeError("headless 模式触发验证码，无法手动完成，请改用有头模式或 --port 接管浏览器")

        logger.warning("=" * 50)
        logger.warning("检测到验证码！请在浏览器窗口中手动完成验证")
        logger.warning("完成后程序将自动继续...")
        logger.warning("=" * 50)

        while True:
            time.sleep(2)
            self._ensure_alive()
            if self._is_captcha():
                continue
            break

        try:
            self._tab.wait.doc_loaded(timeout=15, raise_err=False)
        except Exception:
            time.sleep(1)

        logger.info("验证码已通过，继续执行")

    def __enter__(self) -> CnkiBrowser:
        return self

    def __exit__(self, *args) -> None:
        self.close()
