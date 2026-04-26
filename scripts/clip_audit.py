#!/usr/bin/env python3
"""剪报规范达标检查脚本

运行方式：
    python3 scripts/clip_audit.py

触发修复的阈值：
    - summary 缺失 → 新增
    - summary 长度 > 150字 → 压缩至 150 字以内
    - 存在 HTML/JS 垃圾残留 → 清除
    - 正文超过 50 行且全文无任何换行 → 正文可能被截断或清洗过度，请检查
"""

import os

CLIP_DIR = "/volume2/AI工作区/知识库/1.raw/派蒙剪报"

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
    has_header = False
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
            if line.startswith('## '):
                has_header = True
            if any(x in line for x in ['var ', 'window.', '.weui-', '<!--', 'function ', '=> {', 'try {', '} catch']):
                has_html_garbage = True

    has_no_paragraph_break = False
    if content_lines > 50:
        body_start = content.find('\n---\n', 0)
        if body_start != -1:
            body_text = content[body_start+5:]
            if '\n' not in body_text:
                has_no_paragraph_break = True

    issue = ""
    clean_summary = summary_line.replace('summary:', '').strip() if summary_line else ""
    if not summary_line:
        issue += "无summary; "
    elif len(clean_summary) > 150:
        issue += f"summary过长({len(clean_summary)}字); "

    if has_no_paragraph_break:
        issue += "正文超50行且无换行分段; "
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
