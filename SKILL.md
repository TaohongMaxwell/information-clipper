---
name: information-clipper
description: 信息剪报 Skill — 接收链接，自动抓取网页内容并整理为标准 Markdown，存入本地剪报库。支持微信公众号、即刻等平台，Bilibili/知乎/小红书待测试，生成含元数据的结构化文档，适合作为知识管理或个人阅读存档的工作流。
author: TaohongMaxwell
repository: https://github.com/TaohongMaxwell/information-clipper
version: 1.0.3-27.04.27
---

# 信息剪报 Skill

## 入口

用户发送链接并要求收藏时，自动触发本 Skill。
用户要求更新/刷新已有剪报时，自动触发增量更新流程。
用户说"总结剪报 / 剪报概览 / 剪报目录 / 最近存了什么"时，触发目录总结流程。

> **⚠️ clip_summary.py 只是一个数据扫描工具，不是分析工具。**
> 它负责扫目录、拿标签、抓 metadata、跑统计——这些只是原材料。
> 最终成文必须由派蒙用 AI 能力自己写，而不是把脚本输出直接端出来。

## CLIP_DIR

```
/volume2/AI工作区/知识库/1.raw/派蒙剪报
```

> ⚠️ 若克隆到其他机器使用，请将 `CLIP_DIR` 替换为本地实际路径。

## 核心脚本

**`scripts/clip.py`** 是本 Skill 的核心执行引擎，负责所有标准化操作：

| 命令 | 作用 |
|------|------|
| `python3 scripts/clip.py scrape <url>` | 抓取内容 + 提取正文 + 质量检查，输出 JSON |
| `python3 scripts/clip.py exists <url>` | 检查 URL 是否已在剪报库中 |
| `python3 scripts/clip.py save <url>` | 快速保存流程（检查→抓取→质量检查→写文件），不做 AI 排版，适合纯手动存档 |
| `python3 scripts/clip.py format <url>` | 仅返回标准 frontmatter + raw_text，**不写文件**。AI assisted workflow 的两阶段写文件Stage 1 用此命令 |

> ⚠️ **所有提取逻辑都在 clip.py 里**，SKILL.md 只描述工作流程和判断规则。
> 遇到提取失败时，修改 clip.py 中的对应平台函数，而不是在 SKILL.md 里临时写脚本。

## 剪报原则（最重要）

- **正文 = 原文照录**，只做清洗，不做理解、不做压缩、不做重组
- **标题层级由第六步 AI 排版统一处理**：原文的 h2/h3/h4 → `##`/`###`，原文无分节时由 AI 识别主题段落再插入
- 如果原文没有自然分段，不要强行插入 `##`
- Summary 是 frontmatter 里的元数据摘要，与正文无关

## 筛选标准

就一个字 — **爽**。不只追求有用，不只追求体系，"这个挺有意思"就随手存一下。

## 工作流程

执行时不用逐条报幕，说清楚大致状态即可。例如："抓取中，稍等"而不是"第一步，正在执行抓取命令"。

### 第一步：接收链接，判断是否已存在

> **执行约束**：第四步的派蒙分析必须暂存（不输出到对话），直到第九步通知用户时才一并附上。分析不允许拆分成中间步骤提前发出。

> **唯一入口原则**：`clip.py save <url>` 适合纯手动快速存档（scrape → 直接写文件，不做 AI 排版）。AI assisted workflow（做分析 + 排版 + 补 frontmatter）用 `exists` → `scrape` → `format` → 合并写文件的路径。两阶段写文件必须用 `format` 返回的 frontmatter 为基础，不允许先 scrape 再手动拼接。

用 clip.py 检查：

```bash
python3 scripts/clip.py exists <url>
```

- **已存在** → 告知用户，跳过
- **不存在** → 继续

### 第二步：抓取 + 质量检查

```bash
python3 scripts/clip.py scrape <url>
```

clip.py 会自动：
1. 识别平台（微信公众号 / 即刻 / GitHub / 飞书 / Bilibili / 通用网页）
2. 调用对应提取函数获取正文和元数据
3. 执行质量检查，返回 issues 列表
4. 输出结构化 JSON

