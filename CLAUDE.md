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
- requests + requests.Session（维持 Cookie）
- BeautifulSoup4 + lxml（HTML 解析）
- 命令行参数: argparse

## 架构设计

### 两阶段执行
爬取分为两个独立阶段，原因是 navi.cnki.net（期刊导航）和 kns.cnki.net（论文详情）的反爬策略不同：

1. **阶段1** (`--phase1`): 收集论文 URL 列表
   - 访问 navi.cnki.net，反爬较宽松
   - 获取所有期刊的年份/刊期列表，提取每篇论文的 URL
   - 结果保存到 `paper_urls.json`（中间文件）
   - 支持断点续爬（已完成的刊期自动跳过）

2. **阶段2** (`--phase2`): 爬取论文详情
   - 访问 kns.cnki.net，反爬较严格（频繁触发点选验证码）
   - 逐篇解析论文详情页 HTML
   - 支持断点续爬（已完成的论文自动跳过）
   - 连续3次触发验证码后自动暂停

### 模块结构
```
src/cnki_crawler/
├── __init__.py
├── __main__.py      # python -m 入口
├── main.py          # CLI 入口，两阶段逻辑
├── session.py       # Session 管理，获取 time 令牌和 pykm
├── journal.py       # 期刊级操作：yearList、papers 列表
├── article.py       # 论文详情页解析
├── models.py        # 数据模型定义
├── exporter.py      # JSON/CSV 导出
└── utils.py         # 工具函数（延迟、日志、UA）
```

### 关键策略
- **请求间隔**: 3-5 秒随机延迟
- **验证码处理**: 检测302重定向到/verify/页面，连续3次后暂停，提示用户手动处理
- **Cookie 导入**: 支持从浏览器导出 Cookie 注入到 requests Session，绕过验证码
- **断点续爬**: paper_urls.json 中的 detail_crawled 字段标记每篇论文的爬取状态
- **进度显示**: 实时显示当前进度

### 反爬与验证码说明
- **navi.cnki.net**（阶段1）：反爬宽松，Python requests 直接访问即可，无需特殊处理
- **kns.cnki.net**（阶段2）：反爬严格，Python requests 裸请求会立即触发点选文字验证码（clickWord），即使同一 IP 在浏览器中可以正常访问
- **根本原因**：CNKI 同时检查 IP 和 Cookie/会话状态。浏览器有完整的 Cookie 和 JS 执行环境，而 requests 是裸 HTTP 客户端，缺少关键 Cookie（如 `cnkiUserKey`、`SID_kns_new` 等），因此被识别为爬虫
- **解决方案**：从浏览器导出 Cookie 保存到 `cookies.txt`，爬虫通过 `--cookies` 参数加载后即可正常访问
- **Cookie 时效**：Cookie 有有效期，过期后需重新从浏览器获取

## 命令行用法
```bash
# 阶段1: 收集论文 URL 列表
uv run python -m cnki_crawler --phase1 --year 2024

# 阶段2: 爬取论文详情（需要 cookies.txt）
uv run python -m cnki_crawler --phase2 --cookies cookies.txt

# 仅爬取指定期刊
uv run python -m cnki_crawler --phase1 --year 2024 --journal "中国图书馆学报"

# 一次性执行两个阶段（默认模式）
uv run python -m cnki_crawler --year 2024 --cookies cookies.txt
```

### Cookie 获取方法
1. 在 Chrome 浏览器中访问任意一篇 CNKI 论文详情页（如有验证码则手动通过）
2. 打开开发者工具（F12）→ Console，执行 `document.cookie`
3. 将输出的 cookie 字符串保存到项目根目录的 `cookies.txt` 文件中
4. 运行阶段2时通过 `--cookies cookies.txt` 加载

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

## 状态
- [x] 需求分析
- [x] 项目初始化（uv、git）
- [x] 编码实现
- [x] 阶段1 测试通过（URL收集正常）
- [x] 阶段2 验证码检测正常
- [x] 阶段2 浏览器Cookie导入方案验证通过（53篇论文全部成功解析）
