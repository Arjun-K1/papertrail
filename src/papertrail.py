#!/usr/bin/env python3
"""PaperTrail: a one-page morning digest for low-bandwidth days.

Three parts that do not normally meet, put together on purpose:
  1. RSS feeds. Written off as dead, still published by thousands
     of sites. No account, no algorithm, no tracking.
  2. A local open-weight Gemma model. Summarises offline, nothing
     leaves the machine. Extractive quotes when it cannot run.
  3. A printed page. Works when the internet does not.

Design notes a reader should know before changing anything:
  - Stdlib only, one file. A dependency is a thing that can break
    on a laptop with no internet. This one has none to break.
  - Five stories, three priorities, one page. The page limit is
    the product. A digest that needs scrolling is a feed.
  - Every summary is labelled gemma or extractive. If a reader
    cannot tell which machine wrote a sentence, they cannot trust it.

Commands:
  python3 src/papertrail.py fetch [--sample] [--feeds FILE]
  python3 src/papertrail.py digest [--date YYYY-MM-DD]
  python3 src/papertrail.py serve [--port 8000] [--host 127.0.0.1]
  python3 src/papertrail.py add-task "Buy milk" [--due YYYY-MM-DD]
  python3 src/papertrail.py add-feed https://example.com/feed.xml
  python3 src/papertrail.py remove-feed https://example.com/feed.xml
  python3 src/papertrail.py search "library"
  python3 src/papertrail.py speak [--date YYYY-MM-DD]
  python3 src/papertrail.py schedule [--interval 60]

Stdlib only. No paid API, no account, no GPU. Every summary in a
digest is labelled with its source: "gemma" or "extractive".
The extractive fallback never invents facts: it quotes the first
sentences of the source text.
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATIC = ROOT / "static"
CACHE_FILE = DATA / "cache.json"
FEEDS_FILE = DATA / "feeds.json"
TASKS_FILE = DATA / "tasks.json"
SETTINGS_FILE = DATA / "settings.json"
STATS_FILE = DATA / "stats.json"
OUTPUT = ROOT / "output"

DEFAULT_FEEDS = [
    {"name": "Sample News", "url": "sample://news.xml"},
    {"name": "Sample Tech", "url": "sample://tech.xml"},
]

DEFAULT_SETTINGS = {"fetch_interval_minutes": 0, "gemma_model": "",
                    "voice_rate": 1.0}


def story_id(title, link):
    return hashlib.sha1(f"{title}|{link}".encode()).hexdigest()[:12]


# ---------------------------------------------------------------- RSS
def parse_rss(xml_text):
    """Parse an RSS 2.0 or Atom feed. Returns a list of item dicts."""
    root = ET.fromstring(xml_text)
    items = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue

        def child(name):
            for c in el:
                if c.tag.split("}")[-1] == name:
                    return (c.text or "").strip()
            return ""
        title = child("title")
        link = child("link")
        if not link:
            for c in el:
                if c.tag.split("}")[-1] == "link":
                    link = c.get("href", "")
                    break
        summary = child("description") or child("summary") or child("content")
        published = child("pubDate") or child("updated") or child("published")
        if title:
            items.append({
                "title": title, "link": link,
                "summary": re.sub(r"<[^>]+>", " ", summary).strip(),
                "published": published,
            })
    return items


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "PaperTrail/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def load_feeds(path=FEEDS_FILE):
    if path.exists():
        feeds = json.loads(path.read_text())
        for f in feeds:
            f.setdefault("added", date.today().isoformat())
        return feeds
    return [dict(f) for f in DEFAULT_FEEDS]


def save_feeds(feeds, path=FEEDS_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feeds, indent=2))


def validate_feed_url(url):
    """Return an error string, or None if the URL looks like a feed."""
    url = (url or "").strip()
    if not url:
        return "Feed URL is empty."
    if url.startswith("sample://"):
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "Feed URL must start with http:// or https://."
    if not parsed.netloc or " " in url:
        return "Feed URL is not a valid address."
    return None


def add_feed(url, name="", path=FEEDS_FILE):
    """Validate, fetch once to prove it parses, then save. Returns (ok, msg)."""
    err = validate_feed_url(url)
    if err:
        return False, err
    feeds = load_feeds(path)
    if any(f.get("url") == url for f in feeds):
        return False, "That feed is already listed."
    try:
        if url.startswith("sample://"):
            xml_text = (DATA / "sample" / url.split("://", 1)[-1]).read_text()
        else:
            xml_text = fetch_url(url)
        items = parse_rss(xml_text)
    except Exception as exc:
        return False, f"Could not read that feed: {exc}"
    if not items:
        return False, "That feed parsed but has no items. Check the URL."
    feeds.append({"name": name or url, "url": url,
                  "added": date.today().isoformat()})
    save_feeds(feeds, path)
    return True, f"Added feed: {name or url} ({len(items)} items found)."


def remove_feed(url, path=FEEDS_FILE):
    feeds = load_feeds(path)
    kept = [f for f in feeds if f.get("url") != url]
    if len(kept) == len(feeds):
        return False, "That feed was not listed."
    save_feeds(kept, path)
    return True, f"Removed feed: {url}"


def load_cache(path=CACHE_FILE):
    if path.exists():
        cache = json.loads(path.read_text())
    else:
        cache = {"fetched_at": None, "items": []}
    for item in cache.get("items", []):
        item.setdefault("id", story_id(item.get("title", ""), item.get("link", "")))
        item.setdefault("read", False)
        item.setdefault("favourite", False)
    return cache


def save_cache(cache, path=CACHE_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))


def fetch_all(feeds=None, sample=False):
    """Fetch every feed. Returns (cache, errors). Sample mode parses
    the bundled data/sample/*.xml files so the demo works offline.
    Read and favourite flags survive a refetch."""
    feeds = feeds if feeds is not None else load_feeds()
    old = {i.get("id"): i for i in load_cache().get("items", [])}
    items, errors = [], []
    for feed in feeds:
        url = feed.get("url", "")
        try:
            if sample or url.startswith("sample://"):
                name = url.split("://", 1)[-1]
                xml_text = (DATA / "sample" / name).read_text()
            else:
                xml_text = fetch_url(url)
            for item in parse_rss(xml_text):
                item["source"] = feed.get("name", url)
                item["id"] = story_id(item["title"], item.get("link", ""))
                prev = old.get(item["id"], {})
                item["read"] = prev.get("read", False)
                item["favourite"] = prev.get("favourite", False)
                items.append(item)
        except Exception as exc:
            errors.append(f"{feed.get('name', url)}: {exc}")

    def sort_key(item):
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(item["published"], fmt)
            except Exception:
                continue
        return datetime.min
    items.sort(key=sort_key, reverse=True)
    cache = {"fetched_at": datetime.now().isoformat(timespec="seconds"),
             "items": items}
    save_cache(cache)
    return cache, errors


def search_stories(query, cache=None):
    """Case-insensitive search over title, summary, and source."""
    cache = cache if cache is not None else load_cache()
    q = (query or "").strip().lower()
    if not q:
        return cache.get("items", [])
    return [i for i in cache.get("items", [])
            if q in i.get("title", "").lower()
            or q in i.get("summary", "").lower()
            or q in i.get("source", "").lower()]


def mark_read(item_id, read=True, path=CACHE_FILE):
    cache = load_cache(path)
    for item in cache.get("items", []):
        if item.get("id") == item_id:
            item["read"] = bool(read)
            save_cache(cache, path)
            return True
    return False


def toggle_favourite(item_id, path=CACHE_FILE):
    cache = load_cache(path)
    for item in cache.get("items", []):
        if item.get("id") == item_id:
            item["favourite"] = not item.get("favourite", False)
            save_cache(cache, path)
            return item["favourite"]
    return None


# ---------------------------------------------------------------- settings / stats
def load_settings(path=SETTINGS_FILE):
    settings = dict(DEFAULT_SETTINGS)
    if path.exists():
        settings.update(json.loads(path.read_text()))
    return settings


def save_settings(settings, path=SETTINGS_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2))


def load_stats(path=STATS_FILE):
    if path.exists():
        stats = json.loads(path.read_text())
        stats.setdefault("days", [])
        return stats
    return {"days": []}


def record_day_used(day=None, path=STATS_FILE):
    """Record a day PaperTrail was used. Returns (days_used, streak)."""
    day = day or date.today().isoformat()
    stats = load_stats(path)
    if day not in stats["days"]:
        stats["days"].append(day)
        stats["days"] = sorted(set(stats["days"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2))
    return len(stats["days"]), day_streak(stats["days"])


def day_streak(days):
    """Consecutive days ending today, or yesterday if today is not in yet."""
    if not days:
        return 0
    dates = sorted({datetime.strptime(d, "%Y-%m-%d").date() for d in days})
    today = date.today()
    end = today if today in dates else today - timedelta(days=1)
    if end not in dates:
        return 0
    streak, cursor = 0, end
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ---------------------------------------------------------------- tasks
def load_tasks(path=TASKS_FILE):
    if path.exists():
        tasks = json.loads(path.read_text())
    else:
        tasks = []
    for i, t in enumerate(tasks):
        t.setdefault("id", f"t{i + 1}")
        t.setdefault("done", False)
        t.setdefault("added", date.today().isoformat())
        t.setdefault("due", "")
    return tasks


def save_tasks(tasks, path=TASKS_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2))


def _next_task_id(tasks):
    nums = [int(t["id"][1:]) for t in tasks
            if t.get("id", "").startswith("t") and t["id"][1:].isdigit()]
    return f"t{max(nums, default=0) + 1}"


def add_task(text, due="", path=TASKS_FILE):
    tasks = load_tasks(path)
    tasks.append({"id": _next_task_id(tasks), "text": text.strip(),
                  "done": False, "added": date.today().isoformat(),
                  "due": due or ""})
    save_tasks(tasks, path)
    return tasks


def update_task(task_id, text=None, due=None, done=None, path=TASKS_FILE):
    tasks = load_tasks(path)
    for t in tasks:
        if t.get("id") == task_id:
            if text is not None:
                t["text"] = text.strip()
            if due is not None:
                t["due"] = due
            if done is not None:
                t["done"] = bool(done)
            save_tasks(tasks, path)
            return t
    return None


def delete_task(task_id, path=TASKS_FILE):
    tasks = load_tasks(path)
    kept = [t for t in tasks if t.get("id") != task_id]
    if len(kept) == len(tasks):
        return False
    save_tasks(kept, path)
    return True


# ---------------------------------------------------------------- summarise
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def extractive_summary(text, max_sentences=2):
    """Quote the first sentences. Never invents, never paraphrases."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return ""
    parts = SENTENCE_RE.split(clean)
    return " ".join(parts[:max_sentences]).strip()


_GEMMA = None


def gemma_summary(text, model_file):
    """One short plain-language summary from a local Gemma GGUF file.
    Returns None on any failure, so the caller falls back cleanly.
    Temperature 0, 25 word cap, 4 word minimum: a digest summary
    should be repeatable, short, and never a half sentence. The 1B
    model is deliberate. A larger model is slower and hotter on a
    laptop CPU, and no more accurate at one sentence summaries."""
    global _GEMMA
    if not model_file or not Path(model_file).exists():
        return None
    try:
        if _GEMMA is None:
            from llama_cpp import Llama
            _GEMMA = Llama(model_path=str(model_file), n_ctx=1024,
                           n_threads=2, verbose=False)
        prompt = (
            "<start_of_turn>user\n"
            "Summarise this news item in one plain sentence, under 25 words. "
            "Use only facts from the text. Do not add anything.\n"
            f"Text: {text[:800]}"
            "<end_of_turn>\n<start_of_turn>model\n"
        )
        out = _GEMMA.create_completion(
            prompt, max_tokens=60, temperature=0.0,
            stop=["<end_of_turn>", "<start_of_turn>"])
        result = (out["choices"][0]["text"] or "").strip()
        result = re.sub(r"\s+", " ", result)
        return result if len(result.split()) >= 4 else None
    except Exception:
        return None


def summarise(text, model_file=None):
    """Returns (summary, source) where source is 'gemma' or 'extractive'."""
    if model_file:
        got = gemma_summary(text, model_file)
        if got:
            return got, "gemma"
    return extractive_summary(text), "extractive"


# ---------------------------------------------------------------- digest
def build_digest(cache=None, tasks=None, day=None, model_file=None):
    day = day or date.today().isoformat()
    cache = cache if cache is not None else load_cache()
    tasks = tasks if tasks is not None else load_tasks()
    seen, stories = set(), []
    for item in cache.get("items", []):
        key = item["title"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        text = item.get("summary") or item["title"]
        summary, source = summarise(text, model_file)
        stories.append({
            "title": item["title"], "link": item.get("link", ""),
            "source": item.get("source", ""),
            "published": item.get("published", ""),
            "summary": summary, "summary_source": source,
        })
        if len(stories) >= 5:
            break
    open_tasks = [t for t in tasks if not t.get("done")]
    priorities = [t["text"] for t in open_tasks[:3]]
    if not priorities:
        priorities = [s["title"] for s in stories[:3]]
    return {"date": day, "fetched_at": cache.get("fetched_at"),
            "stories": stories, "tasks": open_tasks,
            "priorities": priorities}


def render_digest_html(digest):
    """Self-contained HTML: inline CSS only, no external fonts or scripts,
    so the file works fully offline and prints from any browser."""
    def esc(s):
        return html.escape(s or "")
    stories = "".join(
        f"<li><strong>{esc(s['title'])}</strong> "
        f"<span class='src'>{esc(s['source'])}"
        + (f" &middot; {esc(s['published'])}" if s.get('published') else "")
        + f"</span><br>{esc(s['summary'])} "
        f"<span class='tag'>summary: {esc(s['summary_source'])}</span></li>"
        for s in digest["stories"])
    tasks = "".join(f"<li>{esc(t['text'])}"
                    + (f" <span class='src'>due {esc(t['due'])}</span>" if t.get('due') else "")
                    + "</li>" for t in digest["tasks"])
    priorities = "".join(f"<li>{esc(p)}</li>" for p in digest["priorities"])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>PaperTrail digest {esc(digest['date'])}</title>
<style>
@page {{ size: A4; margin: 14mm 16mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Georgia, 'Times New Roman', serif; font-size: 12pt; line-height: 1.45;
  color: #111; margin: 0; padding: 0; }}
h1 {{ font-size: 20pt; margin: 0 0 2pt; }} .meta {{ color: #555; font-size: 9pt; margin: 0 0 10pt; }}
h2 {{ font-size: 12pt; border-bottom: 1px solid #999; padding-bottom: 2pt; margin: 12pt 0 6pt; }}
ol, ul {{ margin: 0; padding-left: 18pt; }}
li {{ margin-bottom: 7pt; }} li strong {{ font-size: 11pt; }}
.src {{ color: #555; font-size: 9pt; }} .tag {{ color: #555; font-size: 8pt; font-style: italic; }}
.noprint button {{ font-size: 11pt; padding: 6px 12px; margin-top: 12pt; cursor: pointer; }}
@media print {{
  body {{ padding: 0; }}
  .noprint {{ display: none !important; }}
  h1 {{ font-size: 19pt; }} li {{ margin-bottom: 6pt; }}
}}
</style></head><body>
<h1>PaperTrail &mdash; morning digest</h1>
<p class="meta">{esc(digest['date'])} &middot; fetched {esc(digest.get('fetched_at') or 'unknown')}</p>
<h2>Top stories</h2><ol>{stories or '<li>No stories cached yet. Run fetch first.</li>'}</ol>
<h2>Three priorities</h2><ol>{priorities}</ol>
<h2>Today&rsquo;s tasks</h2><ul>{tasks or '<li>Nothing listed.</li>'}</ul>
<p class="noprint"><button onclick="window.print()">Print this page</button>
<button onclick="window.location='/digest.txt'">Plain text version</button></p>
</body></html>
"""


def render_digest_text(digest):
    lines = [f"PaperTrail - morning digest {digest['date']}",
             f"fetched {digest.get('fetched_at') or 'unknown'}", "",
             "Top stories:"]
    for i, s in enumerate(digest["stories"], 1):
        lines.append(f"{i}. {s['title']} ({s['source']})")
        lines.append(f"   {s['summary']} [summary: {s['summary_source']}]")
    lines += ["", "Three priorities:"]
    lines += [f"- {p}" for p in digest["priorities"]]
    lines += ["", "Today's tasks:"]
    lines += [f"- {t['text']}" + (f" (due {t['due']})" if t.get('due') else "")
              for t in digest["tasks"]] or ["- Nothing listed."]
    return "\n".join(lines) + "\n"


def write_digest(digest):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT / f"digest-{digest['date']}.html"
    text_path = OUTPUT / f"digest-{digest['date']}.txt"
    html_path.write_text(render_digest_html(digest))
    text_path.write_text(render_digest_text(digest))
    record_day_used(digest["date"])
    return html_path, text_path


# ---------------------------------------------------------------- text to speech
def find_system_tts():
    """Return the name of a system TTS binary, or None on this machine."""
    for name in ("espeak-ng", "espeak", "say"):
        if shutil.which(name):
            return name
    return None


def speak_text(text, out_wav=None):
    """Speak text with the system TTS if one exists.
    Returns (ok, method, message). No system TTS on this VM, so the
    web UI uses the browser Web Speech API instead, which needs no server."""
    tts = find_system_tts()
    if not tts:
        return False, "none", ("No system TTS here. Use the Listen button "
                               "in the web UI, it reads the digest aloud "
                               "in your browser.")
    try:
        if tts == "say":
            import subprocess
            subprocess.run([tts, text], check=True, timeout=120)
        else:
            import subprocess
            cmd = [tts, "-v", "en"]
            if out_wav:
                cmd += ["-w", str(out_wav)]
            cmd.append(text)
            subprocess.run(cmd, check=True, timeout=120)
        return True, tts, f"Spoken with {tts}."
    except Exception as exc:
        return False, tts, f"System TTS failed: {exc}"


def digest_spoken_text(digest):
    """Plain text the Listen button and the speak command read aloud."""
    parts = [f"PaperTrail digest for {digest['date']}. Top stories."]
    for i, s in enumerate(digest["stories"], 1):
        parts.append(f"{i}. {s['title']}. {s['summary']}")
    parts.append("Your three priorities are:")
    for p in digest["priorities"]:
        parts.append(p + ".")
    return " ".join(parts)


# ---------------------------------------------------------------- web UI
NAV = """
<nav><a href="/">Stories</a><a href="/feeds">Feeds</a><a href="/digest">Digest</a>
<a href="/tasks">Tasks</a><a href="/settings">Settings</a></nav>
"""


def page_shell(title, body, extra_head=""):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} - PaperTrail</title>
<link rel="stylesheet" href="/static/app.css">
<link rel="manifest" href="/static/manifest.json">
{extra_head}</head><body>
<header><div class="wrap"><h1><a href="/">PaperTrail</a></h1>
<p class="tagline">One page a day, for low-bandwidth days.</p></div>{NAV}</header>
<main class="wrap">{body}</main>
<footer class="wrap"><p>Offline first. No account, no tracking, no cloud.
Summaries are labelled gemma or extractive.</p></footer>
<script src="/static/app.js"></script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8", status=200):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj), "application/json", status)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        return json.loads(raw) if raw else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        if path.startswith("/static/"):
            name = path[len("/static/"):]
            if ".." in name or "/" in name:
                return self._send("Not found.", status=404)
            f = STATIC / name
            if not f.exists():
                return self._send("Not found.", status=404)
            ctype = {"css": "text/css", "js": "text/javascript",
                     "json": "application/json"}.get(f.suffix[1:], "text/plain")
            return self._send(f.read_bytes(), ctype)
        if path == "/sw.js":
            f = STATIC / "sw.js"
            return self._send(f.read_text() if f.exists() else "", "text/javascript")
        if path == "/":
            cache = load_cache()
            q = qs.get("q", [""])[0]
            items = search_stories(q, cache) if q else cache.get("items", [])
            rows = "".join(
                f"<li class='story' data-id='{i['id']}'>"
                f"<strong>{html.escape(i['title'])}</strong> "
                f"<span class='src'>{html.escape(i.get('source', ''))}</span><br>"
                f"<span>{html.escape(i.get('summary', ''))}</span> "
                f"<span class='actions'><button data-read='{i['id']}'>"
                f"{'Read' if i.get('read') else 'Mark read'}</button> "
                f"<button data-fav='{i['id']}'>{'★ Saved' if i.get('favourite') else '☆ Save'}</button></span>"
                f"</li>" for i in items[:30])
            body = (f"<form class='search' method='get' action='/'>"
                    f"<input name='q' value='{html.escape(q)}' placeholder='Search stories'>"
                    f"<button>Search</button></form>"
                    f"<p class='meta'>{len(items)} stories cached"
                    + (f" &middot; fetched {html.escape(cache.get('fetched_at') or '')}" if cache.get('fetched_at') else "")
                    + f"</p><ul class='stories'>{rows or '<li>None yet. Add a feed, then fetch.</li>'}</ul>"
                    f"<p><a class='btn' href='/digest'>Today's digest</a> "
                    f"<a class='btn' href='/digest.txt'>Plain text</a></p>")
            return self._send(page_shell("Stories", body))
        if path == "/feeds":
            feeds = load_feeds()
            rows = "".join(
                f"<li>{html.escape(f.get('name', ''))} &mdash; "
                f"<code>{html.escape(f.get('url', ''))}</code> "
                f"<button data-remove-feed='{html.escape(f.get('url', ''))}'>Remove</button></li>"
                for f in feeds)
            body = (f"<h2>Feeds</h2><ul>{rows}</ul>"
                    f"<form method='post' action='/api/feeds'>"
                    f"<input name='url' placeholder='https://example.org/feed.xml' size='40' required> "
                    f"<input name='name' placeholder='Name (optional)' size='20'> "
                    f"<button>Add feed</button></form>"
                    f"<form method='post' action='/api/fetch'><button>Fetch feeds now</button></form>")
            return self._send(page_shell("Feeds", body))
        if path == "/tasks":
            tasks = load_tasks()
            rows = "".join(
                f"<li class='task' data-id='{t['id']}'>"
                f"<input type='checkbox' data-done='{t['id']}' {'checked' if t.get('done') else ''}> "
                f"<span>{html.escape(t['text'])}</span> "
                + (f"<span class='src'>due {html.escape(t['due'])}</span>" if t.get('due') else "")
                + f" <button data-del-task='{t['id']}'>Delete</button></li>"
                for t in tasks)
            body = (f"<h2>Tasks</h2><ul>{rows or '<li>Nothing listed.</li>'}</ul>"
                    f"<form method='post' action='/api/tasks'>"
                    f"<input name='text' placeholder='Add a task' size='30' required> "
                    f"<input name='due' type='date'> <button>Add task</button></form>")
            return self._send(page_shell("Tasks", body))
        if path == "/settings":
            settings = load_settings()
            stats = load_stats()
            body = (f"<h2>Settings</h2>"
                    f"<p>Days used: <strong>{len(stats['days'])}</strong> &middot; "
                    f"Current streak: <strong>{day_streak(stats['days'])} day(s)</strong></p>"
                    f"<form method='post' action='/api/settings'>"
                    f"<label>Fetch every <input name='fetch_interval_minutes' type='number' min='0' max='1440' "
                    f"value='{settings['fetch_interval_minutes']}'> minutes (0 means off)</label><br>"
                    f"<label>Gemma model file <input name='gemma_model' size='40' "
                    f"value='{html.escape(settings.get('gemma_model', ''))}' "
                    f"placeholder='/path/to/gemma3-1b.gguf'></label><br>"
                    f"<button>Save settings</button></form>"
                    f"<p class='meta'>System TTS on this machine: "
                    f"{html.escape(find_system_tts() or 'none, use the Listen button in your browser')}.</p>")
            return self._send(page_shell("Settings", body))
        if path == "/digest":
            digest = build_digest(model_file=_model_file())
            record_day_used(digest["date"])
            inner = render_digest_html(digest).split("<body>", 1)[1].rsplit("</body>", 1)[0]
            extra = ("<p><button class='btn' onclick='speakDigest()'>Listen to this digest</button> "
                     "<button class='btn' onclick='window.print()'>Print preview</button></p>")
            return self._send(page_shell("Today's digest", extra + inner))
        if path == "/digest.txt":
            digest = build_digest(model_file=_model_file())
            return self._send(render_digest_text(digest), "text/plain; charset=utf-8")
        if path == "/api/search":
            return self._json(search_stories(qs.get("q", [""])[0]))
        if path == "/api/stats":
            stats = load_stats()
            return self._json({"days_used": len(stats["days"]),
                               "streak": day_streak(stats["days"])})
        if path == "/api/speak":
            digest = build_digest(model_file=_model_file())
            return self._json({"text": digest_spoken_text(digest)})
        return self._send("Not found.", status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        ctype = self.headers.get("Content-Type", "")
        if "application/json" in ctype:
            form = self._read_json()
        else:
            length = int(self.headers.get("Content-Length") or 0)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
        if path == "/api/tasks":
            if form.get("_method") == "delete":
                delete_task(form.get("id", ""))
            elif form.get("id") and (form.get("text") or form.get("due") is not None
                                     or form.get("done") is not None):
                done = None
                if form.get("done") is not None:
                    done = str(form["done"]).lower() in ("1", "true", "on")
                update_task(form["id"], text=form.get("text"), due=form.get("due"), done=done)
            elif form.get("text"):
                add_task(form["text"], due=form.get("due", ""))
        elif path == "/api/feeds":
            if form.get("_method") == "delete":
                remove_feed(form.get("url", ""))
            elif form.get("url"):
                ok, msg = add_feed(form["url"], name=form.get("name", ""))
                if not ok:
                    return self._json({"ok": False, "message": msg}, status=400)
        elif path == "/api/read":
            mark_read(form.get("id", ""), str(form.get("read", "true")).lower() in ("1", "true"))
        elif path == "/api/fetch":
            fetch_all()
        elif path == "/api/favourite":
            toggle_favourite(form.get("id", ""))
        elif path == "/api/digest":
            write_digest(build_digest(model_file=_model_file()))
        elif path == "/api/settings":
            settings = load_settings()
            try:
                settings["fetch_interval_minutes"] = int(form.get("fetch_interval_minutes", 0))
            except ValueError:
                pass
            settings["gemma_model"] = form.get("gemma_model", "")
            save_settings(settings)
        if "application/json" in ctype:
            return self._json({"ok": True})
        self.send_response(303)
        self.send_header("Location", form.get("_next", "/"))
        self.end_headers()

    def log_message(self, *args):
        pass


def _model_file():
    return os.environ.get("PAPER_GEMMA_MODEL") or load_settings().get("gemma_model") or None


def serve(port, host="127.0.0.1"):
    settings = load_settings()
    interval = settings.get("fetch_interval_minutes", 0)
    if interval and interval > 0:
        def loop():
            while True:
                time.sleep(interval * 60)
                try:
                    fetch_all()
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True).start()
        print(f"Scheduled fetch every {interval} minutes.")
    print(f"PaperTrail on http://{host}:{port}/ (Ctrl-C to stop)")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="PaperTrail: RSS in, one printed page out.")
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="Cache RSS feeds")
    f.add_argument("--sample", action="store_true", help="Use bundled sample feeds")
    f.add_argument("--feeds", default=str(FEEDS_FILE))
    d = sub.add_parser("digest", help="Build today's digest")
    d.add_argument("--date", default=date.today().isoformat())
    s = sub.add_parser("serve", help="Start the web UI")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--host", default="127.0.0.1")
    t = sub.add_parser("add-task", help="Add a task")
    t.add_argument("text")
    t.add_argument("--due", default="")
    a = sub.add_parser("add-feed", help="Add an RSS feed")
    a.add_argument("url")
    a.add_argument("--name", default="")
    r = sub.add_parser("remove-feed", help="Remove an RSS feed")
    r.add_argument("url")
    q = sub.add_parser("search", help="Search cached stories")
    q.add_argument("query")
    sp = sub.add_parser("speak", help="Read today's digest aloud")
    sp.add_argument("--date", default=date.today().isoformat())
    sp.add_argument("--out-wav", default="")
    sc = sub.add_parser("schedule", help="Fetch on a schedule, then stop after one run")
    sc.add_argument("--interval", type=int, default=60)
    args = ap.parse_args(argv)

    model_file = _model_file()
    if args.command == "fetch":
        feeds = load_feeds(Path(args.feeds))
        cache, errors = fetch_all(feeds, sample=args.sample)
        print(f"Fetched {len(cache['items'])} items from {len(feeds)} feeds.")
        for e in errors:
            print(f"Warning: {e}", file=sys.stderr)
        return 0
    if args.command == "digest":
        digest = build_digest(day=args.date, model_file=model_file)
        html_path, text_path = write_digest(digest)
        print(f"Digest for {digest['date']}: {len(digest['stories'])} stories, "
              f"{len(digest['tasks'])} tasks.")
        print(f"Wrote {html_path}\nWrote {text_path}")
        for s_ in digest["stories"]:
            print(f"- {s_['title']} [summary: {s_['summary_source']}]")
        return 0
    if args.command == "serve":
        serve(args.port, host=args.host)
        return 0
    if args.command == "add-task":
        add_task(args.text, due=args.due)
        print(f"Added task: {args.text}")
        return 0
    if args.command == "add-feed":
        ok, msg = add_feed(args.url, name=args.name)
        print(msg)
        return 0 if ok else 1
    if args.command == "remove-feed":
        ok, msg = remove_feed(args.url)
        print(msg)
        return 0 if ok else 1
    if args.command == "search":
        for item in search_stories(args.query):
            print(f"- {item['title']} ({item.get('source', '')})")
        return 0
    if args.command == "speak":
        digest = build_digest(day=args.date, model_file=model_file)
        text = digest_spoken_text(digest)
        ok, method, msg = speak_text(text, out_wav=args.out_wav or None)
        print(msg)
        if not ok:
            print(text)
        return 0 if ok else 1
    if args.command == "schedule":
        print(f"Fetching every {args.interval} minutes. Press Ctrl-C to stop.")
        try:
            while True:
                cache, errors = fetch_all()
                print(f"Fetched {len(cache['items'])} items.")
                time.sleep(args.interval * 60)
        except KeyboardInterrupt:
            print("Stopped.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