**质量检查项**（有问题会列在 issues 里）：

- 正文少于 500 字 → 可能提取失败
- 标题为空 / 为 "Unknown" → 元数据抓取失败
- HTML/JS 垃圾残留（`<script>`、class=、style=、window.）→ 清洗不彻底
- 截断标记后还有超过 100 字内容 → 截断不彻底
- 正文超过 10 万字 → 可能混入了垃圾

### 第三步：判断是否继续

读取 JSON 中的 `passed` 字段：
- `true`（issues 为空）→ 继续第四步
- `false`（有 issues）→ **不要写文件**，把 issues 报告给用户，询问如何处理

> **两阶段写文件规则**：第五步补充 frontmatter（summary/tags），第六步做 AI 排版，第七步才真正落盘。分析内容始终不写入文件。

### 第四步：派蒙分析（暂存，不输出到此步）

分析在后台进行，内容暂存备用，**不写入文件，也不在此步骤告知用户**。此步只产生一段分析文本，延迟到第九步随通知一并发出。

分析维度（每篇都做）：

1. **核心论点**：一句话说出文章在讲什么
2. **论证结构**（可选，如果层次清晰再写）
3. **金句**：原文原话，不改写
4. **派蒙点评**：什么类型文章、对旅行者的价值、可能的局限

> **约束**：分析内容仅输出到对话，不写入 Markdown 文件。正文永远是原文照录。

### 第五步：补充 frontmatter

`clip.py scrape` 返回的数据中，以下字段由派蒙根据分析结果手动补全（直接在 clip.py frontmatter 模板上修改）：

```yaml
summary: （派蒙补充：一句说明文章类型和主题，不超过150字）
tags: [（派蒙添加主题标签）]
author: （微信公众号文章若提取失败，需从正文末尾手动补录，如"撰文 | 应超"）
official_account: （若提取失败，从正文末尾补录公众号名称）
```

**常见作者格式（微信正文末尾）**：
- `撰文 | 张三` → author: 张三
- `作者：张三` → author: 张三
- `文｜李四` → author: 李四

> **注意**：frontmatter 的标准格式由 clip.py 的 `build_frontmatter` 决定，这里只补充 summary / tags / author / official_account 四个字段，其他字段保持原样。

### 第六步：AI 排版（标题层级化）

在写文件之前，用 LLM 对正文进行标题层级排版。

**标题层级对应规则**：

| 原文层级 | Markdown | 说明 |
|---------|----------|------|
| 文章大标题（如微信文章标题） | `#` 一级 | 通常对应 frontmatter 中的 title |
| 章节标题（如 "从闲聊到助手"） | `##` 二级 | 原文本身就有的节标题 |
| 子节标题 | `###` 三级 | 原文有的子节 |
| 更细的子节 | `####` 四级 | 以此类推 |

**原文无分节时的处理**：

- 即刻帖子、知乎回答等天然没有章节结构的原文，用 AI 识别**自然段落的主题**，在合适位置插入 `##` 二级标题
- 生成的小标题必须**来自原文关键词或核心概念**，不得凭空创造
- 如果原文确实很短（500 字以内）、段落主题相近，**可以保持不分节**，不要强行切分

**判断示例**：

- 微信公众号文章有 h2/h3 → 直接对应 `##` / `###`
- 即刻帖子无分节 → AI 识别2-4个主题段落，插入 `##` 小标题
- 1000字以内的短文 → 可保持无二级标题

### 第七步：写入文件

**分两阶段执行，不允许手动拼接 frontmatter。**

**阶段一**：调用 `clip.py format` 获取标准 frontmatter（此命令不写文件，只返回结构化数据）：

```bash
python3 scripts/clip.py format <url>
```

**阶段二**：将阶段一拿到的 frontmatter（已补充 summary/tags/author），与第六步 AI 排版后的正文，合并为完整 Markdown 内容，一次性写入文件。

> **不允许**先 scrape 再手动写 frontmatter。所有文件必须由 clip.py 生成的标准 frontmatter 为基础。

**文件命名规则**：

