# PaperTrail - Design

## Frankenstein stitch
Three parts that do not normally meet, chosen for what each one removes:
1. RSS (1999-era, still published by thousands of sites, no account). Removes the login and the algorithm.
2. Local Gemma 1B (open-weight, runs on a laptop via llama-cpp, GGUF file). Removes the cloud. Nothing about what you read leaves the machine.
3. A printed page (print CSS, one page, works with no power to the router). Removes the connection itself.

Decisions that shape the rest of the design: one file, stdlib only, because a dependency is a failure mode on a laptop with no internet. Five stories and three priorities, because the page limit is the product. Every summary labelled gemma or extractive, because a reader who cannot tell which machine wrote a sentence cannot trust it.

## Architecture
One file, `src/papertrail.py`, standard library only, plus an optional llama-cpp import that is loaded lazily and only when PAPER_GEMMA_MODEL points at a real file. That keeps the tool working with no model at all.

Modules inside the file, in order:
- RSS: `parse_rss` (handles RSS 2.0 item and Atom entry), `fetch_url`, `fetch_all` (per-feed errors do not kill the other feeds, items sorted newest first, duplicates removed at digest time).
- Tasks: `load_tasks` / `save_tasks` / `add_task`, plain JSON in `data/tasks.json`.
- Summarise: `extractive_summary` (first two sentences, quoted verbatim), `gemma_summary` (raw Gemma turn format, temperature 0, stop on end-of-turn, rejects answers under 4 words), `summarise` (Gemma first, extractive fallback, returns source label).
- Digest: `build_digest` (top 5 unique stories, 3 priorities from open tasks, falling back to top 3 story titles), `render_digest_html` / `render_digest_text`, `write_digest`.
- Web: `Handler` on ThreadingHTTPServer, 127.0.0.1 only. GET / (list), /digest, /digest.txt. POST /api/tasks, /api/fetch, /api/digest, then redirect to /.

## Data
- `data/feeds.json`: list of {name, url}. `sample://name.xml` URLs load bundled files in `data/sample/`, so the demo works offline.
- `data/cache.json`: {fetched_at, items[]}, written by fetch.
- `data/tasks.json`: list of {text, done, added}.
- `output/digest-YYYY-MM-DD.html` and `.txt`.

## Failure modes, decided in advance
- A feed is down: record the error, keep the other feeds, keep the old cache.
- Gemma is missing or returns junk: extractive fallback, labelled honestly.
- No tasks: priorities fall back to the top 3 story titles, and the digest says so by listing them as priorities.
- No stories cached: the digest says "No stories cached yet. Run fetch first." instead of inventing any.

## What was actually built, 2026-11-22
Exactly this design, verified. The Gemma path was tested with the Gemma 3 1B GGUF already on this machine (from the SlothSort work), via PAPER_GEMMA_MODEL: all 5 sample stories summarised as `gemma` in 13 seconds total on 2026-11-22. The extractive fallback was also tested with no model set. See README for the measured numbers.


## v2 upgrade (2026-11-22)
- Web UI is now a real product surface: static/app.css (system fonts, dark and light, responsive, no gradients), static/app.js (theme toggle, read and favourite buttons, task checkboxes, Listen button, service worker registration), static/sw.js (cache-first app shell), static/manifest.json.
- Data grew, plain files still: data/feeds.json gains an added date; data/cache.json items gain id, read, and favourite, kept across refetches; data/tasks.json gains id and due; data/settings.json holds the fetch interval and Gemma model path; data/stats.json holds the days used, from which the streak is computed.
- Routes: GET /, /feeds, /digest, /tasks, /settings, /digest.txt, /static/*, /sw.js, /api/search, /api/stats, /api/speak. POST /api/tasks, /api/feeds, /api/read, /api/favourite, /api/fetch, /api/digest, /api/settings. Old form POSTs still redirect to /.
- TTS: no system TTS on this machine (espeak, espeak-ng, say all checked, none installed). The working path is the browser Web Speech API, via /api/speak text. The speak CLI tries a system TTS first and says so plainly if none exists.
- Offline: digest HTML has inline CSS only, no external fonts or scripts. The service worker caches /, the static files, and /digest.txt after the first visit.
- Print: @page A4 with 14mm margins, 12pt body, print media query hides nav and buttons. Checked by rule inspection and by the generated HTML. No PDF renderer was available here, so no PDF was produced.
- Deploy: render.yaml, Render free tier, start command runs the same server on $PORT and 0.0.0.0. requirements.txt is empty on purpose: stdlib only, llama-cpp stays optional.
- Steering change, recorded: the v1 product steering said PaperTrail is not a productivity system with streaks. The v2 upgrade adds a small days-used and streak counter because the brief asked for it. It is a counter only, no goals, no reminders, no gamification beyond the number.
- Measured after the upgrade: 24 tests, all passing. Gemma 3 1B still works: 5 stories, all labelled gemma, 13 seconds total, verified 2026-11-22. Live server test: home, feeds, tasks, settings, search, stats, and speak all returned 200.
