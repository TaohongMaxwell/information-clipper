---
name: information-clipper
description: 信息剪报 Skill — 接收链接，自动抓取网页内容并整理为标准 Markdown，存入本地剪报库。支持微信公众号、即刻、Bilibili、知乎等多个平台，生成含元数据的结构化文档，适合作为知识管理或个人阅读存档的工作流。
author: TaohongMaxwell
repository: https://github.com/TaohongMaxwell/information-clipper
---

# 信息剪报 Skill

## CLIP_DIR

```
/volume2/AI工作区/知识库/1.raw/派蒙剪报
```

> ⚠️ 若克隆到其他机器使用，请将 `CLIP_DIR` 替换为本地实际路径。

## 功能

接收一个或多个链接，自动抓取页面内容，提取元数据，生成标准 Markdown 存入剪报目录。

**剪报原则（最重要）**：
- **正文 = 原文照录**，只做清洗，不做理解、不做压缩、不做重组
- `##` 二级标题 = 原文本身就有的分段标记（HTML `<h2>/<h3>/<h4>` 标签），由抓取代码自动识别转换；**不是 AI 自行概括的小标题**
- 如果原文没有自然分段，不要强行插入 `##`
- Summary 是 frontmatter 里的元数据摘要，与正文无关

**质量标准**：
- 正文必须是原文的忠实副本，清洗掉干扰内容即可
- HTML 注释、JS 变量、CSS 类名等垃圾内容必须清除
- 正文在有意义的位置截断，不在句子中间断开

**筛选标准**：就一个字 — **爽**。不只追求有用，不只追求体系，"这个挺有意思"就随手存一下。

## 入口

用户发送链接并要求收藏时，自动触发本 Skill。
用户要求更新/刷新已有剪报时，自动触发增量更新流程。

## 文件命名规范

- 格式：`YYYY.MM.DD-标题.md`（**注意是点号分隔年月日，不是横杠**）
- 日期：记录日期，非原文发布日期；**文件名中的日期自动以点号分隔**，与 frontmatter 的 `YYYY-MM-DD`（横杠）区分
- 标题：取自原标题的前 **50 字**（避免重要信息被截断），若已存在则追加 `-1`、`-2` 序号

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

- **若不存在** → 走全新创建流程（第三步~第九步）
- **若已存在** → 走增量更新流程（第八步）

### 第三步：抓取页面内容（全新创建）

#### GitHub

- 尝试 GitHub API 获取仓库/文件元信息（创建时间、更新时间、描述）
- README 内容通过 `https://raw.githubusercontent.com/` 获取

#### 即刻（m.okjike.com）

即客帖是 SPA，所有数据以 JSON 形式嵌在 `<script>` 标签里。步骤：
1. 用 `urllib.request` 抓取页面（`browser_navigate` 超时严重，不推荐）
2. 用 `re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)` 提取所有 script
3. 遍历找包含 `'props\\\":\\\\u4e3bpageProps\\\\u4e0bpost'` 且 `len(s) > 10000` 的 script
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
   - **评论标题判断逻辑**：
     - 如果正文里**没有** `## 评论区`，则用 `## 评论区` 作为评论区标题
     - 如果正文里**已有** `## 评论区`，则用 `## 楼中评论` 作为评论区标题（避免冲突）
   - 每条评论格式：`【昵称】：内容`，多条按出现顺序排列
   - 如果有评论回复嵌套，只保留顶层评论（`c['replyToUser']` 为空则保留）

#### 微信公众号（mp.weixin.qq.com）

同样是 SPA，内容嵌在 JS 里。步骤：
1. 用 `urllib.request` 抓取（User-Agent 设为 iPhone Safari 可绕过部分限制）
2. 从 HTML 中提取元数据：
   - 标题：`re.search(r'og:title["\s]*content=["\']([^"\']+)["\']', content, re.I)`
   - 作者：`re.search(r'var author = "([^"]*)"', content)`
   - 时间戳：`re.search(r'var ct = "(\d+)"', content)` → `int(ts)` 转 Unix 时间戳