- 格式：`CLIP_DIR/YYYY.MM.DD-标题.md`（点号分隔年月，不是横杠）
- **标题优先顺序**：
  1. 分析阶段生成的短标题（15~25 字），适合大多数场景
  2. 原标题前 50 字（仅当原标题本身就很短、且没有生成短标题时）
- 若已存在则追加 `-1`、`-2` 序号

> ⚠️ 日期格式：文件名用点号（`2026.04.26`），frontmatter 用横杠（`2026-04-26`）

### 第八步：排版检查（写文件后复核）

对写好的 Markdown 文件做一次排版层面的质量复核。

**检查内容**：

1. **标题层级是否合理**：文章是否只有 `#` 标题但正文没有任何 `##`，或层级跳跃（如 `#` 直接跳到 `####`）
2. **段落是否残留干扰内容**：如微信"展开全文"按钮文字、平台引导性语句、无意义的符号串
3. **HTML/JS 残留**：肉眼可见的 `<xxx>` 标签、class=、style= 等清洗漏网之鱼
4. **正文是否完整**：对比 scrap JSON 的 raw_text 字符数，大幅偏少可能有内容丢失

**操作方式**：读取已写入的 Markdown 文件，快速扫一遍。发现问题直接 patch 修复，不要返回给用户。

**通过标准**：无明显排版问题、无干扰内容残留、标题层级清晰。细节瑕疵（如个别字词重复）可放过。

### 第九步：通知用户

告知已保存的文件路径，**必须附上第四步的分析结果**（格式照搬，不省略）。

**全新创建**：告知文件名和路径，必须附上分析结果。

**增量更新**：告知更新的内容摘要（"检测到N处变更，已追加到变更记录"）。

### 第十步：增量更新（文件已存在时触发）

当同一 URL 再次被抓取时，按以下规则处理：

**原则：追加或插入，不替换原文，保留完整变更历史。**

1. **抓取新内容**，与原文对比，找出差异（新增段落、修改、评论更新等）
2. **读取现有文件**，找到 `## 变更记录` 区域
3. **在 `## 变更记录` 下方插入本次变更块**
4. **更新 frontmatter 中的 `updated` 字段**为当前时间
5. **绝对不修改、覆盖或删除任何已有的正文内容**

---

## 文件命名规范

- 格式：`YYYY.MM.DD-标题.md`（**点号分隔年月，不是横杠**）
- 日期：记录日期，非原文发布日期
- 标题：优先用分析阶段生成的短标题（15~25 字）；原标题前 50 字仅作为兜底
- 若已存在则追加 `-1`、`-2` 序号

## 变更记录规范（clip.py 不处理，手动维护）

当同一 URL 再次被抓取时，**追加不替换**：

1. 读取现有文件，找到 `## 变更记录` 区域
2. 在其下方插入变更块（格式见下方）
3. 更新 frontmatter 的 `updated` 字段

```markdown
## 变更记录

### {本次变更时间，YYYY-MM-DD HH:mm}

#### 新增内容
{新增的正文内容，原文照录}

#### 内容对比摘要
{简要说明变更内容}
```

---

## 批量元数据重建

当需要全量重建或批量修复剪报库中所有文件的 frontmatter 时（author/official_account/字段标准化），按以下流程执行：

### 第一步：摸底

```python
import os, re
kb = "/volume2/AI工作区/知识库/1.raw/派蒙剪报"
files = sorted([f for f in os.listdir(kb) if f.endswith('.md') and f != 'README.md'])

# 按平台统计、找缺 author/official_account 的文件
for fname in files:
    path = os.path.join(kb, fname)
    with open(path, 'r', errors='ignore') as f:
        content = f.read()
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m: continue
    fm = {}
    for line in m.group(1).split('\n'):
        if ':' in line:
            k, _, v = line.partition(':')
            fm[k.strip()] = v.strip()
    sp = fm.get('source_platform', '')
    # ... 统计逻辑
```

### 第二步：按平台批量处理

| 平台 | 自动化方式 |
|------|-----------|
| GitHub | 从 URL 直接提取 `github.com/NAME/repo` |
| arXiv | 调用 `http://export.arxiv.org/api/query?id_list=` API |
| 微信公众号 | 并行跑 `clip.py format` 获取 frontmatter，再从正文末尾正则提取 author/official_account |
| 即刻 | screenName 从 clip.py format 获取（注意：即刻 author 均为屏幕显示名，非实名） |
| 飞书 | author 暂时只能标 `"飞书文档"`（open_id 无法转姓名） |

