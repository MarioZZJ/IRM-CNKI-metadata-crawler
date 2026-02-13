# CNKI 期刊论文元信息爬虫

批量爬取 [CNKI（中国知网）](https://www.cnki.net/) 指定期刊、指定年份的论文元信息。

## 爬取字段

标题、作者姓名、单位列表、摘要、关键词、基金、分类号

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python 包管理器)

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

### 2. 准备 Cookie（阶段2 必需）

阶段2 爬取论文详情页时需要浏览器 Cookie 来绕过 CNKI 的验证码：

1. 在 Chrome 浏览器中访问任意一篇 [CNKI 论文详情页](https://kns.cnki.net)（如遇验证码则手动通过）
2. 按 `F12` 打开开发者工具 → Console 标签页
3. 输入 `document.cookie` 并回车
4. 复制输出的字符串，保存到项目根目录的 `cookies.txt` 文件中

> Cookie 有时效性，过期后需重新获取。

### 3. 运行爬虫

爬取分为两个阶段，可分开执行也可一次性执行：

```bash
# 阶段1: 收集论文 URL 列表（访问 navi.cnki.net，无需 Cookie）
uv run python -m cnki_crawler --phase1 --year 2024

# 阶段2: 爬取论文详情（访问 kns.cnki.net，需要 Cookie）
uv run python -m cnki_crawler --phase2 --cookies cookies.txt

# 一次性执行两个阶段
uv run python -m cnki_crawler --year 2024 --cookies cookies.txt
```

#### 更多选项

```bash
# 指定年份范围
uv run python -m cnki_crawler --phase1 --year 2020-2025

# 仅爬取特定期刊
uv run python -m cnki_crawler --phase1 --year 2024 --journal "中国图书馆学报"

# 显示详细日志
uv run python -m cnki_crawler --phase2 --cookies cookies.txt -v

# 查看所有参数
uv run python -m cnki_crawler --help
```

## 输出

结果保存在 `output/` 目录：

- **JSON** (`output/{期刊代码}_{年份}.json`) — 按期刊和年份分文件，结构化存储
- **CSV** (`output/all_articles.csv`) — 所有论文汇总，UTF-8 BOM 编码，Excel 可直接打开

## 断点续爬

两个阶段均支持断点续爬：

- **阶段1**: 已收集的刊期记录在 `paper_urls.json` 中，重新运行会自动跳过
- **阶段2**: 已爬取的论文标记为 `detail_crawled: true`，重新运行只处理未完成的

阶段2 连续 3 次触发验证码后会自动暂停，更新 `cookies.txt` 后重新运行即可继续。

## 期刊列表

待爬取的期刊在 `journals.csv` 中配置（期刊名 + CNKI 详情页 URL）。

## 项目结构

```
├── setup.ps1 / setup.sh    # 环境初始化脚本
├── journals.csv             # 期刊列表
├── cookies.txt              # 浏览器 Cookie（需手动创建，不入库）
├── paper_urls.json          # 阶段1 中间结果（不入库）
├── output/                  # 爬取结果（不入库）
└── src/cnki_crawler/        # 源代码
    ├── main.py              # CLI 入口，两阶段逻辑
    ├── session.py           # HTTP 会话管理
    ├── journal.py           # 期刊/刊期/论文列表
    ├── article.py           # 论文详情页解析
    ├── models.py            # 数据模型
    ├── exporter.py          # JSON/CSV 导出
    └── utils.py             # 工具函数
```
