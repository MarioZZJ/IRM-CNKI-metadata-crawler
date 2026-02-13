# CNKI 期刊论文元信息爬取分析

> 以"中国图书馆学报"（pykm=ZGTS）为例，分析期刊刊期浏览页面的交互机制与数据获取方法。

---

## 1. 刊期浏览与切换机制

### 1.1 页面入口

期刊详情页 URL 格式：
```
https://navi.cnki.net/knavi/detail?p={加密参数}&uniplatform=NZKPT
```

页面加载后，点击"刊期浏览"标签（`javascript:void(0)` 链接），触发左侧年期树和右侧论文列表的加载。

### 1.2 获取年份与刊期列表

**API 端点：**
```
POST https://navi.cnki.net/knavi/journals/{pykm}/yearList
```

**请求参数（form-urlencoded）：**
| 参数 | 说明 | 示例值 |
|------|------|--------|
| `pIdx` | 年份分页索引（0-based） | `0` |
| `time` | 服务端生成的加密令牌（从页面隐藏字段 `#time` 获取） | `8c6w9uuD4-Zcise...` |
| `isEpublish` | 是否网络首发（0=正式刊期，1=网络首发） | `0` |
| `pcode` | 出版源代码 | `CJFD,CCJD` |

**必需的请求头：**
```
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
Referer: https://navi.cnki.net/knavi/detail?p=...&uniplatform=NZKPT
language: CHS
uniplatform: NZKPT
```

**响应格式：** HTML 片段，包含年期树结构。关键结构如下：

```html
<input type="hidden" id="totalCnt" value="48"/>  <!-- 总年份数 -->

<!-- 每页约20个年份 -->
<div class="yearissuepage" id="yearissue0" pageindex="0">
  <dl id="2025_Year_Issue" class="s-dataList clearfix">
    <dt><em>2025</em></dt>
    <dd>
      <a id="yq202506" onclick='JournalDetail.BindIssueClick(this)'
         value="sepBzHVYNTn...加密值...">No.06</a>
      <a id="yq202505" value="...">No.05</a>
      <!-- ... 更多期 -->
    </dd>
  </dl>
  <!-- ... 更多年份 -->
</div>
```

**关键字段提取：**
- 年份：`<dl id="{year}_Year_Issue">` 中 `<em>` 标签的文本
- 期号：`<a>` 标签的 `id` 属性格式为 `yq{year}{issue}`（如 `yq202506`）
- 加密 yearIssue 值：`<a>` 标签的 `value` 属性，**每次会话生成不同的加密值**

**分页说明：**
- 每页约20个年份，通过 `pIdx` 参数翻页
- `totalCnt` 为总年份数，可用于计算总页数
- 该期刊总共有 48 个年份，分 3 页（0/1/2）

### 1.3 `pykm`（期刊代码）获取

`pykm` 是 CNKI 为每个期刊分配的**唯一简码**（通常为大写字母，一般4个字符），用于所有 API 路径中标识期刊。例如：
- 中国图书馆学报 → `ZGTS`
- 情报理论与实践 → `QBLL`

**获取方式：**

1. **从期刊详情页隐藏字段**（最可靠）：访问期刊详情页后，从 HTML 中提取 `<input id="pykm" value="ZGTS">`
2. **从期刊封面图 URL 推断**：封面图格式为 `https://c61.cnki.net/cjfd/small/{pykm小写}.jpg`，如 `qbll.jpg`
3. **从 RSS 链接提取**：RSS 链接格式为 `https://rss.cnki.net/knavi/rss/{pykm}?pcode=CJFD,CCJD`

**如何查找目标期刊的 pykm：**

通过出版来源搜索 API 按刊名检索：
```
POST https://navi.cnki.net/knavi/all/searchbaseinfo
```
请求体为 form-urlencoded，关键参数 `searchStateJson` 是一个 JSON 字符串，其中搜索值为期刊名称。响应 HTML 中包含期刊详情页链接（`/knavi/detail?p=...`），访问该链接即可从隐藏字段获取 `pykm`。

