---
name: information-clipper
description: 信息剪报 Skill — 接收链接，自动抓取网页内容并整理为标准 Markdown，存入本地剪报库。支持微信公众号、即刻、Bilibili、知乎等多个平台，生成含元数据的结构化文档，适合作为知识管理或个人阅读存档的工作流。
author: TaohongMaxwell
repository: https://github.com/TaohongMaxwell/information-clipper
---

# 信息剪报 Skill

## 目录路径

```
CLIP_DIR = /path/to/your/clip/directory   # 示例路径，请替换为实际目录
```

> ⚠️ 若克隆到其他机器使用，请将 `CLIP_DIR` 替换为本地实际路径。

## 功能

接收一个或多个链接，自动抓取页面内容，提取元数据，生成标准 Markdown 存入剪报目录。

**剪报原则（最重要）**：
- **正文 = 原文照录**，只做清洗，不做理解、不做压缩、不做重组
- `##` 二级标题 = 原文本身就有的分段标记，不是 AI 自行概括的小标题
- 如果原文没有自然分段，不要强行插入 `##`（纯流水文字也比擅自重组好）
- Summary 是 frontmatter 里的元数据摘要，与正文无关

**质量标准**：
- 正文必须是原文的忠实副本，清洗掉干扰内容即可
- HTML 注释、JS 变量、CSS 类名等垃圾内容必须清除
- 正文在有意义的位置截断，不在句子中间断开

**筛选标准**：就一个字 — **爽**。不只追求有用，不只追求体系，"这个挺有意思"就随手存一下。不要求每篇都系统有用，更注重趣味性和个人启发。

支持变更追溯：同一链接再次抓取时，**追加或插入新内容到原文之后**，保留所有历史版本，不替换原文。

## 入口

用户发送链接并要求收藏时，自动触发本 Skill。
用户要求更新/刷新已有剪报时，自动触发增量更新流程。

## 文件命名规范

- 格式：`YYYY.MM.DD-标题.md`
- 日期：记录日期，非原文发布日期
- 标题：取自原标题，前 20 字，若已存在则追加 `-1`、`-2` 序号

## 操作流程

### 第一步：接收并解析链接

接收用户发来的 URL，解析平台类型：

- `github.com` → GitHub 平台
- `jike.com` / `okjike.com` → 即刻平台
- `bilibili.com` / `b23.tv` → Bilibili 平台
- `zhihu.com` → 知乎平台
- `xiaohongshu.com` → 小红书平台
- `mp.weixin.qq.com` → 微信公众号平台
- `feishu.cn` / `larksuite.com` → 飞书文档平台
- 其他域名 → 通用网页

### 第二步：检查是否已存在

在 `CLIP_DIR` 目录下查找是否有以该 URL 对应的文件。

- **若不存在** → 走全新创建流程（第三步~第六步）
- **若已存在** → 走增量更新流程（第七步）

### 第三步：抓取页面内容（全新创建）

#### GitHub

- 尝试 GitHub API 获取仓库/文件元信息（创建时间、更新时间、描述）
- README 内容通过 `https://raw.githubusercontent.com/` 获取

#### 即刻（m.okjike.com）

即客帖是 SPA，所有数据以 JSON 形式嵌在 `<script>` 标签里。步骤：
1. 用 `urllib.request` 抓取页面（`browser_navigate` 超时严重，不推荐）
2. 用 `re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)` 提取所有 script
3. 遍历找包含 `'props\":\\u4e3bpageProps\\u4e0bpost'` 且 `len(s) > 10000` 的 script
4. `json.loads(脚本内容)` 后，文章数据在 `data['props']['pageProps']['post']`
5. 字段映射：
   - 正文：`post['content']`
   - 作者：`post['user']['username']` / `post['user']['nickname']` / `post['user']['bio']`（注意不是 `post['author']`）
   - 时间：`post['createdAt']`
   - 点赞/评论/转发：`post['likeCount']` / `post['commentCount']` / `post['repostCount']`
   - 评论列表：`data['props']['pageProps'].get('comments', [])`，每人取 `c['content']` 和 `c['user']['nickname']`
6. 注意：同一帖子第二次抓可能返回 529（服务器限流），隔几秒再试即可成功