### 第三步：逐一补全公众号 author

微信公众号 author 从正文末尾 blockquote 区域提取（见上方"作者格式"）。若正文无作者署名（有些转载文章只有公众号名、无作者），标注 `author: ""`。

### 第四步：重建写文件

统一 frontmatter 字段顺序：
```yaml
title: X
date: YYYY-MM-DD
updated: YYYY-MM-DD
source_platform: weixin|jike|github|arxiv|feishu|web|genshin
author: 作者名
official_account: 公众号名|平台名
original_url: https://...
recorded_at: YYYY-MM-DD HH:MM:SS
summary: 一句摘要
keywords: [标签]
tags: [标签]
```

### 第五步：质量验证

写完一批后，扫描所有文件确认：
- 无 `author: ???` 或 `author: ""` 在公众号文章（除非确实无作者）
- 所有文件有 `source_platform`
- 字段顺序一致

---

## 目录总结（剪报概览 / 全局内容分析）

### 核心理念

**脚本提供数据，AI 负责感受和表达。**

`clip_summary.py` 扫出来的标签分布、时间密度、平台比例，只是原材料——不是结论。派蒙要像平时跟在旅行者旁边看他刷手机一样，读完这堆数据之后，有感而发，写出一段真正有人味儿的东西。

### 常见错误：拿着原材料直接端上桌

❌ **错误示范**（2026.04.27 实录反面教材）：

```
=== 标签 TOP20 ===
  AI: 20
  Agent: 11
  职场: 7
  ...

=== 平台分布 ===
  jike: 33
  weixin: 24
  ...

### AI 技术/工具（~28篇）
- Agent学习资料包：Anthropic官方方法论...
- Claude Code记忆模块设计分析...
```

这看起来像数据报表，有数字有分类——但没有人的感受，没有派蒙的声音。这不是分析，这是把 Excel 表格贴了上来。

❌ **另一个错误**：把脚本的统计数字包装成"分析"，在每个分类前面加个 emoji，然后在开头结尾写两句"读完了"。

### 正确姿势：派蒙在替旅行者说话

✅ **正确示范**（2026.04.26 风格参考）：

> **旅行者这十天存了71篇——Jike 33篇，微信24篇。**
>
> **说实话，这不像一个"知识管理系统"，更像是一个在信息洪流里随手捞东西的人。**
>
> **有意思的是，旅行者在存 AI 的同时，也在存 AI 的副作用。**
> 一边在研究 token-maxxing，一边在存"幽灵劳动""头戴摄像头蒸馏家务"。
> 这不是矛盾，这是——我知道我在浪潮里，但我想看清楚浪长什么样。
>
> **简单说。**
> 这是一个技术圈打工人，在AI浪潮里一边往前游一边抬头看天。
> 存的东西没有KPI，爽就存，但存着存着就发现，原来自己最焦虑的和最想解决的，其实是同一件事。

核心区别：
- **不是**派蒙在汇报"你存了什么"
- **是**派蒙在说"我读完之后的感受"
- 数字只是辅助，不是主体
- 要有观点，有感受，有派蒙的视角

### 执行流程

1. **运行脚本**：`clip_summary.py` 或 execute_code 扫描目录，拿到底层数据（标签频率、平台分布、时间密度）
2. **读数据、感受数据**：不是统计它们，是**感受它们**——这些数字背后的人在关心什么？
3. **确定叙事主线**：这堆内容里，最核心的脉络是什么？有没有什么有意思的反差或呼应？
4. **动笔写**：带着派蒙的口吻，像跟旅行者聊天一样写出来
   - 可以有"说实话"
   - 可以有"有意思的是"
   - 可以有派蒙自己的观察（"这不是……这是……"）
   - 结尾可以用一句点睛的话收住
5. **不发中间稿**：脚本跑完直接写最终稿，不要先输出一个数据版再重写

### 约束

