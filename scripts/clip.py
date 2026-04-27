#!/usr/bin/env python3
"""
剪报核心脚本 clip.py
====================
统一的内容抓取 + 清洗 + 质量检查 + frontmatter 生成工具。

运行方式（由派蒙调用，输出 JSON 到 stdout）：
    python3 scripts/clip.py scrape <url>    # 抓取 + 质量检查，输出 JSON
    python3 scripts/clip.py exists <url>   # 检查 URL 是否已存
    python3 scripts/clip.py save <url>     # 完整保存流程

设计原则：
- 所有提取逻辑集中在此脚本，不再散落在 SKILL.md 里
- 脚本输出结构化 JSON，由派蒙读取后做第六步半分析和最终判断
- 质量检查在写文件之前执行，有问题时报错，不静默写坏文件

踩坑教训（请勿与脚本内函数/变量同名）：
- 局部变量名不能与模块级函数同名（如 clean_text 是函数，局部变量请用 clean_readme）
- GitHub README 是 HTML 格式，必须过通用TextExtractor清洗，不能直接用原始文本
- 即刻帖子 author 字段有时是 UUID 而非 nickname，需要 fallback 到 bio
- 微信文章有时需要 fallback 到 img-content 区域（如三联生活实验室）
- 微信登录墙：空壳 HTML 小于 50KB 且不含 id="js_content"，判断为登录墙
- 飞书 blocks API 默认分页，每页最多500条，需要循环拉取
"""

import sys
import os
import re
import json
import time
import html.parser
import datetime
import urllib.request
import urllib.error
from typing import Optional

# ============================================================================
# 常量
# ============================================================================

CLIP_DIR = "/volume2/AI工作区/知识库/1.raw/派蒙剪报"
BACKUP_DIR = os.path.join(CLIP_DIR, ".bak")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 截断标记（微信文章用）
TRUNCATE_MARKERS = ["未经授权", "预览时标签不可点", "值班主编", "排版"]

# 质量检查阈值
MIN_TEXT_LENGTH = 500       # 正文少于 500 字可能提取失败
MAX_TEXT_LENGTH_CN = 100000 # 中文正文合理上限（10万字）
MIN_TITLE_LENGTH = 3        # 标题最短

# ============================================================================
# 工具函数
# ============================================================================

def http_get(url: str, retries: int = 3, delay: float = 5.0) -> Optional[str]:
    """带重试的 HTTP GET，失败返回 None"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=30)
            return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 529:
                # 即刻服务器限流，稍后重试
                if attempt < retries - 1:
                    time.sleep(delay * 2)
                    continue
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return None
    return None


def clean_text(text: str) -> str:
    """标准清洗：HTML 实体 + 注释 + 垃圾残留"""
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r" +\n", "\n", text)           # 段尾空格
    text = re.sub(r"\n{3,}", "\n\n", text)      # 连续空行压缩
    # 清除微信隐藏内容残留的孤立 ">" 分隔符（出现在行首且单独成行的 >）
    text = re.sub(r"\n>\n", "\n", text)
    text = re.sub(r"^>\n", "", text)
    text = text.strip()
    return text


def truncate_at_marker(text: str) -> str:
    """在截断标记处截断，返回截断后的文本和是否截断了的标记"""
    for marker in TRUNCATE_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            return text[:idx], marker
    return text, None


# ============================================================================
# HTML 正文提取器（通用基础款）
# ============================================================================

class 通用TextExtractor(html.parser.HTMLParser):
    """通用 HTML→文本提取器，识别 h2/h3/h4 为 ## 标题"""

    def __init__(self):
        super().__init__()
        self.texts = []
        self.skip_tags = {"script", "style", "noscript", "iframe", "embed", "object"}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1
        elif tag in ("br", "p", "section", "div"):
            self.texts.append("\n")
        elif tag in ("h2", "h3", "h4"):
            self.texts.append("\n\n## ")

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.current_skip = max(0, self.current_skip - 1)
        elif tag in ("p", "section", "div"):
            self.texts.append("\n")
        elif tag in ("h2", "h3", "h4"):
            self.texts.append("\n")

    def handle_data(self, data):
        if self.current_skip == 0:
            text = data.strip()
            if text:
                self.texts.append(text + " ")

    def get_text(self) -> str:
        return "".join(self.texts)


# ============================================================================
# 平台提取器
# ============================================================================