**即刻帖子必须保留评论区**：评论是内容的重要组成部分，必须完整保留到正文中，绝不能截断删掉。具体格式：
   ```
   {帖子正文内容}

   ---

   ## 评论区

   【{用户昵称}】：{评论内容}

   【{用户昵称}】：{评论内容}
   ```
   - 评论标题统一用 `## 评论区`
   - 每条评论格式：`【昵称】：内容`，多条按出现顺序排列
   - 如果有评论回复嵌套，只保留顶层评论（`c['replyToUser']` 为空则保留）
   - 评论内容本身如包含 `#` 话题标签等，保留原样

#### 微信公众号（mp.weixin.qq.com）

同样是 SPA，内容嵌在 JS 里。步骤：
1. 用 `urllib.request` 抓取（User-Agent 设为 iPhone Safari 可绕过部分限制）
2. 从 HTML 中提取元数据：
   - 标题：`re.search(r'og:title[\"\\s]*content[\"\\s]*=[\"\\s]*[\"\\']([^\"\\']+)[\"\\']', content, re.I)`
   - 作者：`re.search(r'var author = \"([^\"]*)\"', content)`
   - 时间戳：`re.search(r'var ct = \"(\\d+)\"', content)` → `int(ts)` 转 Unix 时间戳
3. **⚠️ 正文提取必须用 HTMLParser，不能用 regex 标签内文本法**：
   - 微信文章的 js_content div 带有 `style="visibility: hidden; opacity: 0;"`，用 `re.findall(r'>([^<]+)<')` 会遗漏大量内容
   - 正确方法：用 Python `html.parser.HTMLParser` 遍历 DOM，跳过 `script/style/noscript` 标签，收集其余所有 `handle_data`，得到完整正文
   - 示例：
     ```python
     class TextExtractor(html.parser.HTMLParser):
         def __init__(self):
             super().__init__()
             self.texts = []
             self.skip_tags = {'script', 'style', 'noscript', 'iframe', 'embed', 'object'}
             self.current_skip = 0
         def handle_starttag(self, tag, attrs):
             if tag in self.skip_tags:
                 self.current_skip += 1
             elif tag in ('br', 'p', 'section'):
                 if self.current_skip == 0:
                     self.texts.append('\n')
         def handle_endtag(self, tag):
             if tag in self.skip_tags:
                 self.current_skip = max(0, self.current_skip - 1)
             elif tag in ('p', 'section'):
                 if self.current_skip == 0:
                     self.texts.append('\n')
         def handle_data(self, data):
             if self.current_skip == 0:
                 text = data.strip()
                 if text:
                     self.texts.append(text + ' ')
     ```
   - **⚠️ 重要：不要用 `re.sub(r'\s+', ' ', text)` 合并所有空格！** 这会把段落间的换行全部压掉。正确做法是：
     - HTMLParser 在 `<p>/<section>` 时已插入 `\n`
     - 最后只需做：`text = text.strip()` 去掉首尾空白，`re.sub(r' +\n', '\n', text)` 去掉段尾多余空格
     - 禁止：`re.sub(r'\s+', ' ', ...)` 这条规则对正文清洗禁用！
   - **⚠️ 重要：部分公众号（如同出自三联生活实验室）的文章内容不在 js_content 内，而是直接在 `id="img-content"` 外层容器中**。判断方法：先按 js_content 截取，如果提取到的正文少于 2000 字，立即 fallback 到 img-content 区域重新提取：
     ```python
     # 方法：从 img-content 位置开始截取，到 js_pc_qr_code 或 js_cp_tool 之前
     img_content_start = content.find('id="img-content"')
     img_content_end = content.find('id="js_pc_qr_code"', img_content_start)
     if img_content_end == -1:
         img_content_end = content.find('id="js_cp_tool"', img_content_start)
     article_html = content[img_content_start:img_content_end]
     ```
   - 截断范围：js_content 开始位置到 `js_pc_qr_code` 或 `js_cp_tool` 之前
