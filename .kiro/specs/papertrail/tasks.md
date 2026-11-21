# PaperTrail - Tasks

## v1 (2026-11-22, done)
- [x] RSS parsing with xml.etree, RSS 2.0 and Atom, HTML stripped from summaries
- [x] fetch command, per-feed error handling, cache to data/cache.json, sample mode for offline demo
- [x] Tasks in data/tasks.json, add/list from CLI and web UI
- [x] Extractive summariser (first two sentences, quoted, never invents)
- [x] Local Gemma summariser via llama-cpp, lazy import, temperature 0, junk rejection, labelled "gemma"
- [x] Digest builder: top 5 unique stories, 3 priorities, today's tasks
- [x] Printable HTML digest with print CSS and plain text version in output/
- [x] Web UI on localhost:8000, stdlib http.server, no external assets
- [x] Sample feeds in data/sample/ (news.xml, tech.xml, 5 items total) and a verified sample digest
- [x] Unit tests in tests/test_papertrail.py, all passing
- [x] README, MIT LICENSE, .gitignore, local git repo, first commit
- [x] Demo video, 74 seconds, from a real terminal run, screen only, no face

## v2 upgrade (2026-11-22, done)
- [x] Polished web UI: clean design, dark and light mode, responsive, system fonts only, no external images, no purple gradients. Navigation: Stories, Feeds, Digest, Tasks, Settings.
- [x] Add and remove RSS feeds in the UI, with validation and a one-time parse check before saving.
- [x] Fetch on a schedule, from Settings, with a background thread in serve and a schedule CLI command.
- [x] Cache keeps read and favourite flags across refetches.
- [x] Search stories, case-insensitive, over title, summary, and source.
- [x] Mark stories read, save favourites.
- [x] Tasks with due dates, edit, mark done, delete, with ids.
- [x] Days used and streak counter in data/stats.json, shown on Settings.
- [x] TTS: Listen button in the UI using the Web Speech API. System TTS checked on this machine and none found, documented in README. speak CLI uses a system TTS if one exists.
- [x] Offline: digest HTML is self contained, no external fonts or scripts. Service worker caches the app shell. Manifest added.
- [x] Print: one-page A4 print CSS, print preview button. Checked by reading the print CSS rules and the generated HTML. No PDF renderer was available on this machine, documented in README.
- [x] Deployment: render.yaml for the Render free tier, requirements.txt, README deploy steps. Local run still one command.
- [x] README and Devpost draft rewritten in plain human voice, zero em dashes, only measured numbers.
- [x] Tests for the new features. 24 tests total, all passing.
- [x] Spec and design docs updated to match v2.

## Still open (needs a human)
- [ ] Public GitHub repo with /.kiro at the root (needs Arjun's GitHub sign-in; the browser task is waiting on it)
- [ ] Free Kiro credits, 4,000, request by Dec 1, 2026, 12:00 PM PT (Dec 2, 01:30 IST)
- [ ] Devpost registration and submission by Sat Dec 5, 2026, 03:30 IST
- [ ] Hosted app URL on Render (needs a Render account, free tier, no card)
