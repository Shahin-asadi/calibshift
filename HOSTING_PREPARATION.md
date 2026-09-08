# Local hosting preparation — 2026-09-09

These are uncommitted local changes on top of 0.5.2. No new release or hosted service has been created. [Web access](WEB_ACCESS.md) gives the owner-controlled deployment steps.

- Runtime-only `requirements.txt` uses the existing tested constraints and installs the package without development extras.
- The Streamlit configuration sets a 50 MB upload limit and disables usage statistics. Security defaults are preserved.
- The workbench accurately describes local or server processing; hosted uploads are not described as staying on the visitor's computer. Scientific calculation modules are unchanged.
- README download/run/report buttons, current CI badge, server guidance and a manual test trigger make the entry points explicit. Generated reports are marked as generated in `.gitattributes` and remain versioned.

## Checks of this local snapshot

Complete Windows Python 3.14.7 suite: **81 passed**, including the new processing-notice regression. Ruff lint and format checks passed. [Full JUnit](validation/hosting_preparation/windows314.xml) and [source/test/configuration hashes](validation/hosting_preparation/record.json) identify the checked files.

The app started successfully on localhost and its revised notice was visible in Chrome. Runtime requirement resolution passed a pip dry-run in the existing QA environment; this is not a fresh cloud installation. The earlier complete import/export regressions ran as part of the suite.

**NOT_RUN:** actual Streamlit hosting, public URL, cloud resource/concurrent-user tests, and remote CI for these uncommitted changes. The prior successful published-commit CI runs remain separately documented in [CI status](CI_STATUS.md). No new claim of external scientific validation is made.

The original 0.5.2 ZIPs and their frozen evidence remain unchanged. This local snapshot has different workbench/test/configuration bytes; use the new record above when reviewing it.