def extract_wechat(url: str) -> dict:
    """微信公众号（SPA，内容嵌在 JS 里）"""
    html = http_get(url)
    if not html:
        return {"error": "请求失败，请检查网络或URL"}

    # 登录墙检测：微信返回空壳 HTML 时 js_content 不存在
    if len(html) < 50000 and 'id="js_content"' not in html:
        return {"error": "登录墙拦截，该内容需要关注公众号后才能访问"}

    # 元数据提取
    # title：优先 og:title，回退到 <title>
    title_m = re.search(r'og:title["\s]*content=["\']([^"\']+)["\']', html, re.I)
    if not title_m:
        title_m = re.search(r'<title>([^<]+)</title>', html, re.I)
    title = title_m.group(1).strip() if title_m else "Unknown"

    # author：微信公众号的 "作者" 实为公众号名称，og:article:author 包含公众号名
    # var author 也是公众号名称，两者等价，取 og: 的更完整
    author_m = re.search(r'og:article:author["\s]*content=["\']([^"\']+)["\']', html, re.I)
    if not author_m:
        author_m = re.search(r'var author\s*=\s*"([^"]*)"', html)
    author = author_m.group(1).strip() if author_m else "Unknown"

    # 发布时间
    ct_m = re.search(r'var ct\s*=\s*"(\d+)"', html)
    ct_str = ct_m.group(1) if ct_m else "0"
    pub_date = datetime.datetime.fromtimestamp(int(ct_str)).strftime("%Y-%m-%d") if ct_str and ct_str != "0" else datetime.datetime.now().strftime("%Y-%m-%d")

    # 正文区域提取（js_content 到 js_pc_qr_code）
    m = re.search(r'id="js_content"(.*?)id="js_pc_qr_code"', html, re.DOTALL)
    if not m:
        return {"error": "无法定位正文区域 js_content"}

    raw_html = m.group(1)

    # 特殊处理：style="visibility:hidden" 残留
    raw_html = re.sub(r'style="[^"]*visibility:\s*hidden[^"]*"', '', raw_html)

    # HTML→文本
    extractor = 通用TextExtractor()
    try:
        extractor.feed(raw_html)
    except Exception:
        pass
    raw_text = extractor.get_text()
    raw_text = clean_text(raw_text)

    # 截断
    raw_text, used_marker = truncate_at_marker(raw_text)

    # fallback：正文少于 2000 字时尝试 img-content
    if len(raw_text) < 2000:
        idx_start = html.find('id="img-content"')
        idx_end = html.find('id="js_pc_qr_code"')
        if idx_start != -1 and idx_end != -1 and idx_start < idx_end:
            fallback_html = html[idx_start:idx_end]
            extractor2 = 通用TextExtractor()
            try:
                extractor2.feed(fallback_html)
            except Exception:
                pass
            raw_text2 = clean_text(extractor2.get_text())
            raw_text2, _ = truncate_at_marker(raw_text2)
            if len(raw_text2) > len(raw_text):
                raw_text = raw_text2

    return {
        "title": title.strip(),
        "author": author.strip(),
        "pub_date": pub_date,
        "platform": "微信",
        "raw_text": raw_text,
        "truncated_by": used_marker,
    }


def extract_github(url: str) -> dict:
    """GitHub README"""
    # 解析 URL 获取 repo
    m = re.search(r'github\.com[/:]([^/]+)/([^/\.]+)', url)
    if not m:
        return {"error": "无法解析 GitHub URL"}

    owner, repo = m.group(1), m.group(2).replace('.git', '')
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"

    # 尝试读 README
    readme = http_get(raw_url)
    if not readme:
        # 尝试其他分支
        try:
            req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github.v3+json"})
            resp = urllib.request.urlopen(req, timeout=15)
            repo_data = json.loads(resp.read())
            default_branch = repo_data.get("default_branch", "main")
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/README.md"
            readme = http_get(raw_url)
        except Exception:
            pass

    if not readme:
        return {"error": "无法获取 README 内容"}

    # GitHub README 是 HTML 格式，需要过 HTMLParser 清洗
    extractor = 通用TextExtractor()
    try:
        extractor.feed(readme)
    except Exception:
        pass
    clean_readme = clean_text(extractor.get_text())

    # 元数据
    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github.v3+json"})
        resp = urllib.request.urlopen(req, timeout=15)
        repo_data = json.loads(resp.read())
        created_at = repo_data.get("created_at", "")[:10]
        updated_at = repo_data.get("updated_at", "")[:10]
        description = repo_data.get("description", "")
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
    except Exception:
        created_at = updated_at = datetime.datetime.now().strftime("%Y-%m-%d")
        description = ""

    return {
        "title": f"{owner}/{repo}",
        "author": owner,
        "pub_date": created_at,
        "platform": "GitHub",
        "raw_text": clean_readme,
        "description": description,
        "stars": stars,
        "forks": forks,
    }


