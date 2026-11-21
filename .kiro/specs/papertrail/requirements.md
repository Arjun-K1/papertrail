# PaperTrail - Requirements

## Problem
On a low-bandwidth day, during an internet shutdown, or on a screen-fatigue day, a person loses two things at once: the news and the plan for the day. Both live in apps that need a connection, an account, and a feed algorithm. That is three separate ways to fail on exactly the days the tool is needed most. PaperTrail removes all three. Fetch once, read on paper, no account, no algorithm, no live connection after the cache.

## Users
One person, solo, on an ordinary laptop, with unreliable internet. No team, no server, no account.

## Requirements
1. Fetch RSS feeds with the Python standard library only (xml.etree, urllib). No feedparser, no account, no API key.
2. Cache fetched items on disk, so a digest can be built after the internet drops.
3. Summarise each story in one plain sentence. Try a local Gemma model (llama-cpp, GGUF file, env PAPER_GEMMA_MODEL) first; if the model is missing, slow, or returns junk, fall back to extractive summary, which quotes the first sentences and never invents facts.
4. Label every summary in the digest with its source: "gemma" or "extractive".
5. Tasks live in a plain JSON file. Add and list tasks from the CLI and the web UI.
6. A digest contains: top 5 stories, 3 priorities, today's tasks, the fetch time.
7. Digest output is a printable one-page HTML file with print CSS and a plain text version, in output/digest-YYYY-MM-DD.html and .txt.
8. Web UI on localhost:8000: add a feed, add a task, fetch, view today's digest, print button. No external images, no external scripts.
9. All work is free, offline-capable, and private: no data leaves the machine except the RSS fetch itself.
10. Tests cover RSS parsing, extractive summarisation, digest generation, and task handling. All tests pass before submission.

## Non-goals
- No cloud sync, no accounts, no push notifications.
- No fine-tuning, no paid model, no GPU.
- No face, no camera, no microphone in the demo.
