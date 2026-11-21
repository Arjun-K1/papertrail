# Kiroween 2026 submission - PaperTrail (Frankenstein)

Category: Frankenstein
Bonus: Best Student Project (Frankenstein) - Arjun, 3rd year Computing and Data Science (Minor AI), SAI University, Chennai

## What it does

PaperTrail is a morning digest for days when the internet cannot be trusted. It fetches RSS overnight, summarises the top five stories on your own machine with a local Gemma 3 1B model, and prints one page: the news, three priorities, and the tasks for today.

It is built from three things that do not normally meet. RSS, which never died, it just lost the algorithm. A local open weight model, which summarises without sending anything to a server. And a printed page, which works when the router does not.

After the nightly cache, it needs no internet at all. The digest HTML is self contained, inline CSS, no external fonts or scripts, and it opens from disk. A service worker caches the app shell after the first visit. The stories themselves are plain JSON on disk, so a digest can be built after the connection drops.

The web UI is the daily surface. Add and remove feeds, with validation, a feed is only saved after it has been fetched and parsed once. Fetch on a schedule from Settings. Search the cache, mark stories read, save favourites, and those flags survive a refetch. Tasks take due dates. A Listen button reads the digest aloud in the browser. Dark and light follow the system setting.

## Why this problem, and why this shape

Internet shutdowns, low bandwidth, and screen fatigue are not edge cases in India. They are ordinary days. A news app that needs a live connection, an account, and a feed algorithm is three separate ways to fail on exactly those days.

RSS solves the account and the algorithm. It is a published feed, no login, no tracking, no ranking. Gemma running locally solves the cloud. Nothing about what you read leaves the laptop. Paper solves the connection. A printed page does not care whether the network is up.

Five stories is a deliberate limit, not a default. It fits one A4 page at 12pt with room for tasks, and it forces a choice about what matters. A digest that needs scrolling is a feed with better branding.

Every summary is labelled `gemma` or `extractive` in plain sight. That label is the trust mechanism. Without a model file, PaperTrail quotes the first two sentences of each story instead of paraphrasing. A thin story gives a thin summary, and the label says so. That is a better failure than a confident sentence the source never supported.

## Measured, not claimed

- Five sample stories, all five summarised by Gemma 3 1B, labelled `gemma`, in 13 seconds total. Verified 2026-11-22.
- Without a model file, the extractive fallback runs instead, labelled `extractive`. A missing model file is a tested case, not a crash.
- 24 tests, all passing. RSS parsing, feed validation, search, read and favourite flags surviving a refetch, tasks with due dates, streak counting, the print CSS rules, and the static files being local.
- Web server tested live. Home, feeds, tasks, settings, search, stats, and the speak endpoint all returned 200.

## How Kiro was used

- Spec driven development. The spec in `.kiro/specs/papertrail/` was written first, then implemented. The tasks file marks what is done.
- Steering. Product and tech steering kept the build stdlib only, free, and offline first.
- Hooks. A hook runs the test suite on save.
- Custom agent. The Digest Editor agent checks a generated digest against its source cache. Every story must exist in the cache. Every summary must be labelled. No summary may add a fact that is not in the source text.
- Kiro powers and MCP were not used. I am not claiming they were.

One plain note. Kiro itself was not installed on this build machine, so the spec, steering, hooks, and agent files were written by hand to match what was actually built, in the exact Kiro directory layout the rules require, with `/.kiro` at the repo root. If Kiro is used for the remaining work, that use will be recorded here too.

## Links (to add at submit time)

- GitHub repo: [public repo link, /.kiro at root]
- Working app: [hosted URL, Render free tier, or localhost demo instructions]
- Demo video: demo.mp4 in this repo, under 3 minutes, screen only, no face

## Limits, stated plainly

- Gemma summarisation needs a local GGUF model file. Without it you get extractive summaries. They are duller but still correct.
- RSS only covers feeds that publish RSS. Many sites do not, and PaperTrail does not scrape them. Scraping breaks on every redesign, and I would rather miss a site than maintain a scraper.
- The print layout fits one page for five stories and three tasks. More than that spills to page two, which is why the limits are what they are.
- There is no system TTS on the build machine. The Listen button uses the browser Web Speech API instead.
- The print output was checked by reading the print CSS rules and the generated HTML. There was no PDF renderer on the build machine to render it to PDF.
- It does not summarise video, audio, or paywalled pages. RSS is text, and the digest is built from that text.