def extract_jike(url: str) -> dict:
    """即刻即客帖（SPA，JSON 在 script 里）"""
    html = http_get(url)
    if not html:
        return {"error": "请求失败"}

    # 提取所有 script，找包含 post 数据的
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    post_data = None
    for s in scripts:
        if "props" in s and len(s) > 10000:
            try:
                # 尝试 JSON 解析
                data = json.loads(s)
                post = data.get("props", {}).get("pageProps", {}).get("post", {})
                if post:
                    post_data = post
                    break
            except Exception:
                continue

    if not post_data:
        return {"error": "无法解析即刻帖子数据"}

    user = post_data.get("user", {})
    # screenName 是用户显示名，username 是 UUID，bio 是个人简介兜底
    author = user.get("screenName") or user.get("nickname") or user.get("username") or user.get("bio") or "Unknown"
    content = post_data.get("content", "")
    created_at = post_data.get("createdAt", "")[:10]

    # 评论
    comments_html = ""
    try:
        comments = data.get("props", {}).get("pageProps", {}).get("comments", [])
        if comments:
            comment_lines = []
            for c in comments:
                if not c.get("replyToUser"):  # 只取顶层评论
                    nickname = c.get("user", {}).get("nickname", "匿名")
                    text = c.get("content", "")
                    comment_lines.append(f"【{nickname}】：{text}")
            if comment_lines:
                has_section = "## 评论区" in content
                comments_html = "\n\n---\n\n" + ("## 楼中评论\n\n" if has_section else "## 评论区\n\n") + "\n\n".join(comment_lines)
    except Exception:
        pass

    full_text = content + comments_html

    return {
        "title": content[:80].replace("\n", " "),
        "author": author,
        "pub_date": created_at,
        "platform": "即刻",
        "raw_text": full_text.strip(),
    }


def extract_feishu(url: str, app_id: str = None, app_secret: str = None) -> dict:
    """飞书文档（通过开放 API）"""
    # 从 URL 提取 wiki_token
    m = re.search(r'wiki[/:]([A-Za-z0-9_-]{10,})', url)
    if not m:
        return {"error": "无法从 URL 提取飞书 wiki token"}

    wiki_token = m.group(1)

    # 读取凭据（优先用环境变量或传入参数）
    app_id = app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        return {"error": "缺少飞书凭据 FEISHU_APP_ID / FEISHU_APP_SECRET"}

    try:
        # 获取 token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
        token_req = urllib.request.Request(token_url, data=token_data)
        token_req.add_header("Content-Type", "application/json")
        token_resp = urllib.request.urlopen(token_req, timeout=15)
        token = json.loads(token_resp.read())["tenant_access_token"]

        # 获取 wiki node
        wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={wiki_token}"
        wiki_req = urllib.request.Request(wiki_url)
        wiki_req.add_header("Authorization", f"Bearer {token}")
        wiki_resp = urllib.request.urlopen(wiki_req, timeout=15)
        node = json.loads(wiki_resp.read())["data"]["node"]
        obj_token = node["obj_token"]
        title = node["title"]

        # 解析时间（Unix时间戳 → 北京时间日期）
        obj_ts = node.get("obj_create_time") or node.get("node_create_time")
        if obj_ts:
            pub_date = datetime.datetime.fromtimestamp(
                int(obj_ts), tz=datetime.timezone(datetime.timedelta(hours=8))
            ).strftime("%Y-%m-%d")
        else:
            pub_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # 获取 blocks（分页循环）
        blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{obj_token}/blocks"
        blocks_req = urllib.request.Request(blocks_url)
        blocks_req.add_header("Authorization", f"Bearer {token}")
        blocks_resp = urllib.request.urlopen(blocks_req, timeout=15)
        result = json.loads(blocks_resp.read())
        all_blocks = result["data"]["items"]
        page_token = result["data"].get("page_token")

        # 循环拉取后续页
        while page_token:
            paged_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{obj_token}/blocks?page_token={page_token}"
            paged_req = urllib.request.Request(paged_url)
            paged_req.add_header("Authorization", f"Bearer {token}")
            paged_resp = urllib.request.urlopen(paged_req, timeout=15)
            paged_result = json.loads(paged_resp.read())
            all_blocks.extend(paged_result["data"]["items"])
            page_token = paged_result["data"].get("page_token")

        blocks = all_blocks

        # 解析 blocks
        TYPE_FIELDS = {
            1: "page", 2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
            6: "heading4", 12: "bullet", 13: "ordered", 14: "todo", 15: "code",
            16: "quote", 27: "divider", 31: "table", 32: "table_row",
            33: "table_cell", 34: "quote_container",
        }
        lines = []
        for block in blocks:
            bt = block.get("block_type", 0)
            field = TYPE_FIELDS.get(bt)
            if not field or field not in block:
                continue
            content = block[field]
            if isinstance(content, dict) and "elements" in content:
                text = "".join(
                    e["text_run"].get("content", "")
                    for e in content["elements"]
                    if "text_run" in e
                )
                if text.strip():
                    # heading 加标记
                    prefix = "## " if bt in (3, 4, 5, 6) else ""
                    lines.append(f"{prefix}{text}")
            elif isinstance(content, str) and content.strip():
                lines.append(content.strip())

        return {
            "title": title,
            "author": "飞书文档",
            "pub_date": pub_date,
            "platform": "飞书",
            "raw_text": "\n".join(lines),
        }
    except Exception as e:
        return {"error": f"飞书API错误: {str(e)}"}


