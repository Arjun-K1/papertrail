import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import papertrail as pt

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>First story</title><link>https://example.org/1</link>
<pubDate>Sat, 22 Nov 2026 06:00:00 GMT</pubDate>
<description>Alpha sentence. Beta sentence. Gamma sentence.</description></item>
<item><title>Second story</title><link>https://example.org/2</link>
<description>Only one sentence here.</description></item>
</channel></rss>"""


def test_parse_rss_finds_items():
    items = pt.parse_rss(RSS)
    assert len(items) == 2
    assert items[0]["title"] == "First story"
    assert items[0]["link"] == "https://example.org/1"
    assert "Alpha sentence" in items[0]["summary"]


def test_parse_rss_strips_html():
    items = pt.parse_rss(RSS.replace("Alpha sentence", "<b>Alpha</b> sentence"))
    assert "<b>" not in items[0]["summary"]


def test_extractive_summary_quotes_first_sentences():
    out = pt.extractive_summary("Alpha sentence. Beta sentence. Gamma sentence.")
    assert out == "Alpha sentence. Beta sentence."
    # It never invents: every word comes from the source.
    assert "Gamma" not in out


def test_extractive_summary_empty():
    assert pt.extractive_summary("") == ""


def test_summarise_falls_back_to_extractive_without_model():
    summary, source = pt.summarise("Alpha sentence. Beta sentence. Gamma sentence.",
                                   model_file=None)
    assert source == "extractive"
    assert summary == "Alpha sentence. Beta sentence."


def test_summarise_falls_back_when_model_missing():
    summary, source = pt.summarise("Alpha sentence. Beta sentence.",
                                   model_file="/no/such/model.gguf")
    assert source == "extractive"


def test_add_task_and_load(tmp_path):
    path = tmp_path / "tasks.json"
    pt.add_task("Do the thing", path=path)
    tasks = pt.load_tasks(path)
    assert len(tasks) == 1 and tasks[0]["text"] == "Do the thing"
    assert tasks[0]["done"] is False


def test_build_digest_top_five_and_priorities():
    cache = {"fetched_at": "2026-11-22T08:00:00",
             "items": [{"title": f"Story {i}", "link": "", "summary": f"Body {i}. More.",
                        "source": "Sample", "published": ""} for i in range(7)]}
    tasks = [{"text": "Task one", "done": False},
             {"text": "Task two", "done": False},
             {"text": "Done task", "done": True}]
    digest = pt.build_digest(cache=cache, tasks=tasks, day="2026-11-22")
    assert len(digest["stories"]) == 5
    assert digest["priorities"] == ["Task one", "Task two"]
    assert all(s["summary_source"] == "extractive" for s in digest["stories"])


def test_build_digest_dedupes_titles():
    cache = {"fetched_at": None, "items": [
        {"title": "Same", "link": "", "summary": "One.", "source": "A", "published": ""},
        {"title": "Same", "link": "", "summary": "Two.", "source": "B", "published": ""}]}
    digest = pt.build_digest(cache=cache, tasks=[], day="2026-11-22")
    assert len(digest["stories"]) == 1


def test_digest_html_labels_summary_source():
    digest = {"date": "2026-11-22", "fetched_at": None,
              "stories": [{"title": "T", "link": "", "source": "S",
                           "published": "", "summary": "Sum.",
                           "summary_source": "extractive"}],
              "tasks": [], "priorities": ["P"]}
    out = pt.render_digest_html(digest)
    assert "summary: extractive" in out
    assert "window.print()" in out


def test_homepage_renders_without_format_error():
    # Regression: the old PAGE used .format() and CSS braces raised KeyError.
    # The new shell uses f-strings, so braces in CSS are safe.
    out = pt.page_shell("Stories", "<li>Story</li>")
    assert "Story" in out and "Stories" in out
    assert "/static/app.css" in out


def test_digest_text_is_plain():
    digest = {"date": "2026-11-22", "fetched_at": None,
              "stories": [], "tasks": [], "priorities": []}
    assert "PaperTrail" in pt.render_digest_text(digest)


# --- upgrade tests (2026-11-22) -------------------------------------------

def test_validate_feed_url_rejects_bad():
    assert pt.validate_feed_url("") is not None
    assert pt.validate_feed_url("ftp://example.org/feed") is not None
    assert pt.validate_feed_url("not a url") is not None


def test_validate_feed_url_accepts_http_and_sample():
    assert pt.validate_feed_url("https://example.org/feed.xml") is None
    assert pt.validate_feed_url("sample://news.xml") is None


def test_add_feed_rejects_duplicate_and_bad(tmp_path, monkeypatch):
    feeds = tmp_path / "feeds.json"
    feeds.write_text("[]")
    monkeypatch.setattr(pt, "FEEDS_FILE", feeds)
    ok, _ = pt.add_feed("sample://news.xml", path=feeds)
    assert ok is True
    ok, msg = pt.add_feed("sample://news.xml", path=feeds)
    assert ok is False and "already" in msg
    ok, _ = pt.add_feed("ftp://example.org/x", path=feeds)
    assert ok is False


def test_remove_feed(tmp_path, monkeypatch):
    feeds = tmp_path / "feeds.json"
    feeds.write_text("[]")
    monkeypatch.setattr(pt, "FEEDS_FILE", feeds)
    pt.add_feed("sample://news.xml", path=feeds)
    ok, _ = pt.remove_feed("sample://news.xml", path=feeds)
    assert ok is True
    ok, _ = pt.remove_feed("sample://news.xml", path=feeds)
    assert ok is False


def test_search_stories(tmp_path):
    cache = {"fetched_at": None, "items": [
        {"title": "Library hours", "link": "", "summary": "Books and reading.",
         "source": "News", "published": ""},
        {"title": "Roads closed", "link": "", "summary": "Traffic diversions.",
         "source": "News", "published": ""}]}
    assert len(pt.search_stories("library", cache)) == 1
    assert len(pt.search_stories("NEWS", cache)) == 2
    assert len(pt.search_stories("", cache)) == 2


def test_mark_read_and_favourite_survive(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(pt, "CACHE_FILE", cache_path)
    items = [{"title": "A", "link": "https://example.org/a", "summary": "One.",
              "source": "S", "published": "", "id": "abc123"}]
    pt.save_cache({"fetched_at": None, "items": items}, path=cache_path)
    assert pt.mark_read("abc123", True, path=cache_path) is True
    assert pt.toggle_favourite("abc123", path=cache_path) is True
    assert pt.mark_read("nope", True, path=cache_path) is False
    loaded = pt.load_cache(cache_path)
    assert loaded["items"][0]["read"] is True
    assert loaded["items"][0]["favourite"] is True


def test_task_edit_delete_and_due(tmp_path):
    path = tmp_path / "tasks.json"
    pt.add_task("First", due="2026-11-25", path=path)
    tasks = pt.load_tasks(path)
    tid = tasks[0]["id"]
    assert tasks[0]["due"] == "2026-11-25"
    pt.update_task(tid, text="First, edited", done=True, path=path)
    tasks = pt.load_tasks(path)
    assert tasks[0]["text"] == "First, edited" and tasks[0]["done"] is True
    assert pt.delete_task(tid, path=path) is True
    assert pt.load_tasks(path) == []
    assert pt.delete_task("nope", path=path) is False


def test_day_streak():
    assert pt.day_streak([]) == 0
    today = pt.date.today()
    days = [(today - pt.timedelta(days=i)).isoformat() for i in range(3)]
    assert pt.day_streak(days) == 3
    assert pt.day_streak([days[0]]) == 1
    assert pt.day_streak([(today - pt.timedelta(days=5)).isoformat()]) == 0


def test_record_day_used_counts_once(tmp_path):
    path = tmp_path / "stats.json"
    n1, _ = pt.record_day_used("2026-11-22", path=path)
    n2, _ = pt.record_day_used("2026-11-22", path=path)
    assert n1 == 1 and n2 == 1


def test_speak_text_reports_no_system_tts_here(monkeypatch):
    monkeypatch.setattr(pt, "find_system_tts", lambda: None)
    ok, method, msg = pt.speak_text("Hello.")
    assert ok is False and method == "none" and "Listen" in msg


def test_digest_html_is_self_contained_and_print_ready():
    digest = {"date": "2026-11-22", "fetched_at": None,
              "stories": [{"title": "T", "link": "", "source": "S",
                           "published": "", "summary": "Sum.",
                           "summary_source": "gemma"}],
              "tasks": [], "priorities": ["P"]}
    out = pt.render_digest_html(digest)
    assert "http://" not in out and "https://" not in out
    assert "@page" in out and "@media print" in out
    assert "summary: gemma" in out


def test_static_assets_exist_and_are_local():
    root = Path(__file__).resolve().parent.parent
    for name in ("app.css", "app.js", "sw.js", "manifest.json"):
        assert (root / "static" / name).exists()
    css = (root / "static" / "app.css").read_text()
    assert "linear-gradient" not in css and "http" not in css
    js = (root / "static" / "app.js").read_text()
    assert "speechSynthesis" in js and "serviceWorker" in js
