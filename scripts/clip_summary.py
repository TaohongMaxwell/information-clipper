#!/usr/bin/env python3
"""剪报目录总结脚本 — 聚合分析剪报元数据，生成目录级digest"""

import os
import re
from collections import Counter
from datetime import datetime, timedelta

# ⚠️ 请将此路径替换为实际剪报目录
CLIP_DIR = "/volume2/AI工作区/知识库/1.raw/派蒙剪报"  # TODO: 替换为你的实际路径


def parse_frontmatter(content):
    """提取 frontmatter 元数据（纯正则，不依赖yaml）"""
    fm = {}
    m = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return fm
    for line in m.group(1).split('\n'):
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
            val = val[1:-1]
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1]
            fm[key] = [x.strip().strip('"').strip("'") for x in inner.split(',')]
        else:
            fm[key] = val
    return fm


def extract_date_from_filename(fname):
    """从文件名提取日期：2026.04.26-标题.md"""
    m = re.match(r'^(\d{4}\.\d{2}\.\d{2})', fname)
    if m:
        return m.group(1).replace('.', '-')
    return None


def run_summary():
    files = sorted([
        f for f in os.listdir(CLIP_DIR)
        if f.endswith('.md') and f not in ('README.md',)
    ])

    clips = []
    for fname in files:
        path = os.path.join(CLIP_DIR, fname)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        fm = parse_frontmatter(content)
        date = fm.get('date') or extract_date_from_filename(fname)
        clips.append({
            'file': fname,
            'title': fm.get('title', fname),
            'date': date,
            'platform': fm.get('source_platform', 'unknown'),
            'tags': fm.get('tags', []),
            'keywords': fm.get('keywords', []),
            'summary': fm.get('summary', ''),
            'url': fm.get('original_url', ''),
        })

    total = len(clips)
    platform_count = Counter(c['platform'] for c in clips)
    tag_count = Counter(t for c in clips for t in c['tags'])
    keyword_count = Counter(k for c in clips for k in c['keywords'])

    date_count = Counter(c['date'] for c in clips if c['date'])
    sorted_dates = sorted(date_count.items())

    # 近7天动态
    cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    recent = [c for c in clips if c['date'] and c['date'] >= cutoff]
    recent_total = len(recent)
    recent_platform = Counter(c['platform'] for c in recent)
    recent_tag = Counter(t for c in recent for t in c['tags'])

    sample_summaries = [c['summary'] for c in clips if c['summary']][:8]

    lines = []
    lines.append("# 📰 剪报目录总结\n")
    lines.append(f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"**剪报总数**：{total} 篇\n")
    lines.append(f"**涵盖平台**：{', '.join(f'{k}({v})' for k, v in platform_count.most_common())}\n")
    lines.append(f"**时间跨度**：{min(date_count.keys()) if date_count else '?'} ~ {max(date_count.keys()) if date_count else '?'}\n")
    lines.append(f"**近7天新增**：{recent_total} 篇\n")
    lines.append(f"\n---\n")

    lines.append("## 🗓️ 近7天动态\n")
    for d, cnt in sorted_dates[-7:]:
        lines.append(f"- **{d}**：+{cnt} 篇\n")
    lines.append(f"\n**近7天平台分布**：{', '.join(f'{k}({v})' for k, v in recent_platform.most_common(5))}\n")
    lines.append(f"\n**近7天标签**：{', '.join(f'`{t}`' for t, _ in recent_tag.most_common(10))}\n")
    lines.append(f"\n---\n")

    lines.append("## 🏷️ 全量标签 TOP 15\n")
    for tag, cnt in tag_count.most_common(15):
        lines.append(f"- `{tag}` ×{cnt}\n")
    lines.append(f"\n---\n")

    lines.append("## 🔑 全量关键词 TOP 20\n")
    for kw, cnt in keyword_count.most_common(20):
        lines.append(f"- `{kw}` ×{cnt}\n")
    lines.append(f"\n---\n")

    lines.append("## 📋 摘要样本（前8篇）\n")
    for s in sample_summaries:
        lines.append(f"> {s}\n")
    lines.append(f"\n---\n")

    lines.append("## 📂 完整文件清单\n")
    lines.append("| 日期 | 平台 | 标题 | 标签 |\n")
    lines.append("|------|------|------|------|\n")
    for c in clips:
        tags_str = ', '.join(c['tags'][:3]) if c['tags'] else '-'
        title = c['title'][:30] + '...' if len(c['title']) > 30 else c['title']
        lines.append(f"| {c['date'] or '?'} | {c['platform']} | {title} | {tags_str} |\n")

    output = '\n'.join(lines)
    print(output)
    return output


if __name__ == '__main__':
    run_summary()