def extract_bilibili(url: str) -> dict:
    """Bilibili 视频/专栏"""
    html = http_get(url)
    if not html:
        return {"error": "请求失败"}

    # 专栏：bilibili.com/read/
    if "/read/" in url or "/article/" in url:
        m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        if not m:
            m = re.search(r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        content_html = m.group(1) if m else html

        extractor = 通用TextExtractor()
        try:
            extractor.feed(content_html)
        except Exception:
            pass
        raw_text = clean_text(extractor.get_text())

        title_m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
        if not title_m:
            title_m = re.search(r'<title>([^<]+)</title>', html)
        title = title_m.group(1).strip() if title_m else "Unknown"

        date_m = re.search(r'<meta[^>]*(?:property|name)=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        pub_date = date_m.group(1)[:10] if date_m else datetime.datetime.now().strftime("%Y-%m-%d")

        return {
            "title": title,
            "author": "Bilibili",
            "pub_date": pub_date,
            "platform": "Bilibili",
            "raw_text": raw_text,
        }

    # 视频：bilibili.com/video/
    title_m = re.search(r'<title>([^<]+)</title>', html)
    title = title_m.group(1).replace("_哔哩哔哩 (゜-゜)つロ 干杯~-bilibili", "").strip() if title_m else "Unknown"

    desc_m = re.search(r'<meta name="description" content="([^"]+)"', html)
    description = desc_m.group(1) if desc_m else ""

    date_m = re.search(r'<meta[^>]*(?:property|name)=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    pub_date = date_m.group(1)[:10] if date_m else datetime.datetime.now().strftime("%Y-%m-%d")

    raw_text = "# " + title + "\n\n" + description

    return {
        "title": title,
        "author": "Bilibili",
        "pub_date": pub_date,
        "platform": "Bilibili",
        "raw_text": raw_text,
    }


def extract_generic(url: str) -> dict:
    """通用网页"""
    html = http_get(url)
    if not html:
        return {"error": "请求失败"}

    # 标题
    title_m = re.search(r'<title>([^<]+)</title>', html, re.I)
    title = title_m.group(1).strip() if title_m else "Unknown"

    # 发布时间
    date_m = re.search(r'<meta[^>]*(?:property|name)=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if not date_m:
        date_m = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']article:published_time["\']', html, re.I)
    pub_date = date_m.group(1)[:10] if date_m else datetime.datetime.now().strftime("%Y-%m-%d")

    # 正文区域（优先 article）
    m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
    if not m:
        m = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    content_html = m.group(1) if m else html

    extractor = 通用TextExtractor()
    try:
        extractor.feed(content_html)
    except Exception:
        pass
    raw_text = clean_text(extractor.get_text())

    # 截断
    raw_text, _ = truncate_at_marker(raw_text)

    return {
        "title": title,
        "author": "Unknown",
        "pub_date": pub_date,
        "platform": "web",
        "raw_text": raw_text,
    }


def extract(url: str) -> dict:
    """统一入口，根据 URL 自动分发到对应平台提取器"""
    if "mp.weixin.qq.com" in url:
        return extract_wechat(url)
    elif "github.com" in url:
        return extract_github(url)
    elif "jike.com" in url or "okjike.com" in url:
        return extract_jike(url)
    elif "feishu.cn" in url or "larksuite.com" in url:
        return extract_feishu(url)
    elif "bilibili.com" in url or "b23.tv" in url:
        return extract_bilibili(url)
    else:
        return extract_generic(url)


# ============================================================================
# 质量检查
# ============================================================================

def check_text(data: dict) -> list:
    """
    对提取结果做质量检查，返回问题列表。
    空列表 = 通过，有列表 = 有问题需要报告。
    """
    issues = []

    # 1. 错误检测
    if "error" in data:
        issues.append(f"提取错误: {data['error']}")
        return issues  # 有 error 就直接返回，后面的不用查了

    # 2. 标题检查
    title = data.get("title", "")
    if not title or len(title) < MIN_TITLE_LENGTH:
        issues.append(f"标题异常: '{title}'（长度 {len(title)}）")
    if title == "Unknown":
        issues.append("标题未能提取，值为 'Unknown'")

    # 3. 正文长度检查
    raw_text = data.get("raw_text", "")
    if len(raw_text) < MIN_TEXT_LENGTH:
        issues.append(f"正文过短（{len(raw_text)} 字），可能提取失败")
    if len(raw_text) > MAX_TEXT_LENGTH_CN:
        issues.append(f"正文超长（{len(raw_text)} 字），可能混入了垃圾内容")

    # 4. HTML 残留检查
    html_garbage_patterns = [
        (r'<script[^>]*>', "script 标签残留"),
        (r'<div[^>]*>', "div 标签残留"),
        (r'<a [^>]*href=', "a 标签残留"),
        (r'class=["\']', "class 属性残留"),
        (r'style=["\'][^"\']*["\']', "style 属性残留"),
        (r'data-[a-z-]+=["\']', "data-* 属性残留"),
        (r'window\.', "window. JS 变量残留"),
        (r'var\s+\w+\s*=', "var 变量声明残留"),
    ]
    for pattern, desc in html_garbage_patterns:
        if re.search(pattern, raw_text, re.I):
            issues.append(f"HTML/JS 垃圾残留: {desc}")

    # 5. 截断标记后还有正文（截断不彻底）
    for marker in TRUNCATE_MARKERS:
        idx = raw_text.find(marker)
        if idx != -1 and idx < len(raw_text) - 50:
            # 截断标记后面还有不少内容，说明截断位置可能不对
            after = raw_text[idx + len(marker):].strip()
            if len(after) > 100:
                issues.append(f"截断标记 '{marker}' 后仍有 {len(after)} 字内容，可能截断不彻底")
            break

    # 6. 文件名合法性（由调用方检查，这里只返回问题）
    # 7. frontmatter 字段完整性（由调用方检查）

    return issues


# ============================================================================
# Frontmatter 生成
# ============================================================================

def build_frontmatter(data: dict, record_date: str, record_time: str, url: str, raw_text: str) -> str:
    """生成标准 frontmatter 块（不包含正文）"""

    title = data.get("title", "Unknown")
    author = data.get("author", "Unknown")
    pub_date = data.get("pub_date", record_date)
    platform = data.get("platform", "web")

    # 提取关键词（简单词频法，过滤停用词，保留标题词）
    cn_stopwords = "的了和是在有我你他她它们这那要都被把能会与对向给从到为所以因为但是而且以及或者如果虽然那么多什么怎么多少自己一是二是三是可以已经不能没有与向被把"
    en_stopwords = "the a an is are was were be been being have has had do does did will would could should may might can to of in for on with at by from as into through during before after and or but if because while that this it its"
    stopwords = set(cn_stopwords.split()) | set(en_stopwords.split())
    words = re.findall(r'[\u4e00-\u9fff]{2,}', raw_text[:5000])  # 只用前5000字统计
    filtered = [w for w in words if w not in stopwords and len(w) >= 2]
    from collections import Counter
    top_words = [w for w, _ in Counter(filtered).most_common(10)]

    # 标题词优先
    title_words = re.findall(r'[\u4e00-\u9fff]{2,}', title)
    keywords = title_words[:3] + [w for w in top_words if w not in title_words][:2]

    fm = f"""---
title: {title}
type: raw
maturity: draft
date: {record_date}
updated: {record_date}
source_platform: {platform}
original_url: {url}
recorded_at: {record_time}
summary: （由派蒙根据原文内容补充，描述文章类型和主题，不超过150字）
keywords: [{', '.join(keywords[:5])}]
tags: [（由派蒙添加主题标签）]
---"""
    return fm


# ============================================================================
# 文件操作
# ============================================================================

def filename_safe(title: str, date_str: str = "2026.01.01") -> str:
    """生成合法的文件名"""
    safe = title[:50].replace("/", "-").replace("\\", "-").replace(":", "：").replace("*", "").replace("?", "").replace('"', "").replace("<", "").replace(">", "").strip()
    # 去掉点（文件名规范要求点只用于日期分隔）
    safe = safe.replace(".", "·")
    filename = f"{date_str}-{safe}.md"
    return filename


def file_exists_for_url(url: str) -> Optional[str]:
    """检查 URL 是否已在剪报库中（精确匹配 original_url 字段），返回文件路径，不存在返回 None"""
    if not os.path.exists(CLIP_DIR):
        return None
    # 转义 URL 中的特殊字符，用于正则匹配
    escaped = re.escape(url)
    pattern = re.compile(r"^original_url:\s*" + escaped + r"$", re.MULTILINE)
    for f in os.listdir(CLIP_DIR):
        if not f.endswith(".md") or f == "README.md":
            continue
        path = os.path.join(CLIP_DIR, f)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
                if pattern.search(content):
                    return path
        except Exception:
            continue
    return None


def save_clip(data: dict, url: str, record_date: str, record_time: str) -> dict:
    """
    完整保存流程：检查 → 质量检查 → 写文件。
    返回结果 dict，包含 status / file_path / issues / frontmatter
    """
    # 1. 去重检查
    existing = file_exists_for_url(url)
    if existing:
        return {"status": "exists", "file_path": existing}

    # 2. 质量检查
    issues = check_text(data)
    if issues:
        return {"status": "check_failed", "issues": issues}

    # 3. 构建文件名
    filename = filename_safe(data.get("title", "Unknown"), record_date.replace("-", "."))
    filepath = os.path.join(CLIP_DIR, filename)

    # 4. 处理文件名冲突
    counter = 1
    while os.path.exists(filepath):
        base = filename.replace(".md", "")
        filename = f"{base}-{counter}.md"
        filepath = os.path.join(CLIP_DIR, filename)
        counter += 1

    # 5. 写入文件
    fm = build_frontmatter(data, record_date, record_time, url, data.get("raw_text", ""))
    body = data.get("raw_text", "")

    full_content = f"""{fm}

{body}

---

## 变更记录

- {record_time} — 初始创建
"""

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(full_content)

    return {
        "status": "ok",
        "file_path": filepath,
        "filename": filename,
        "frontmatter": fm,
    }


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: clip.py <command> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scrape":
        # 抓取并输出 JSON（不写文件）
        url = sys.argv[2] if len(sys.argv) > 2 else ""
        if not url:
            print(json.dumps({"error": "缺少 URL"}))
            sys.exit(1)
        data = extract(url)
        issues = check_text(data)
        result = {
            "url": url,
            "data": data,
            "issues": issues,
            "passed": len(issues) == 0,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "check-text":
        # 检查传入的文本数据（用于调试）
        raw = sys.argv[2] if len(sys.argv) > 2 else "{}"
        data = json.loads(raw)
        issues = check_text(data)
        print(json.dumps({"issues": issues, "passed": len(issues) == 0}, ensure_ascii=False, indent=2))

    elif cmd == "exists":
        # 检查 URL 是否已存在
        url = sys.argv[2] if len(sys.argv) > 2 else ""
        existing = file_exists_for_url(url)
        if existing:
            print(json.dumps({"exists": True, "path": existing}))
        else:
            print(json.dumps({"exists": False}))

    elif cmd == "save":
        # 完整保存流程
        url = sys.argv[2] if len(sys.argv) > 2 else ""
        if not url:
            print(json.dumps({"error": "缺少 URL"}))
            sys.exit(1)
        now = datetime.datetime.now()
        record_date = now.strftime("%Y-%m-%d")
        record_time = now.strftime("%Y-%m-%d %H:%M:%S")

        data = extract(url)
        result = save_clip(data, url, record_date, record_time)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(json.dumps({"error": f"未知命令: {cmd}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
