# CNKI 期刊论文元信息爬虫

## 项目概述
批量爬取 CNKI（中国知网）指定期刊、指定年份的论文元信息。

## 需求
- **输入**: journals.csv（期刊名+详情页URL）、命令行指定年份（单年或范围）
- **输出**: JSON + CSV 双格式，保存到 output/ 目录
- **爬取字段**: 标题、作者姓名、单位列表、摘要、关键词序列、基金序列、分类号
- **不含网络首发**（isEpublish=0）

## 技术栈
- Python 3.11+，uv 管理虚拟环境
- DrissionPage（浏览器自动化，基于 CDP 协议直连系统 Chrome）
- BeautifulSoup4 + lxml（HTML 解析）
- 命令行参数: argparse

### 为什么选 DrissionPage 而非 Playwright
| 对比 | Playwright | DrissionPage |
|------|-----------|-------------|
| `navigator.webdriver` | 默认 `true`（暴露自动化） | 不设置（无自动化痕迹） |
| 驱动机制 | 自有协议 + WebDriver | 直接 CDP websocket |
| 代理处理 | 需手动配置，env 变量干扰 | 直接继承系统 Chrome 设置 |
| 接管模式 | 需 `--remote-debugging-port` | 原生支持接管已运行的浏览器 |
| 验证码渲染 | 腾讯验证码检测自动化后拒绝渲染 | 正常渲染 |

**实测结论**：Playwright 启动的 Chrome 被腾讯验证码检测为自动化浏览器，拼图/滑块不渲染，导致无法通过验证。DrissionPage 通过 CDP 直连系统 Chrome，无自动化标记，验证码正常工作。

## 架构设计

### 单阶段执行
爬取在**单阶段**内完成：获取论文列表后**立即**爬取详情页，确保 URL 中的 `v` 参数在有效期内。

流程：
```
for 每个期刊:
    导航到期刊详情页 → 获取 time_token + pykm
    for 每个目标刊期:
        跳过已完成刊期
        AJAX 获取论文列表（含新鲜 v 参数的 URL）
        for 每篇论文:
            跳过已爬取的论文
            random_delay(3-6秒)
            导航到详情页（v 参数有效）→ 获取 HTML
            检测验证码 → 暂停让用户在浏览器窗口中手动解决
            parse_article_detail(html)  # 复用现有解析
            保存进度
        标记刊期完成
    导出 JSON + CSV
```

### 模块结构
```
src/cnki_crawler/
├── __init__.py
├── __main__.py      # python -m 入口
├── main.py          # CLI 入口，单阶段流程
├── browser.py       # DrissionPage 浏览器管理：启动/导航/验证码检测/AJAX
├── progress.py      # 分层进度管理（期刊→刊期→论文）
├── journal.py       # 期刊级操作：yearList、papers 列表解析
├── article.py       # 论文详情页解析
├── models.py        # 数据模型定义
├── exporter.py      # JSON/CSV 导出
└── utils.py         # 工具函数（延迟、日志）
```

### 关键策略
- **请求间隔**: 3-6 秒随机延迟
- **验证码处理**: 检测 URL 中 `/verify/` 或 `captchaType`，暂停等待用户在浏览器窗口中手动解决
- **Cookie 管理**: DrissionPage 使用系统 Chrome 用户数据目录，Cookie 自动持久化
- **断点续爬**: crawl_progress.json 按刊期为单位标记完成，每篇论文爬取后立即保存（原子写入）
- **资源屏蔽**: 通过 `tab.set.blocked_urls()` 屏蔽字体/媒体等非必要资源
- **进度显示**: 实时显示当前进度
- **浏览器存活检测**: 检测浏览器是否被用户关闭，及时终止避免无效重试

### 核心模块设计

#### browser.py — CnkiBrowser 类
```python
class CnkiBrowser:
    def __init__(self, headless=False, port=None):
        # 使用 DrissionPage 的 ChromiumOptions
        # port 指定时接管已运行的浏览器，否则启动新实例
        # 使用系统 Chrome，TLS/Cookie/指纹完全真实

    def navigate(self, url) -> str:  # 导航 + 验证码检测，返回 HTML
    def post_ajax(self, url, data) -> str:  # 在浏览器内 run_js(fetch())
    def get_ajax(self, url) -> str:  # GET 风格的 AJAX
    def get_article_html(self, url) -> (str, bool):  # 获取论文详情页，自动处理验证码
    def is_alive -> bool:  # 检测浏览器是否仍然可用
    def _is_captcha(self) -> bool:  # 检测验证码
    def _handle_captcha(self):  # 暂停等待用户手动解决
```

关键设计：
- **DrissionPage Chromium**：通过 CDP 直连系统 Chrome，无 `navigator.webdriver` 标记
- **接管模式**（`--port`）：连接用户已打开的 Chrome，继承代理/Cookie/登录状态
- **自启动模式**（默认）：自动启动新 Chrome 实例，使用 `auto_port()` 避免端口冲突
- **反自动化检测**：`--disable-blink-features=AutomationControlled`
- **post_ajax 用 tab.run_js(fetch(...))**：在浏览器 JS 上下文中执行 AJAX，继承所有 cookie 和指纹
- **资源屏蔽**：`tab.set.blocked_urls(['*.woff', '*.woff2', '*.mp4'])`

#### progress.py — 分层进度管理
```json
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
```

- 按**刊期**为单位标记完成（非逐篇论文）
- 每篇论文爬取后立即保存（非每 20 篇）
- 原子写入（写临时文件 → rename）

