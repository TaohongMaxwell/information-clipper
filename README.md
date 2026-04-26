# Information Clipper（信息剪报）

把散落在各处的网页内容，像剪报纸条一样存到本地，再也不用依赖某个 App 的收藏夹了。

---

## 它能做什么

就是"剪报"——学生时代把错题剪下来贴到本子里的那个方法的 AI 版本。

只需要把觉得有意思的链接扔给 AI，它咔嚓一下把好东西剪下来，贴成一个结构完整的 Markdown 文件，存进本地知识库。

筛选标准就一个字 — **爽**。"这个挺有意思"就随手存，不要求每篇都系统有用，更注重趣味性和个人启发。

---

## 快速上手

```
用户：收藏一下 https://mp.weixin.qq.com/s/xxx

AI：✅ 已保存到 2026.04.26-标题.md
     摘要：...
     关键词：xxx, xxx, xxx
```

```
用户：总结剪报

AI：[输出目录级聚合统计]
```

---

## 剪报长什么样

每篇是一个完整的 Markdown 文件：

```yaml
---
title: "登味"是什么味
type: raw
maturity: draft
date: 2026-04-23
updated: 2026-04-23
source_platform: 微信公众号
original_url: https://mp.weixin.qq.com/s/abc123xyz
recorded_at: 2026-04-23 15:10:51
summary: 社会观察类文章，聚焦"登味"梗的语义演变与代际传播逻辑
keywords: [老登, 小登, 登味, 代际, 自嘲]
tags: [网络流行语, 社会观察]
---

{正文内容，原文照录，有结构有分节}

## 变更记录

- 2026-04-23 15:10:51 — 初始创建
```

---

## 增量更新

同一个链接再次被抓取时，不会替换原文，而是把新内容追加到变更记录里，随时可以追溯历史版本。

---

## 目录总结

当你想快速了解最近存了什么，直接说：

```
总结剪报 / 剪报概览 / 剪报目录 / 最近存了什么
```

AI 会扫描整个目录，聚合统计标签分布、关键词频率、平台分布、时间趋势，输出完整文件清单——目录级的聚合 digest，不是重写每篇摘要。

---

## 支持的平台

- 微信公众号
- 即刻（移动端）
- Bilibili（视频/专栏）
- 知乎
- 小红书
- GitHub
- 飞书文档
- 通用网页

---

## 在知识库中的位置

```
知识库/
├── 1.raw/                    ← 剪报 raw 层（Information Clipper 维护）
│   ├── README.md            ← 本目录说明
│   ├── YYYY.MM.DD-标题.md
│   └── ...
├── 2.wiki/                   ← 编译输出层（Wiki-Compiler 编译）
│   └── ...
└── 3.outputs/                ← 最终产出
    └── ...
```

Information Clipper 只做信息收集这一步。raw 文件可以单独用，也可以交给 Wiki-Compiler 编译成长青知识库。

---

## 技术细节（给 AI 看的）

### 工作流程

```
发送链接 → AI 识别平台 → 抓取内容 → 清洗正文 → 提取元数据 → 写入 Markdown
```

### 正文原则

- **原文照录**，只做清洗，不做理解、不做压缩、不做重组
- `##` 二级标题 = 原文本身就有的分段标记，不是 AI 自行概括的小标题
- 如果原文没有自然分段，不要强行插入 `##`

### 关键词提取

- 文本分词 → 过滤停用词 → 统计词频 → 标题优先 → 取 TOP 3~5
- 内置停用词表，无需外部依赖

### 元数据字段

| 字段 | 说明 |
|------|------|
| title | 原文标题 |
| type | 固定 `raw` |
| date | 记录日期（YYYY-MM-DD） |
| updated | 最近修改时间 |
| source_platform | 来源平台 |
| original_url | 原文链接 |
| recorded_at | 记录时间 |
| summary | 一句话描述文章是什么（不是概括观点） |
| keywords | 3~5 个关键词 |
| tags | 主题标签 |

---

🔗 **GitHub 仓库**：[TaohongMaxwell/information-clipper](https://github.com/TaohongMaxwell/information-clipper)

✍️ 派蒙 ✦ 旅行者的专属伙伴（Powered by [Hermes](https://github.com/NousResearch/hermes-agent) and [MiniMax](https://www.minimaxi.com)）· [TaohongMaxwell](https://github.com/TaohongMaxwell)
