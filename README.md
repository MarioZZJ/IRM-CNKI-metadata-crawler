# CNKI 期刊论文元信息爬虫

批量爬取 [CNKI（中国知网）](https://www.cnki.net/) 指定期刊、指定年份的论文元信息。

## 爬取字段

标题、作者姓名、单位列表、摘要、关键词、基金、分类号

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python 包管理器)
- Google Chrome 浏览器

## 快速开始

### 1. 初始化环境

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

**Linux / macOS:**
```bash
bash setup.sh
```

脚本会自动安装 uv（如未安装）、创建虚拟环境并安装所有依赖。

如果你已安装 uv，也可以手动执行：
```bash
uv sync
uv pip install -e .
```

### 2. 运行爬虫（v3 当前方式）

默认会启动一个可见 Chrome 窗口，遇到验证码时可手动完成后继续。

```bash
# 爬取指定年份
uv run python -m cnki_crawler --year 2025

# 指定期刊
uv run python -m cnki_crawler --year 2025 --journal "大学图书馆学报"

# 指定年份范围
uv run python -m cnki_crawler --year 2020-2025

# 指定输出目录 + 详细日志（推荐排障）
uv run python -m cnki_crawler --year 2025 --journal "信息资源管理学报" --output-dir output/test_run -v
```

#### 接管已打开的 Chrome（推荐）

如果你依赖系统代理、已有登录态，建议接管你已打开的 Chrome：

```bash
# 先关闭所有 Chrome 窗口，再启动调试端口
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# 爬虫接管该 Chrome
uv run python -m cnki_crawler --year 2025 --port 9222
```

#### 更多选项

```bash
# 仅导出已爬取数据（不启动爬虫）
uv run python -m cnki_crawler --export-only

# 无头模式（注意：触发验证码时无法人工处理，可能失败）
uv run python -m cnki_crawler --year 2025 --headless

# 显示详细日志
uv run python -m cnki_crawler --year 2025 -v

# 查看所有参数
uv run python -m cnki_crawler --help
```

### 验证码处理

爬虫运行时会打开一个可见的 Chrome 浏览器窗口。当 CNKI 触发验证码时：
1. 爬虫自动暂停并提示
2. 在浏览器窗口中手动完成验证码
3. 爬虫自动检测验证码通过后继续运行

Cookie 由 Chrome 浏览器自动管理，无需手动导出。

### 请求节奏（默认）

- 论文之间随机等待 `3-6` 秒
- 刊期列表请求前随机等待 `1-2` 秒

## 输出

结果保存在 `output/` 目录：

- **JSON** (`output/{期刊代码}_{年份}.json`) — 按期刊和年份分文件，结构化存储
- **CSV** (`output/all_articles.csv`) — 所有论文汇总，UTF-8 BOM 编码，Excel 可直接打开

## 断点续爬

支持断点续爬，进度保存在 `crawl_progress.json` 中：

- 已完成的刊期自动跳过
- 每篇论文爬取后立即保存进度
- 中途中断（Ctrl+C）后重新运行即可从断点继续

## 期刊列表

待爬取的期刊在 `journals.csv` 中配置（期刊名 + CNKI 详情页 URL）。

## 项目结构

```
├── setup.ps1 / setup.sh    # 环境初始化脚本
├── journals.csv             # 期刊列表
├── crawl_progress.json      # 爬取进度（自动生成，不入库）
├── output/                  # 爬取结果（不入库）
└── src/cnki_crawler/        # 源代码
    ├── main.py              # CLI 入口，单阶段流程
    ├── browser.py           # DrissionPage 浏览器管理
    ├── progress.py          # 分层进度管理
    ├── journal.py           # 期刊/刊期/论文列表
    ├── article.py           # 论文详情页解析
    ├── models.py            # 数据模型
    ├── exporter.py          # JSON/CSV 导出
    └── utils.py             # 工具函数
```
