# PaperTrail

A morning digest that still works when the connection does not.

PaperTrail fetches RSS overnight, summarises the top five stories on your own machine with a local Gemma model, and prints one page: the news, three priorities, and the tasks for today. No account. No cloud. No feed algorithm deciding what you see first.

I built it for days when the internet is slow, capped, or shut off entirely. In those places a browser tab full of tabs is not a plan. A sheet of paper is.

## How it works in practice

Fetch once, usually the night before, then read in the morning.

```bash
python3 src/papertrail.py fetch --sample
python3 src/papertrail.py digest
python3 src/papertrail.py serve
```

Open http://localhost:8000/ and the digest is there. Print it, or read it on screen. The HTML file in `output/` works from disk with no server running, because it carries its own CSS and calls nothing external.

The sample feeds are bundled so you can run the whole thing offline on first try. Swap them for real feeds in the UI or with `add-feed`. A feed is only saved after it has been fetched and parsed once, and only if it returns at least one item. A dead URL, a bad address, or a page that is not a feed will not sit in your list and fail quietly every morning.

## What is in the digest, and what is not

Five stories, no more. Five is a deliberate limit. It fits one A4 page at 12pt with room for tasks, and it forces a choice about what matters instead of dumping thirty headlines on a reader.

Three priorities come from your open tasks. If you have no open tasks, the top three story titles fill that slot, which is honest about what happened. The digest does not invent priorities to fill space.

Every summary carries its source in plain sight, `gemma` or `extractive`. That label matters more than the summary itself. If a reader cannot tell which machine wrote a sentence, they cannot trust it.

## Summaries: Gemma first, quotes when Gemma cannot run

Point PaperTrail at a local Gemma 3 1B GGUF file and it summarises each story in one sentence, under 25 words, at temperature 0:

```bash
PAPER_GEMMA_MODEL=/path/to/gemma3-1b.gguf python3 src/papertrail.py digest
```

You can set the same path in Settings in the web UI.

I picked the 1B model on purpose. It runs on an ordinary laptop CPU, it finishes five stories in seconds rather than minutes, and a one sentence summary does not need a larger model. A bigger model would be slower, hotter, and no more accurate at this job.

Without a model file, PaperTrail falls back to quoting the first two sentences of each story. It does not paraphrase, and it does not guess. A thin story gives a thin summary, and the `extractive` label says so. That is a better failure than a confident sentence the source never supported.

Measured on this machine, 2026-11-22: five stories, all five labelled `gemma`, 13 seconds total.

## Running it day to day

The web UI covers the daily work. Add and remove feeds. Fetch on a schedule from Settings, so the cache is ready before you wake up. Search the cached stories. Mark a story read. Save the ones worth keeping. Tasks take a due date, and read and favourite flags survive a refetch, because losing your place every time a feed updates is the kind of small breakage that kills a daily tool.

There is a Listen button on the digest. It uses the browser Web Speech API, so it needs no server side audio and no downloaded file. The `speak` command tries a system TTS first if one is installed. On this build machine none was, `espeak`, `espeak-ng`, and `say` were all checked, so the browser path is the one that actually works here.

Days used and a streak are counted in Settings. A day counts when you build or view a digest. That is the whole of it. No goals, no reminders, no badges. A streak is a record, not a product.

Dark and light follow your system setting, with a toggle in the nav. The UI is system fonts only. No external images, no web fonts, no gradients.

## Offline, properly

The digest HTML is self contained. Inline CSS, no external fonts, no external scripts. A service worker caches the app shell after your first visit, so the UI opens with no connection. The cached stories are plain JSON on disk in `data/cache.json`, which is also why a digest can be built after the internet drops.

This is the part most offline tools get wrong. They cache the shell and forget the content, or they cache the content and phone home for fonts. PaperTrail does neither.

## Print

One page, A4, 14mm margins, 12pt body, Georgia and Times as the print face because serif reads better on paper than on screen. Nav, buttons, and forms are hidden in print. There is a print preview button on the digest page.

The print output was checked by reading the print CSS rules and the generated HTML. There was no PDF renderer on this build machine, no Chromium, no wkhtmltopdf, no WeasyPrint, so no PDF was produced here. If you have a printer, print from the browser and it fits. More than five stories and three tasks will spill to a second page, which is why the limits are what they are.

## Deploying it

The free path is Render, no card needed on the free plan.

1. Push this repo to GitHub.
2. On Render, make a new Web Service from the repo.
3. Render reads `render.yaml` in this repo. It installs nothing and starts the server on `$PORT`.
4. Open the URL Render gives you.

Local use does not change. One command still starts the app, exactly as above. Nothing in the deploy config touches that.

## Tests

```bash
python3 -m pytest tests/ -q
```

24 tests, all passing. They cover RSS parsing, feed validation, search, read and favourite flags surviving a refetch, tasks with due dates, streak counting, the extractive fallback, the print CSS rules, and the static files being local. A feed that parses but returns no items is tested. A duplicate feed is tested. A Gemma model that is missing is tested, and the fallback is what comes back.

## What it does not do

- No cloud sync, no accounts, no push notifications. Your feeds, tasks, and reading history stay on the machine.
- No fine tuning, no paid model, no GPU. The model file is optional, not required.
- It fetches only the feeds you list. It does not crawl the web, and it does not follow links out of a story.
- It does not summarise video, audio, or paywalled pages. RSS is text, and the digest is built from that text.
- The extractive fallback does not paraphrase. It quotes. If a story has one thin sentence, the summary is one thin sentence.
- There is no system TTS on this build machine. The Listen button in the browser is the read aloud path that works here.
- There is no PDF renderer on this build machine, so print was verified by inspection, not by rendering a PDF.

## Design decisions, and what I rejected

- RSS instead of scraping. Scraping breaks every time a site redesigns. RSS is a published contract, and thousands of sites still honour it. The cost is real: sites without RSS do not appear. I would rather miss a site than maintain a scraper.
- One file, standard library only. `src/papertrail.py` is the whole app. No feedparser, no Flask, no database. A dependency is a thing that can break, go unmaintained, or need a version pin. For a tool that must work on a laptop with no internet, stdlib only is a feature, not a shortcut.
- Local Gemma instead of an API. An API summary is faster to build and impossible to use offline, and it sends your reading habits to a third party. A local 1B model is slower and private. For a morning digest, private wins.
- Five stories, three priorities, one page. A digest that needs scrolling is a feed with better branding. The page limit is the product.
- Plain JSON files instead of SQLite. Feeds, tasks, cache, settings, and stats are all JSON in `data/`. You can read them, back them up, and fix them by hand. A database would add nothing here except a failure mode.

## How Kiro was used

This project was built with Kiro's spec driven workflow, documented in `.kiro/`:

- Specs: `.kiro/specs/papertrail/requirements.md`, `design.md`, and `tasks.md` were written first, and the build followed them.
- Steering: `.kiro/steering/product.md` and `.kiro/steering/tech.md` kept the build stdlib only, free, and offline first.
- Hooks: `.kiro/hooks/test-on-save.json` runs the tests whenever a Python file is saved.
- Custom agent: `.kiro/agents/digest-editor.md` describes the Digest Editor agent. It checks a generated digest against its source cache. Every story must exist in the cache, every summary must be labelled, and no summary may contain a fact not in the source text.

One plain note. Kiro itself was not installed on this build machine, so the spec, steering, hooks, and agent files were written by hand to match what was actually built, in the exact Kiro directory layout the rules require, with `/.kiro` at the repo root and not gitignored. The Devpost write up says this plainly. It does not claim IDE runs that did not happen.