4. **正文清洗**：
   - 拼接所有提取文本后，用 `re.sub(r'\s+', ' ', text)` 合并空格
   - 清除 HTML 实体：`re.sub(r'&\w+;', '', text)`
   - 清理开头无用元数据（作者、编辑行）
   - **截断**：在文末找到 `预览时标签不可点`、`未经授权`、`值班主编`、`排版` 等标记之一，在其位置截断，不要在句子中间断开
   - 保留文章中已有的自然段落结构（电视剧照引用等保留）
5. 公众号评论区不在页面内，无需处理
6. **⚠️ 微信频率限制**：同一 IP 短时间内多次请求会被拦截（空白页面或 403）。失败后等 5~10 秒再重试，连续 3 次失败才放弃
7. **⚠️ 跨平台差异**：飞书转发链接可能抓取失败，微信直接打开的链接更可靠

#### 飞书文档（feishu.cn / larksuite.com）

飞书文档是 **SPA**，内容通过 API 渲染。必须使用飞书开放 API 获取内容：

**前置准备**：需要 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`（环境变量或手动提供）。

**Step 1 — 获取 tenant_access_token**：
```python
import urllib.request, json

APP_ID = "cli_xxxx"
APP_SECRET="***"

url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
data = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode()
req = urllib.request.Request(url, data=data)
req.add_header('Content-Type', 'application/json')
response = urllib.request.urlopen(req, timeout=15)
token = json.loads(response.read().decode())['tenant_access_token']
```

**Step 2 — 从 wiki URL 提取 wiki_token**：
- URL 格式：`https://my.feishu.cn/wiki/FwwzwIjVBikPqSk8khDc1AmXnle`
- wiki_token = `FwwzwIjVBikPqSk8khDc1AmXnle`

**Step 3 — 调用 wiki API 获取 obj_token 和 obj_type**：
```python
wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token=***
req = urllib.request.Request(wiki_url)
req.add_header('Authorization', f'Bearer {token}')
resp = urllib.request.urlopen(req, timeout=15)
result = json.loads(resp.read().decode())
node = result['data']['node']
obj_token = node['obj_token']   # 用于获取文档内容
obj_type = node['obj_type']    # 通常是 "docx"
title = node['title']          # 文档标题
```

**Step 4 — 调用 docx API 获取文档 blocks**：
```python
doc_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{obj_token}"
req = urllib.request.Request(doc_url)
req.add_header('Authorization', f'Bearer {token}')
resp = urllib.request.urlopen(req, timeout=15)
doc_result = json.loads(resp.read().decode())
# 文档标题也可以从这里取：doc_result['data']['document']['title']
```

**Step 5 — 获取所有 blocks（正文内容）**：
```python
blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{obj_token}/blocks"
req = urllib.request.Request(blocks_url)
req.add_header('Authorization', f'Bearer {token}')
resp = urllib.request.urlopen(req, timeout=15)
result = json.loads(resp.read().decode())
items = result['data']['items']   # list of blocks
```

**Step 6 — 解析 blocks 提取文本**：
```python
# block_type → 字段名映射
TYPE_FIELDS = {
    1: 'page', 2: 'text', 3: 'heading1', 4: 'heading2', 5: 'heading3',
    6: 'heading4', 12: 'bullet', 13: 'ordered', 14: 'todo', 15: 'code',
    16: 'quote', 27: 'divider', 31: 'table', 32: 'table_row',
    33: 'table_cell', 34: 'quote_container',
}

def get_block_text(block):
    bt = block.get('block_type', 0)
    field = TYPE_FIELDS.get(bt)
    if not field or field not in block:
        return ''
    content = block[field]
    if isinstance(content, dict) and 'elements' in content:
        return ''.join(
            e['text_run'].get('content', '')
            for e in content['elements']
            if 'text_run' in e
        )
    return ''

type_names = {1:'页面标题', 2:'文本', 3:'H1', 4:'H2', 5:'H3',
               12:'列表项', 14:'代码块', 16:'引用', 27:'分隔线'}

for block in items:
    text = get_block_text(block)
    if text:
        bt = block.get('block_type', 0)
        type_name = type_names.get(bt, f'T{bt}')
        print(f"[{type_name}] {text}")
```