3. **正文提取必须用 HTMLParser**，不能依赖 regex 标签内文本法（会漏掉 visibility:hidden 的内容）
4. **微信公众号文章使用 `<h2>`、`<h3>`、`<h4>` 作为小节标题，必须在 HTMLParser 中识别并转换为 Markdown `##` 标题**：
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
           elif tag in ('br', 'p', 'section', 'div'):
               if self.current_skip == 0:
                   self.texts.append('\n')
           elif tag in ('h2', 'h3', 'h4'):
               # 识别微信文章小节标题，转为 ## Markdown 标题
               if self.current_skip == 0:
                   self.texts.append('\n\n## ')

       def handle_endtag(self, tag):
           if tag in self.skip_tags:
               self.current_skip = max(0, self.current_skip - 1)
           elif tag in ('p', 'section', 'div'):
               if self.current_skip == 0:
                   self.texts.append('\n')
           elif tag in ('h2', 'h3', 'h4'):
               if self.current_skip == 0:
                   self.texts.append('\n')

       def handle_data(self, data):
           if self.current_skip == 0:
               text = data.strip()
               if text:
                   self.texts.append(text + ' ')
   ```
5. **⚠️ 重要：不要用 `re.sub(r'\s+', ' ', text)` 合并所有空格！** 正确做法：
   - HTMLParser 在 `<p>/<section>/<div>` 时已插入 `\n`，在 `<h2-h4>` 时已插入 `\n\n## `
   - 全文拼接后只需：`text = re.sub(r' +\n', '\n', text)`（去掉段尾多余空格）
   - 再用：`text = re.sub(r'\n{3,}', '\n\n', text)`（压缩连续空行）
   - **禁止全局空格合并**（会把段落边界压掉）
6. **部分公众号文章内容不在 js_content 内**（如三联生活实验室）。判断方法：先按 js_content 截取，如果提取到的正文少于 2000 字，立即 fallback 到 `id="img-content"` 区域重新提取
7. **截断范围**：js_content 开始位置到 `js_pc_qr_code` 或 `js_cp_tool` 之前
8. **正文清洗**：
   - 清除 HTML 实体：`re.sub(r'&\w+;', '', text)`
   - 清理开头无用元数据（作者行、编辑行）
   - **截断**：在文末找到 `预览时标签不可点`、`未经授权`、`值班主编`、`排版` 等标记之一，在其位置截断
   - 保留文章中已有的自然段落结构
9. **微信频率限制**：同一 IP 短时间内多次请求会被拦截（空白页面或 403）。失败后等 5~10 秒再重试，连续 3 次失败才放弃

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
wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token=***"
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
```

**Step 5 — 获取所有 blocks（正文内容）**：
```python
blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{obj_token}/blocks"
req = urllib.request.Request(blocks_url)
req.add_header('Authorization', f'Bearer {token}')
resp = urllib.request.urlopen(req, timeout=15)
result = json.loads(resp.read().decode())
items = result['data']['items']
```

**Step 6 — 解析 blocks 提取文本**：
```python
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
- 飞书 wiki 有两种链接格式，都走同一个 wiki API
- `source_platform` 填写 `feishu`
- 飞书文档通常结构清晰（多级标题、列表），保留原文层级结构

#### Bilibili（bilibili.com / b23.tv）

> ⚠️ 尚未测试，失败时自行尝试其他方案。

**视频**：
1. 用 `urllib.request` 抓取页面
2. 标题在 `<title>` 或 `__playinfo__` / `__INITIAL_STATE__` JSON 里
3. 简介在页面 `<meta name="description">` 或视频信息 JSON 里
4. 发布时间用 `<meta property="article:published_time">`

**专栏**：
1. 用 `urllib.request` 抓取页面
2. 专栏正文在 `<div class="article-content">` 里，用通用 HTMLParser 提取
3. 标题在 `<h1 class="title">` 里

#### 知乎（zhihu.com）

> ⚠️ 尚未测试，失败时自行尝试其他方案。

**文章/回答**：
1. 用 `urllib.request` 抓取页面（知乎对爬虫有限流，失败后等几秒再试）
2. 正文在 `<div class="Post-RichText">` 或 `<div class="RichText">` 里，用通用 HTMLParser 提取
3. 标题在 `<title>` 或 `<h1 class="Post-Title">` 里
4. 发布时间用 `<meta property="article:published_time">`
5. ⚠️ 知乎回答需要登录才能完整获取，未登录时可能只拿到摘要，失败时降级为「仅链接+标题」记录