1. **不把脚本输出直接当作分析结果输出**。脚本是原材料，不是成品。
2. **不填表格做分析**：不要输出"标签-篇数-说明"这种表格形式的分析，那不是派蒙会说的话。
3. **不机械分类**：不是把文章按标签分组然后每组列个清单——那是文件系统的活，不是分析的活。
4. **有感而发才写**：读完如果没有感受，就不要硬写。先让子弹飞一会儿，想清楚"这篇文章整体说明了什么"再动笔。
5. **最终稿只出一遍**：script 跑完直接写，写完直接发，不出中间数据版。

---

## clip.py 支持的平台

| 平台 | 提取方式 | 备注 |
|------|---------|------|
| `mp.weixin.qq.com` | HTMLParser + js_content | 自动识别 h2/h3/h4 标题 |
| `github.com` | GitHub API + raw README | README 是 HTML 格式，必须过 HTMLParser 清洗 |
| `jike.com` / `okjike.com` | JSON in script tag | 自动保留评论区 |
| `feishu.cn` / `larksuite.com` | 飞书开放 API | 需要 FEISHU_APP_ID / FEISHU_APP_SECRET |
| `bilibili.com` / `b23.tv` | HTMLParser | 支持视频/专栏，标题含B站水印需清洗 |
| 其他域名 | 通用 HTMLParser | 优先提取 `<article>` / `<main>` |

## 平台提取注意事项（实战教训）

### 微信公众号
- **author 字段**：文章作者姓名，从正文末尾扫描以下模式提取，提取失败则为空字符串。实战中遇到过的格式包括：
  - `文 丨 司雯雯`（空格+丨分隔）
  - `文｜李四` / `文 | 李四`（竖线/双竖线）
  - `撰文 | 应超`
  - `作者：张三` / `作者：XXX`
  - `撰文/播音：XXX`
  - `>/ 作者：卡兹克、可达、闯子`（微信 blockquote 格式，正文末尾 `>` 开头的引用行）
  - `作者：OPC同行社 | 发布于 2026-04-24`（机构号格式，需截取 `|` 前的内容）
  - `晚点专栏作者孟醒：五源资本合伙人`（需截取 `：` 和 `：` 之间的内容）
  - `作者：宋思杭` / `作者｜虎嗅科技组`（标准格式）
  - 西风 发自 凹非寺（这种格式需结合下一行的 `量子位 | 公众号 QbitAI` 联合判断）
  - 若正文中未见上述格式，但文章明显有作者署名（如独立署名风格），可从正文第一段（如 `> 西风 发自 凹非寺`）或最后一段推断，并标注 `author: （推断）`
- **official_account 字段**：公众号名称，从正文末尾扫描以下模式提取：
  - `量子位 | 公众号 QbitAI` → official_account: 量子位
  - `本文首发于《XXX》` / `来源：《XXX》` / `转载自《XXX》`
  - `公众号：XXX`
  若正文末尾未见公众号标识，但正文开头有 `>/ {author} 发自 凹非寺` 格式，通常可结合上一行的 `平台 | 公众号 {name}` 格式推断
- **正文末尾追加提示行**：`>/ 作者：{author}｜公众号：{official_account}`，供第四步分析时直接参考（若两者皆为空则不追加）
- **正文开头 `>` 残留**：微信部分段落含 `style="visibility:hidden"` 隐藏内容，HTMLParser 会把其中的 `>` 分隔符当正文提取。`clean_text()` 里已处理（`re.sub(r"\n>\n", "\n")` 和 `re.sub(r"^>\n", "", text)`），无需在提取逻辑里额外处理
- **`pub_date`**：微信公众号 `var ct` 时间戳有时为 0，回退到当天日期
- **登录墙检测**：微信文章若需要登录/关注才能阅读，返回的是小于 50KB 的空壳 HTML（无 `js_content` 正文区域），正常文章返回 3MB+ 完整页面。检测到空壳页面时应判断为"登录墙拦截"，告知用户无法自动抓取
- **URL 可能变旧/归档**：同一微信文章可能存在多个历史 URL（如 `b_X5vzW7y85DImNbGJjdUw` vs `0yTV4K_2iJvqGl_6n8lV0Q`），旧链接可能已归档为登录墙，新链接返回完整内容。若存档中已有完整内容（12KB+），且旧 URL 返回空壳（<50KB），说明旧链接已失效，应更新 `original_url` 到新链接
- **truncated_by 不等于截断**：微信平台 UI 元素（如 `"预览时标签不可点"`）会出现在 `truncated_by` 字段里，但这不代表文章被截断——它只是页面底部的水印提示。判断文章是否完整的可靠依据是：`raw_text` 字符数是否与页面大小吻合、结尾是否有自然收束（如「他今年二十出头」这样的完整句子）。**不要仅凭 `truncated_by` 有值就判定截断。**
- **`og:article:author` 元字段不可信**：微信页面的 `og:article:author` meta 标签有时包含平台前缀或乱码（如 APPSO 文章变成了 `"发现明日产品的"`），不能用于 author 提取。author 仍须从正文末尾 patterns 提取。