### 反爬分析与发现

#### v 参数时效性（关键发现）
- 论文详情页 URL 中的 `v` 参数是加密编码，**具有有效期**
- 同一篇论文在不同时间访问，v 参数值完全不同
- 过期的 v 参数 → 服务器强制 302 重定向到验证码页面
- 这是导致旧版两阶段架构失败的**根本原因**：Phase1 收集 URL → Phase2 爬取详情，时间差导致所有 URL 失效

#### CNKI 反爬层级
1. **TLS 指纹检测**：CNKI 检测 TLS 握手指纹（JA3/JA4），Python HTTP 客户端（requests、curl_cffi）即使模拟 Chrome 指纹仍被识别
2. **HTTP 头指纹**：sec-ch-ua、sec-fetch-*、Accept 等头部需与真实浏览器完全一致
3. **Cookie/会话验证**：缺少关键 Cookie（如 `cnkiUserKey`、`SID_kns_new`）会被识别为爬虫
4. **v 参数时效**：URL 中的 v 参数过期后强制触发验证码
5. **自动化检测**：`navigator.webdriver` 等标记导致腾讯验证码拒绝渲染

#### 技术选型演进
1. **v1 requests/curl_cffi**：即使补全 UA、sec-ch-ua、sec-fetch-* 头和 TLS 指纹，仍被 kns.cnki.net 拦截
2. **v2 Playwright**：TLS 指纹真实，但 `navigator.webdriver=true` 导致腾讯验证码拼图不渲染，用户无法手动解决验证码
3. **v3 DrissionPage**：CDP 直连系统 Chrome，无自动化标记，验证码正常渲染，代理设置继承系统配置

## 命令行用法
```bash
# 标准用法（自动启动 Chrome，可手动解决验证码）
uv run python -m cnki_crawler --year 2025

# 指定期刊
uv run python -m cnki_crawler --year 2025 --journal "大学图书馆学报"

# 指定年份范围
uv run python -m cnki_crawler --year 2020-2025

# 接管已运行的 Chrome（继承代理/Cookie 设置）
uv run python -m cnki_crawler --year 2025 --port 9222

# 仅导出（不爬取）
uv run python -m cnki_crawler --export-only

# 无头模式（适合无 GUI 环境）
uv run python -m cnki_crawler --year 2025 --headless

# 显示详细日志
uv run python -m cnki_crawler --year 2025 -v
```

## 输出格式

### JSON (output/{pykm}_{year}.json)
```json
{
  "journal": "中国图书馆学报",
  "pykm": "ZGTS",
  "year": "2024",
  "crawl_time": "2025-01-01T00:00:00",
  "total_articles": 53,
  "articles": [...]
}
```

### CSV (output/all_articles.csv)
所有期刊论文汇总，一行一篇论文，列表字段用分号分隔。UTF-8 BOM 编码，Excel 可直接打开。

## 实现文件清单

### v3 变更（DrissionPage 重写）

#### 重写文件
| 文件 | 变更 |
|------|------|
| `src/cnki_crawler/browser.py` | **重写**：Playwright → DrissionPage，CDP 直连系统 Chrome |
| `src/cnki_crawler/main.py` | **修改**：适配 DrissionPage API（`--cdp` → `--port`） |
| `src/cnki_crawler/journal.py` | **小改**：`browser.post_ajax()` / `browser.get_ajax()` 接口不变 |
| `pyproject.toml` | 依赖：+DrissionPage，-playwright |

#### 不变文件（100% 复用）
| 文件 | 原因 |
|------|------|
| `progress.py` | 进度管理逻辑与浏览器实现无关 |
| `article.py` | 所有解析函数基于 HTML 字符串 + BeautifulSoup，与传输层无关 |
| `models.py` | 数据模型不变 |
| `exporter.py` | 导出逻辑不变 |
| `utils.py` | 工具函数不变 |

### 删除文件
| 文件 | 原因 |
|------|------|
| `src/cnki_crawler/session.py` | 早已被 browser.py 替代 |

## 状态
- [x] 需求分析
- [x] 项目初始化（uv、git）
- [x] v1 编码实现（两阶段 + requests/curl_cffi）
- [x] v1 阶段1 测试通过（URL收集正常）
- [x] 反爬分析：发现 v 参数时效性问题，确认两阶段架构不可行
- [x] v2 架构设计：单阶段 + Playwright
- [x] v2 编码实现
- [x] v2 测试：发现 Playwright 自动化标记导致验证码不渲染
- [x] v3 架构设计：单阶段 + DrissionPage
- [x] v3 编码实现
- [x] v3 测试验证（2026-02-14：信息资源管理学报 2025 全年 6 期，共 73 篇）

## v3 测试记录（2026-02-14）
- 测试对象：`信息资源管理学报`，年份 `2025`
- 测试命令：`PYTHONPATH=src .venv/bin/python -m cnki_crawler --year 2025 --journal "信息资源管理学报" --output-dir output/test_irm_2025_headful -v`
- 结果：成功抓取 `No.01`~`No.06` 共 `73` 篇论文
- 输出文件：
  - `output/test_irm_2025_headful/XNZY_2025.json`
  - `output/test_irm_2025_headful/all_articles.csv`
- 迭代修复：
  - 问题：抓完一刊期后停留在详情页域名（`kns.cnki.net`），后续论文列表接口（`navi.cnki.net`）`fetch` 触发跨域失败（`TypeError: Failed to fetch`）
  - 方案：获取论文列表失败时，自动回到期刊详情页重试一次