#### 小红书（xiaohongshu.com）

> ⚠️ 尚未测试，失败时自行尝试其他方案。

**笔记**：
1. 用 `urllib.request` 抓取页面（PC端可能要求登录，优先尝试）
2. 正文在 `<div class="note-content">` 或 `window.__INITIAL_SSR_STATE__` JSON 里
3. 标题在 `<title>` 或 `<h1 class="title">` 里
4. 图片描述/标签可作为 keywords 的补充来源
5. ⚠️ 小红书对未登录访问限制较严，失败时降级为「仅链接+标题」记录

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

### 第六步半：分析（必做，输出给用户，不写入文件）

**原则**：分析是给用户的阅读辅助，**不写入 Markdown 文件**，文件里只有原文。

**口语化要求**：
- 像派蒙在跟旅行者聊天，不是写报告
- 控制字数，总长度一般不超过 200 字
- 语气柔和一点，可以说"感觉"、"好像"、"可能"；少用"绝对"、"必须"、"毫无疑问"
- 如果拿不准，可以跟旅行者讨论，不强求结论

**分析维度**（每篇都做，不跳过）：

1. **核心论点**：一句话说出文章在讲什么
2. **论证结构**（可选，如果文章层次清晰再写）：
   - 文章分几层？每层讲什么？
   - 用原文自己的关键词串起来，不要自己发明
3. **金句**：原文原话，不改写
4. **派蒙点评**（口语化，轻量级）：
   - 这篇大概是什么类型？（比如"个人经验分享"、"技术科普"、"新闻报道"……）
   - 对旅行者来说，有什么值得注意的地方？
   - 有什么局限性或者可能值得讨论的点？

**格式要求**（口语化版）：
```
## 文章分析

**标题**：...

**核心论点**：...

**论证结构**（可选）：...
- ...

**金句**：
> 「原文原话」

**派蒙点评**：...（控制在 200 字以内，语气自然，像聊天）
```

**⚠️ 注意**：分析是临时输出给用户看的对话内容，**不追加到 Markdown 正文里**。正文永远是原文照录。

### 第七步：写入 Markdown（全新创建）

**文件路径**：`CLIP_DIR/{文件名}.md`

**文件名格式**：`YYYY.MM.DD-标题.md`（**点号分隔年月日，不是横杠**）

> ⚠️ **日期格式易错点**：文件名日期用点号（如 `2026.04.26`），frontmatter date 用横杠（如 `2026-04-26`）。两者不同，写代码时不要混用。

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
summary: {一句话说明文章是什么，用于快速判断内容，不超过150字}
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
   {简要说明这次变更的内容，如"评论区新增5条评论"、"补充了架构图说明"等}
   ```
4. **更新 frontmatter 中的 `updated` 字段**为当前时间
5. **绝对不修改、覆盖或删除任何已有的正文内容**

### 第九步：通知用户

**全新创建**：
- 告知已保存的文件名和路径
- **必须附上分析结果**（第六步半的输出），格式照搬，不省略

**增量更新**：告知更新的内容摘要（"检测到N处变更，已追加到变更记录"）

**抓取失败**：告知原因，询问是否以"仅链接+标题"形式记录

---

## 目录结构

```
CLIP_DIR/                    ← 剪报 raw 层（本 Skill 维护）
├── README.md               ← 剪报目录说明（如不存在需创建）
├── YYYY.MM.DD-标题.md       ← 注意：点是分隔符，不是横杠
└── ...
```

> ⚠️ 若克隆到其他机器使用，请将 `CLIP_DIR` 替换为本地实际路径。

**首次运行须知**：每次在新环境首次执行本 Skill 前，需检查 `CLIP_DIR/README.md` 是否存在。若不存在，请参考以下模板创建目录级 README，告知可访问该目录的用户和 agents 这个文件夹的用途，并注明详细信息请参考本 Skill：

```markdown
# 剪报

这是一个本地网页内容收藏库——把散落在各处的感兴趣的内容，以结构化 Markdown 的形式存档在这里。

## 这是什么

"剪报"的 AI 版本：不用自己动手整理，只需要把觉得有意思的链接扔给 AI，它会咔嚓一下把好东西剪下来，贴成一个完整的文档。
```