**⚠️ 注意事项**：
- 飞书 wiki 有两种链接格式：
  - `https://my.feishu.cn/wiki/{wiki_token}` → 个人空间
  - `https://xxx.feishu.cn/wiki/{wiki_token}` → 租户空间
  - 两种格式都走同一个 wiki API，结果一样
- `source_platform` 填写 `feishu`
- 飞书文档通常结构清晰（多级标题、列表），保留原文层级结构

#### Bilibili

- 视频：获取标题、简介、发布时间
- 专栏：获取标题、正文、发布时间

#### 通用网页

- 使用 browser 工具或 HTML 解析方式获取页面内容
- 提取 `<title>` 作为标题
- 提取 `<meta name="published" / "date" / "article:published_time">` 作为原文发表时间
- 提取 `<meta name="lastmod" / "article:modified_time">` 或 GitHub 文件的 `commit.date` 作为最近修改时间
- 提取 `<meta name="keywords">` 作为关键词兜底
- 提取 `<article>` 或正文主要区域内容

### 第四步：提取正文并排版

**原则：原文照录，不重组、不压缩、不概括。**

**步骤**：
1. 清洗 HTML 标签，保留纯文本
2. 去除广告、导航栏、侧边栏、评论区、分享按钮等干扰内容
3. 保留原文主体内容

**排版规范（仅在原文本身有结构时使用）**：
- 原文有列表（`1.` `a.` `-` `*`）→ 保留为 Markdown 有序/无序列表
- 原文有分段（有空行分隔）→ 保留原段落边界
- 代码块 → 用 ``` 包裹
- 引用块 → 用 `>` 保留

**必须清除的垃圾内容**：
- HTML 注释：`re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)`
- JS 变量：`re.sub(r'window\.\w+\s*=.*?;', '', text)`
- CSS 类名/选择器：`re.sub(r'\.[a-zA-Z][\w-]*\{[^}]*\}', '', text)`
- `.weui-*`、`.js_*`、`var ` 开头等残留：`re.sub(r'(var |\.(?:weui|js_)[a-zA-Z0-9_-]*)[^<]*', '', text)`

**截断位置**：在有意义的位置截断（如段尾、小节末尾），绝对不能在句子中间断开。

**⚠️ 禁止行为**：
- ❌ 不要用 AI 理解后重新概括段落大意
- ❌ 不要把长文缩写成"核心观点"
- ❌ 不要把几个段落合并成一个 AI 理解的小节
- ❌ 不要在原文没有分段的位置强行插入 `##` 二级标题

### 第五步：计算关键词

**步骤**：
1. 文本分词（按空格和标点分割，保留中文连续词）
2. 过滤停用词表
3. 统计词频，选取 TOP 10 高频词
4. 标题中已出现的词优先保留
5. 取 3~5 个最有代表性的词作为关键词

**停用词标准表**（内置，无需外部依赖）：

中文常见停用词：`的、了、和、是、在、有、我、你、他、她、它、们、这、那、要、都、被、把、能、会、与、对、向、给、从、到、为、所以、因为、但是、而且、以及、或者、如果、虽然、那么、什么、怎么、多少、哪个、自己、一是、二是、三是、可以、已经、不能、没有`

英文常见停用词：`the、a、an、is、are、was、were、be、been、being、have、has、had、do、does、did、will、would、could、should、may、might、can、to、of、in、for、on、with、at、by、from、as、into、through、during、before、after、and、or、but、if、because、while、that、this、it、its`

### 第六步：填写 frontmatter 元数据

**summary 字段**：一句话说明这篇文章**是什么**，用于快速判断内容。不需要概括全文观点，只需要描述文章类型和主题。参考写法：
- 例子：文章类型（采访/评测/观点/技术科普）+ 核心主题 + 适读场景
- 示例：`summary: 虎嗅对DeepSeek V4的技术解读，聚焦工程效率改进与单位智能成本下降，不追逐榜单排名。`

**keywords**：从正文中提取出现频率最高且有实际意义的词，取 3~5 个。标题中已出现的词优先保留。

**tags**：主题标签，如 `[AI, 大模型, 技术解读]`。

### 第七步：写入 Markdown（全新创建）

**文件路径**：`CLIP_DIR/{文件名}.md`

**Frontmatter 格式**：