**searchStateJson 结构示例：**
```json
{
  "StateID": "",
  "Platfrom": "",
  "QueryTime": "",
  "Account": "knavi",
  "ClientToken": "",
  "Language": "",
  "CNode": {
    "PCode": "9R5HMN1M",
    "SMode": "",
    "OperateT": ""
  },
  "QNode": {
    "SelectT": "",
    "Select_Fields": "",
    "S_DBCodes": "",
    "Subscribed": "",
    "QGroup": [
      {
        "Key": "subject",
        "Logic": 1,
        "Items": [],
        "ChildItems": [
          {
            "Key": "txt",
            "Logic": 1,
            "Items": [
              {
                "Key": "txt_1",
                "Title": "",
                "Logic": 1,
                "Name": "LY",
                "Operate": "%",
                "Value": "'期刊名称'",
                "ExtendType": 0,
                "ExtendValue": "",
                "Value2": ""
              }
            ],
            "ChildItems": []
          }
        ]
      }
    ],
    "OrderBy": "",
    "GroupBy": "",
    "Additon": ""
  }
}
```
其余 form 参数：`displaymode=1&pageindex=1&pagecount=10&index=UXTGKYC2&searchType=来源名称&parentcode=BTBKQV4X&clickName=&switchdata=search`

**简便方法**：如果只需少量期刊，直接在浏览器中打开 `https://navi.cnki.net/knavi/` 搜索期刊名称，进入详情页后查看页面源代码中 `id="pykm"` 的 value 即可。

### 1.4 `time` 令牌

- 由**服务端渲染**在页面 HTML 中的隐藏字段 `<input id="time">`
- **每次页面加载时重新生成**，必须从页面解析获取
- 仅 `yearList` 接口需要此参数

---

## 2. 获取指定刊期的论文列表

### 2.1 论文列表 API

**API 端点：**
```
POST https://navi.cnki.net/knavi/journals/{pykm}/papers?yearIssue={加密值}&pageIdx={页码}&pcode=CJFD,CCJD&isEpublish=0
```

**URL 查询参数：**
| 参数 | 说明 |
|------|------|
| `yearIssue` | 从 yearList 响应中获取的加密刊期标识 |
| `pageIdx` | 论文列表分页索引（0-based，通常一期论文不超过一页） |
| `pcode` | `CJFD,CCJD` |
| `isEpublish` | `0`（正式刊期） |

**请求体：** 空（Content-Length: 0），但 Method 为 POST

**请求头：** 同 yearList（需要 `X-Requested-With`、`language`、`uniplatform`）

### 2.2 响应 HTML 结构

```html
<div>
  <div>
    <dt class="tit">专栏:中国特色图书情报学</dt>   <!-- 栏目标题（可为空） -->

    <dd class="row clearfix bgcGray">
      <span class="name">
        <a target="_blank"
           href="https://kns.cnki.net/kcms2/article/abstract?v={加密值}&uniplatform=NZKPT&language=CHS">
          论文标题文本
        </a>
        <b name="encrypt" id="ZGTS202506001" value="">  <!-- 文章编号 -->
          <label>免费</label>
        </b>
      </span>
      <span class="author" title="作者1;作者2;">作者1;作者2;</span>
      <span class="company" title="起止页码">4-17</span>
    </dd>

    <!-- 更多论文... -->
  </div>
</div>
```

**提取目标：**
- **标题**：`dd.row > span.name > a` 的文本内容
- **论文详情 URL**：`dd.row > span.name > a` 的 `href` 属性
- **作者列表**（预览）：`dd.row > span.author` 的 `title` 属性
- **页码**：`dd.row > span.company` 的 `title` 属性
- **栏目**：`dt.tit` 的文本（同一 `<div>` 下的所有 `<dd>` 属于该栏目）

---

## 3. 论文详情页元信息提取

### 3.1 详情页 URL 格式

```
https://kns.cnki.net/kcms2/article/abstract?v={加密参数}&uniplatform=NZKPT&language=CHS
```

### 3.2 页面 HTML 结构与提取方法

详情页为**服务端渲染的 HTML 页面**，所有元信息都在 DOM 中。

