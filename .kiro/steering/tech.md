# Tech steering

- Python standard library only for the app itself. The only optional dependency is llama-cpp, and only for the Gemma path, imported lazily.
- One file for the app: src/papertrail.py. If a feature does not fit cleanly in that file, it is probably too big for this project.
- No paid APIs, no API keys, no card, no GPU assumed. A run with no model file set must work end to end.
- Data is plain files: JSON for feeds, cache, and tasks; HTML and text for digests. No database.
- Tests are plain asserts with pytest, in tests/test_papertrail.py. No network in tests.
- Never copy code verbatim from an earlier project. PaperTrail is a new project, built Nov 22 - Dec 5, 2026, for Kiroween.
- Git: local repo, MIT licence, model files and cache excluded via .gitignore.