```markdown
---
title: {原标题}
type: raw
maturity: draft
date: {记录日期，YYYY-MM-DD}
updated: {最近修改时间，YYYY-MM-DD}
source_platform: {来源平台}
original_url: {原文链接}
recorded_at: {记录时间，YYYY-MM-DD HH:mm:ss}
summary: {AI 总结的摘要，50-80字，一两句话概括核心观点；不是前300字原文拼接}
keywords: [{关键词列表，逗号分隔}]
tags: [{标签列表}]
---

{正文原文}

---

## 变更记录

- {记录时间} — 初始创建
```

### 第八步：增量更新（文件已存在）

当同一 URL 再次被抓取时，按以下规则处理：

**原则：追加或插入，不替换原文，保留完整变更历史。**

1. **抓取新内容**，与原文对比，找出差异（新增段落、修改、评论更新等）
2. **读取现有文件**，找到 `## 变更记录` 区域
3. **在 `## 变更记录` 下方插入本次变更块**：
   ```markdown
   ## 变更记录
   
   ### {本次变更时间，YYYY-MM-DD HH:mm}
   
   #### 新增内容
   {新增的正文内容，原文照录}
   
   #### 内容对比摘要
   {简要说明这次变更的内容，如"评论区新增5条评论"、"补充了架构图说明"、"更新了版本号从1.2到1.3"等}
   ```
4. **更新 frontmatter 中的 `updated` 字段**为当前时间
5. **绝对不修改、覆盖或删除任何已有的正文内容**

### 第九步：通知用户

- **全新创建**：告知已保存的文件名和路径
- **增量更新**：告知更新的内容摘要（"检测到N处变更，已追加到变更记录"）
- **抓取失败**：告知原因，询问是否以"仅链接+标题"形式记录

---

## 目录结构

```
CLIP_DIR/                    ← 剪报 raw 层（本 Skill 维护）
├── README.md               ← 剪报目录说明（如不存在需创建）
├── YYYY.MM.DD-标题.md
└── ...
```

> ⚠️ 若克隆到其他机器使用，请将 `CLIP_DIR` 替换为本地实际路径。

**首次运行须知**：每次在新环境首次执行本 Skill 前，需检查 `CLIP_DIR/README.md` 是否存在。若不存在，请参考以下模板创建目录级 README，告知可访问该目录的用户和 agents 这个文件夹的用途，并注明详细信息请参考本 Skill：

```markdown
# 剪报

这是一个本地网页内容收藏库——把散落在各处的感兴趣的内容，以结构化 Markdown 的形式存档在这里。

## 这是什么

"剪报"的 AI 版本：不用自己动手整理，只需要把觉得有意思的链接扔给 AI，它会咔嚓一下把好东西剪下来，贴成一个完整的文档。

筛选标准就一个字 — **爽**。"这个挺有意思"就随手存，不要求每篇都系统有用，更注重趣味性和个人启发。

## 目录结构

```
剪报/
├── README.md              ← 本文件
├── .bak/                  ← 备份目录（自动清理，保留30天）
├── YYYY.MM.DD-标题.md     ← 单篇剪报
└── ...
```

## 单篇剪报格式

每篇是一个完整的 Markdown 文件，包含：
- **frontmatter 元数据**：标题、来源平台、原文链接、标签、关键词、摘要
- **正文**：原文照录，只做清洗，不做压缩重组
- **变更记录**：追踪原文的历次更新

## 快速上手

### 收藏新链接
直接发送链接给 AI，说"收藏一下"即可。

### 查看最近存了什么
说"总结剪报"或"剪报概览"，AI 会输出目录级的聚合统计。

### 了解更多
技术细节和完整操作规范，请参考 Information Clipper Skill：
```
/opt/data/skills/productivity/information-clipper/SKILL.md
```

## 已知说明

- **正文 = 原文照录**：不重组、不压缩、不概括
- **增量更新**：同一链接再次抓取时，内容追加到变更记录，不替换原文
- **平台覆盖**：微信公众号、即刻、Bilibili、知乎、小红书、GitHub、飞书文档、通用网页
```

---

## 剪报总结（目录级 Digest）

当用户要求"总结剪报"、"剪报概览"、"剪报目录摘要"时，触发本功能。