| 字段 | CSS 选择器 | 提取方式 | 示例值 |
|------|-----------|---------|--------|
| **标题** | `.wx-tit h1` | `.text` 去除尾部"附视频"等标签 | "人工智能+"背景下的高质量数据集建设… |
| **作者** | `#authorpart a` | 每个 `<a>` 内首个文本节点为姓名，`<sup>` 为单位编号 | 张晓林 `<sup>1,2</sup>` |
| **单位列表** | `.wx-tit h3.author`（第二个） | 内部 `<a>` 标签文本，格式 "编号.单位名" | "1.上海科技大学", "2.中国科学院文献情报中心" |
| **摘要** | `#ChDivSummary` | `.text` | 全文摘要文本 |
| **关键词** | `.keywords a` | 每个 `<a>` 的文本，以分号分隔 | "人工智能+;", "高质量数据集;", ... |
| **基金资助** | `.funds` | `.text`（标签标题为"基金资助："） | "国家社会科学基金重大项目…(项目编号:23&ZD224)…" |
| **分类号** | `.clc-code` | `.text` | "TP18;TP311.13;G250.7" |
| **DOI** | `.top-space` 中标签为"DOI："的 `<p>` | `.text` | "10.13530/j.cnki.jlis.2025046" |

**详细 DOM 结构示例：**

```html
<!-- 标题 -->
<div class="wx-tit">
  <h1> "人工智能+"背景下的高质量数据集建设：图书馆的机遇与挑战
    <span id="corr-video" style="display:none">附视频</span>
  </h1>

  <!-- 作者（第一个 h3#authorpart） -->
  <h3 class="author" id="authorpart">
    <span>
      <a href="...">张晓林<sup>1,2</sup><i class="icon-email"></i></a>
      <p class="authortip">zhangxl@mail.las.ac.cn</p>
      <input class="authorcode" type="hidden" value="000030221324">
    </span>
  </h3>

  <!-- 单位（第二个 h3.author） -->
  <h3 class="author">
    <span><a href="...">1.上海科技大学</a></span>
    <span><a href="...">2.中国科学院文献情报中心</a></span>
  </h3>
</div>

<!-- 摘要 -->
<div class="row">
  <span class="rowtit">摘要：</span>
  <p id="ChDivSummary">摘要全文...</p>
</div>

<!-- 关键词 -->
<div class="row">
  <span class="rowtit">关键词：</span>
  <p class="keywords">
    <a href="...">人工智能+;</a>
    <a href="...">高质量数据集;</a>
    ...
  </p>
</div>

<!-- 基金资助（并非所有论文都有） -->
<div class="row">
  <span class="rowtit">基金资助：</span>
  <p class="funds">
    <span><a href="...">国家社会科学基金重大项目"..."(项目编号:23&ZD224)的研究成果；</a></span>
  </p>
</div>

<!-- 分类号 -->
<li class="top-space">
  <span class="rowtit">分类号：</span>
  <p class="clc-code">TP18;TP311.13;G250.7</p>
</li>
```

**注意事项：**
- 基金资助字段 **并非所有论文都有**，需做可选处理
- 作者页面有两个 `h3.author`：第一个（`id="authorpart"`）是作者列表，第二个是单位列表
- 关键词以分号结尾，需去除尾部分号和空白
- 标题中可能包含隐藏的 `<span>` 标签（如"附视频"），提取时需过滤

---

## 4. 认证与反爬机制

### 4.1 Cookies

| Cookie 名 | 说明 | 获取方式 |
|-----------|------|---------|
| `JSESSIONID` | 服务端 Session ID | 首次访问时由服务器 Set-Cookie |
| `Ecp_ClientId` | 客户端标识 | 首次访问时生成 |
| `Ecp_IpLoginFail` | IP 登录失败记录 | 服务端设置 |
| `cnkiUserKey` | 用户标识 UUID | 首次访问时生成 |
| `SID_navi` | 导航系统会话 ID | 首次访问 navi 站点时生成 |
| `kcmscanary` / `kcmscanarytag` | 金丝雀标记（灰度发布） | 服务端设置 |

