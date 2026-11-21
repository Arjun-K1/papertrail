# Product steering

PaperTrail is for one person on a bad-internet day. It is not a news app, not a social feed, and not a productivity system with streaks.

- One page a day. If the digest does not fit on one printed page, cut stories, do not shrink the font.
- Days used and a streak counter are allowed now, added in the v2 upgrade. They are a counter only. No goals, no reminders, no gamification beyond the number.
- Plain language. Summaries are one sentence, under 25 words when Gemma writes them, two quoted sentences at most when the fallback writes them.
- Honest labels. Every summary says how it was made: gemma or extractive. Never present a quoted extract as a model summary.
- Never invent. The fallback quotes the source. Gemma is instructed to use only facts from the text, and answers under 4 words are rejected.
- Offline first. A digest built from yesterday's cache is better than no digest. The web UI works on localhost with no internet.
- No account, no tracking, no cloud. The only network call is the RSS fetch itself.