### 核心原则

剪报总结是**目录级聚合分析**，不是单篇文章的摘要重写。

**不做的事**：
- ❌ 不要重新理解/重写每篇文章的 summary
- ❌ 不要对正文再做摘要
- ❌ 不要生成行动建议或阅读路线

**该做的事**：
- ✅ 读取所有剪报文件的 frontmatter 元数据
- ✅ 聚合统计：标签分布、关键词频率、平台分布、时间趋势
- ✅ 抽样展示摘要样本，让用户快速感知内容调性
- ✅ 输出完整文件清单

### 操作步骤

**第一步：扫描目录**

读取 `CLIP_DIR` 下所有 `.md` 文件（排除 README.md），提取 frontmatter 元数据（date、platform、tags、keywords、summary）。

**第二步：聚合统计**

- **篇数统计**：总篇数、近7天篇数、时间跨度
- **平台分布**：Counter 统计各平台篇数
- **标签 TOP**：所有 tags 合并后取 TOP 15
- **关键词 TOP**：所有 keywords 合并后取 TOP 20
- **时间线**：按日期统计每日新增篇数

**第三步：摘要样本**

取前 8 篇有 summary 的文件，展示摘要文本，让用户快速感知内容调性。

**第四步：文件清单**

生成完整表格：| 日期 | 平台 | 标题 | 标签 |

**第五步：输出 Markdown**

```markdown
# 📰 剪报目录总结

**生成时间**：YYYY-MM-DD HH:MM
**剪报总数**：XX 篇
**涵盖平台**：github(3), 即刻(12), 微信公众号(8), ...
**时间跨度**：2026-04-18 ~ 2026-04-26
**近7天新增**：X 篇

---

## 🗓️ 近7天动态
- **2026-04-26**：+3 篇
- ...

## 🏷️ 全量标签 TOP 15
- `AI` ×12
- `职场` ×7
- ...

## 🔑 全量关键词 TOP 20
- `LLM` ×15
- ...

## 📋 摘要样本（前8篇）
> 摘要文本...

## 📂 完整文件清单
| 日期 | 平台 | 标题 | 标签 |
...
```

### 运行脚本

已内置 Python 脚本，可直接运行：

```bash
python3 /opt/data/skills/productivity/information-clipper/scripts/clip_summary.py
```

脚本路径：
```
/opt/data/skills/productivity/information-clipper/scripts/clip_summary.py
```

### 触发关键词

以下任一表述均触发本功能：
- "总结剪报"
- "剪报概览"
- "剪报目录"
- "最近存了什么"
- "剪报有多少篇"

---

## 元数据字段说明

| 字段 | 必填 | 获取方式 | 示例 |
|------|------|---------|------|
| **title** | ✅ | 原文 `<title>` 或 og:title | `title: RF-GPT: 无线语言模型让AI看懂无线信号` |
| **type** | ✅ | 固定值，标识原材料层 | `type: raw` |
| **maturity** | ✅ | 默认 `draft`；需复核后改为 `reviewed` | `maturity: draft` |
| **date** | ✅ | 记录日期（不是原文发布日期），格式 `YYYY-MM-DD` | `date: 2026-04-22` |
| **updated** | ✅ | 最近一次修改时间，格式 `YYYY-MM-DD` | `updated: 2026-04-22` |
| **source_platform** | ✅ | 根据域名判断 | `source_platform: weixin` |
| **original_url** | ✅ | 原文完整链接 | `original_url: https://mp.weixin.qq.com/s/xxx` |
| **recorded_at** | ✅ | 创建时间，精确到秒 | `recorded_at: 2026-04-22 14:30:00` |
| **summary** | ✅ | 文章类型 + 核心主题的一句话描述，不超过150字，不需要概括全文观点 | `summary: 虎嗅对DeepSeek V4的技术解读，聚焦工程效率改进与单位智能成本下降，不追逐榜单排名。` |
| **keywords** | ✅ | 词频统计 + 标题优先，取 3~5 个 | `keywords: [RF-GPT, 无线信号, 频谱感知, AI识别]` |
| **tags** | ✅ | 主题标签列表 | `tags: [AI, 无线通信, 机器学习]` |