### 4.2 腾讯滑块验证码（Tencent Captcha）

- 页面底部始终存在验证码组件：`拖动下方拼图完成验证`
- 使用 **腾讯天御验证码** (`turing.captcha.qcloud.com/TJCaptcha.js`)
- 触发条件：请求频率过高、异常访问模式
- 验证码类型：**滑块拼图验证**（drag slider to complete puzzle）
- 相关 JS：`tencentSlide.js`

### 4.3 加密参数

| 参数 | 位置 | 说明 |
|------|------|------|
| `time` | 页面隐藏字段 `#time` | 服务端渲染的令牌，yearList API 必需，每次页面加载都不同 |
| `yearIssue` (value) | yearList 响应中 `<a>` 的 `value` 属性 | 加密的刊期标识，每次会话不同 |
| `v` (URL 参数) | 论文详情页 URL | 加密的文章标识 |
| `p` (URL 参数) | 期刊详情页 URL | 加密的期刊标识 |

### 4.4 请求头检测

以下自定义请求头为 **必需**，缺少可能导致请求被拒绝：
```
X-Requested-With: XMLHttpRequest
language: CHS
uniplatform: NZKPT
Referer: https://navi.cnki.net/knavi/detail?p=...
```

### 4.5 跨域配置

- 响应头 `Access-Control-Allow-Origin: *.cnki.net` — 仅允许 cnki.net 域名
- 响应头 `Access-Control-Allow-Credentials: true` — 需要携带 Cookie

### 4.6 其他注意事项

- 该网站涉及 **两个域名**：
  - `navi.cnki.net` — 期刊导航、刊期浏览、论文列表
  - `kns.cnki.net` — 论文详情页
- 两个域名共享部分 Cookie（`Ecp_ClientId`、`cnkiUserKey`），但 `JSESSIONID` 独立
- 无需登录即可访问元信息（标题、摘要、关键词等），但**下载全文需要登录/付费**
- 频繁请求会触发滑块验证码，建议在爬虫中**加入合理的请求间隔**

---

## 5. 爬虫实现要点总结

### 5.1 整体流程

```
1. 访问任意一个期刊的详情页 → 获取 Session Cookie 和 time 令牌
2. 用 time + 目标 pykm 调用 yearList API (pIdx=0,1,2...) → 获取所有年份及其刊期的加密 yearIssue 值
3. 过滤目标年份，遍历其所有刊期
4. 对每个刊期调用 papers API → 获取论文标题和详情页 URL
5. 对每篇论文访问详情页 → 解析 HTML 提取元信息
```

### 5.2 关键发现：`time` 令牌不绑定期刊

经实测验证：
- **`time` 令牌是会话级别的**，不与特定期刊绑定
- 从任意一个期刊详情页获取的 `time`，可用于查询**任何**期刊的 yearList 和 papers
- 这意味着：只需访问一次任意期刊详情页获取 `time`，即可用已知的 `pykm` 批量查询多个期刊
- **`time` 有时效性**，过期后需重新访问详情页获取

因此，**只要知道 `pykm`，配合一个有效的 `time` 令牌，就能获取该期刊所有刊期的所有论文 URL**。

### 5.3 关键变量来源

| 变量 | 来源 | 作用域 |
|------|------|--------|
| `pykm` | 期刊详情页隐藏字段 `#pykm`，或提前已知 | 标识目标期刊 |
| `time` | 任意期刊详情页隐藏字段 `#time` | 会话级，可跨期刊使用 |
| `pCode` | 固定值 `CJFD,CCJD` | — |
| `yearIssue` | yearList API 响应中 `<a>` 的 `value` 属性 | 每次会话不同 |
| 论文 URL | papers API 响应中 `span.name > a` 的 `href` | 可直接访问 |

### 5.3 推荐技术栈

- **HTTP 客户端**: `requests` + `requests.Session`（维持 Cookie）
- **HTML 解析**: `BeautifulSoup4` 或 `lxml`
- **反爬应对**: 合理间隔（2-5秒）、随机 User-Agent、异常重试
- **可选**: `Selenium`/`Playwright`（如需处理滑块验证码）