### 即刻
- **author 字段**：`screenName` = 显示名（如"风小海"），`username` = UUID，`bio` = 个人简介兜底。**不要用 `nickname`**，该字段不存在于数据结构中。检测顺序：`screenName` → `nickname`（不存在）→ `username` → `bio`（兜底）
- **author_id 字段**：`user.username` = 用户唯一ID（如 `ewoidSI6ICI2NzMwYTIyNWRjZWVkMDBhN2Q3N2U0MDEi`），与 `author` 字段并列输出
- **支持路径**：`m.okjike.com/originalPosts/`（推荐）；评论仅取顶层

### GitHub
- **README 是 HTML**：GitHub 页面上的 README 是 HTML 格式，不是纯 Markdown。必须过一遍 `通用TextExtractor` 清洗，不能直接用 raw 文本，否则 `<div>`、`<a href>` 等标签会残留在正文中
- **stars / forks**：clip.py 已从 GitHub API 提取这两个字段，保存时 fronts matter 应补充 `stars` 和 `forks`（已有旧文件缺少这两个字段属正常）

### 飞书（Wiki）
- **author**：飞书 Wiki API 返回的 `owner` 是 `open_id`（如 `ou_xxx`），没有公开 API 能将其转换为用户姓名（需要 contact API 额外权限）。`author: "飞书文档"` 是当前能取到的最准确值，属平台限制而非 bug
- **pub_date**：使用 `obj_create_time`（或 `node_create_time`），是 **Wiki 创建时间**，不是派蒙保存时间。注意这是 **Unix 时间戳字符串**（如 `"1776843037"`），需要 `int()` 转换后再 `fromtimestamp()`，且需指定北京时间时区（`datetime.timezone(datetime.timedelta(hours=8))`）转换
- **所需凭据**：`FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`（已配置在环境变量中，clip.py 自动读取）

---

## 目录结构

```
CLIP_DIR/
├── README.md
├── scripts/
│   ├── clip.py              ← 核心执行引擎（本 Skill 的程序化部分）
│   ├── clip_audit.py        ← 剪报库批量审计（检查已存文件质量）
│   ├── clip_summary.py     ← 目录扫描工具（提供metadata统计，不是分析工具）
└── YYYY.MM.DD-标题.md       ← 注意：点是日期分隔符，不是横杠
```

> ⚠️ 若克隆到其他机器使用，请将 `CLIP_DIR` 替换为本地实际路径。

**首次运行须知**：每次在新环境首次执行本 Skill 前，需检查 `CLIP_DIR/README.md` 是否存在。若不存在，请参考以下模板创建目录级 README：

```markdown
# 信息剪报（Information Clipper）

把散落在各处的网页内容，像剪报纸条一样存到本地，再也不用依赖某个 App 的收藏夹了。

## 这是什么

"剪报"的 AI 版本：不用自己动手整理，只需要把觉得有意思的链接扔给 AI，它会咔嚓一下把好东西剪下来，贴成一个结构完整的 Markdown 文件，存进本地知识库。

筛选标准就一个字 — **爽**。"这个挺有意思"就随手存，不要求每篇都系统有用，更注重趣味性和个人启发。

## Skill 说明

详细信息请参考 `../skills/productivity/information-clipper/SKILL.md`
```