**Summary 避坑指南**：
- ❌ 不要写成"本文共5部分，分别介绍……"（这是目录不是摘要）
- ❌ 不要直接复制文章开头段落
- ✅ 要写"这是一篇[类型]，关于[主题]，适合[场景]"
- 注意：正文是原文照录，summary 只是 frontmatter 里的快速描述字段，两者职责不同

---

## 变更记录格式说明

每条变更记录包含：
- **变更时间**：精确到分钟（YYYY-MM-DD HH:mm）
- **新增内容**：原始正文照录，便于追溯
- **内容对比摘要**：用自然语言描述本次变更内容

这样做的目的：用户可以随时追溯任意历史版本，知道原文是什么时间因为什么原因发生了什么变化。

---

## 定期巡检（规范达标检查 + AI重组检测）

每次批量抓取或定期整理时，建议运行一次规范达标检查，确保所有剪报符合排版和摘要规范。

**运行方式**：将以下 Python 脚本保存为 `scripts/clip_audit.py`，定期执行：

```python
"""剪报规范达标检查脚本"""
"""剪报规范达标检查脚本"""

CLIP_DIR = "/path/to/your/clip/directory"  # 请替换为实际目录

# AI 重组正文的铁证标记——搜索到即需要修复
AI_SECTION_MARKERS = [
    "## 帖子正文",       # 类型A：即刻帖子 AI 加的章节
    "## 热门评论",        # 类型A：评论混入正文
    "## 评论精选",        # 类型A：评论混入正文
    "## 正文",            # AI 自行添加的章节标记
    "## 基本信息",        # 类型B：AI 模板章节
    "## 一句话概括",      # 类型B：AI 模板章节
    "## 相关技能标签",    # 类型B：AI 模板章节
]

files = sorted([f for f in os.listdir(CLIP_DIR) if f.endswith('.md') and f != 'README.md'])
issues = []
ok = 0

for f in files:
    path = os.path.join(CLIP_DIR, f)
    with open(path, 'r') as fh:
        content = fh.read()

    lines = content.split('\n')
    in_frontmatter = False
    has_frontmatter_end = False
    summary_line = None
    has_html_garbage = False
    content_lines = 0

    for line in lines:
        if line.strip() == '---':
            if not has_frontmatter_end:
                has_frontmatter_end = True
                in_frontmatter = True
            else:
                in_frontmatter = False
                continue
        if in_frontmatter:
            if line.startswith('summary:'):
                summary_line = line
        else:
            content_lines += 1
            if any(x in line for x in ['var ', 'window.', '.weui-', '<!--', 'function ', '=> {', 'try {', '} catch']):
                has_html_garbage = True
            for marker in AI_SECTION_MARKERS:
                if marker in line:
                    issues.append(f"【{f}】含AI重组标记：{marker}")
                    break

    issue = ""
    clean_summary = summary_line.replace('summary:', '').strip() if summary_line else ""
    if not summary_line:
        issue += "无summary; "
    elif len(clean_summary) > 150:
        issue += f"summary过长({len(clean_summary)}字); "

    if has_html_garbage:
        issue += "HTML/JS垃圾; "

    if issue:
        issues.append(f"【{f}】{issue}")
    else:
        ok += 1

print(f"✅ 正常: {ok} 篇")
print(f"❌ 问题: {len(issues)} 篇")
for i in issues:
    print(i)
```

**达标标准**（触发修复的阈值）：

| 检查项 | 触发修复条件 |
|--------|------------|
| AI 重组标记 | 存在 `## 帖子正文`、`## 热门评论`、`## 评论精选`、`## 正文`、`## 基本信息`、`## 一句话概括`、`## 相关技能标签` → 按下方修复手册处理 |
| summary 字段 | 缺失 → 新增；长度 > 150字 → 压缩至 50~100 字 |
| HTML/JS 垃圾 | 存在 `var `、`window.`、`.weui-`、`<!--`、`function `、`=> {` 等 → 清除 |
| 正文截断检测 | 正文超过50行且全文无任何换行/分段标记 → 正文可能被压缩，请重新抓取验证 |
| 截断位置 | 在句子中间断开 → 移到上一段结尾或下一段开头 |

---

### AI重组标记修复手册

> ⚠️ **修复前必读：先备份，再操作！**
>
> 剪报原文是无价的历史数据，修复过程中一旦写崩就没有了。**任何修复操作前**，必须先对目标文件做完整备份：
> ```bash
cp CLIP_DIR/文件名.md \
   CLIP_DIR/.bak/文件名-YYYYMMDD-HHMMSS.md
> ```
> 备份目录 `.bak/` 在剪报目录下，保留30天自动清理。

**类型C：正文段落被压成超长一段（微信公众号常见）**

典型现象：正文超过20行但全文没有任何换行，所有段落被合并成一条长长的文字流。这是微信公众号的 HTML 结构（`<p>` / `<section>` 标签携带语义边界）在抓取时没有被保留导致的。

根因：TextExtractor 的 `handle_data` 把所有文本拼接成一行，最后 `re.sub(r'\s+', ' ', text)` 把所有换行和段落边界全部压成了空格。

修复步骤：
1. 从 `original_url` 重新抓取完整 HTML
2. 确认 `id="js_content"` 内提取到的字数（应该数千字）
3. 用正确的 TextExtractor（`<p>/<section>/<br>` 插入换行符）重新解析
4. 验证正文有自然分段后再写入

**类型A：即刻帖子混入评论（`## 帖子正文` + `## 热门评论`）**

典型模式：正文前被插入 `## 帖子正文`，文末有 `## 热门评论` 或 `## 评论精选`，后续内容是评论区。

修复步骤：
1. 删除 `## 帖子正文` 这一行（保留其下方的正文内容）
2. 在 `## 热门评论` 或 `## 评论精选` 出现的位置截断，删除该标记及之后所有内容
3. 清理文末残留的分隔线（如 `---`）

**类型B：模板化整理文（`## 基本信息`、`## 一句话概括`、`## 相关技能标签`）**

典型模式：飞书/GitHub/游戏Wiki 文章被加入了 AI 模板章节。

修复步骤：
1. 删除 `## 基本信息` 整个章节（及其内容）
2. 删除 `## 一句话概括` 整个章节
3. 删除 `## 相关技能标签` 整个章节
4. 保留原文自带的章节（如 GitHub README 的 `## Overview`、`## Key Features`）
5. 如果文章正文被显著压缩（少于原文应有长度），从 `original_url` 重新抓取验证

**正文被压缩（缺少内容）的检测**

现象：正文只有几百字，但原文应该是几千字的长文。
处理：从 `original_url` 重新抓取完整正文，覆盖写入。

---

### 平台陷阱速查

| 平台 | 正文来源 | 主要风险 |
|------|---------|---------|
| 即刻（okjike.com） | 正文 + 评论都在同一 HTML 的 script 标签 JSON 里 | 评论容易被当作正文混入；正文前可能被 AI 加 `## 帖子正文` 章节 |
| 微信公众号 | 正文在 `js_content` div 内，评论不在页面内 | 正文容易被 AI 压缩成摘要；需要用 HTMLParser 完整提取 |
| 飞书文档 | Wiki API → docx API → blocks JSON | 需要飞书应用凭证（APP_ID + APP_SECRET）；浏览器直接抓会返回 SPA 空壳；token 有时效性 |

---

## 已知限制

- **即刻平台**：移动端 `m.okjike.com` 可无需登录直接访问；网页版 `web.okjike.com` 常要求扫码登录，建议始终用移动端 URL
- **微信公众号**：内容为 SPA，依赖 JS 渲染；`urllib.request` 直接抓 HTML 是可行的（无需无头浏览器），注意服务器可能返回 529 限流；同一个文章链接，从飞书转发和从微信直接转发访问效果可能不同（飞书可能抓取失败），失败后告知用户可尝试从微信转发（若本身就在微信端对话则省略提示）
- **飞书文档**：内容为 SPA，不能用浏览器工具或 HTML 解析抓取；必须使用飞书开放 API（需要 APP_ID + APP_SECRET）；个人空间（my.feishu.cn）和租户空间（xxx.feishu.cn）的链接都支持，走同一个 wiki API
- 若页面存在多个发布/修改时间，以最先获取到的为准
