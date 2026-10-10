# github-watch

Daily check (09:30 Mauritius) of:
- LF-Decentralized-Trust/lab-proposals #2
- Agent-Authority-Conformance/aps-conformance-suite #121
- x402-foundation/tsc #4
- x402-foundation/x402 #2887
- x402-foundation/x402 #3220 (PR: conversation comments, reviews, review comments, merge state)
- magentixai/axes - every issue and PR (new items, state changes, new comments) plus stars, forks, watchers
- giskard09/action-ref-conformance (branches, tags, commits)

`watch.py` diffs live GitHub API data against `state.json`. Each run writes `last-report.json` and `reports/<timestamp>.json`, then commits.
New items are baselined silently on their first run (no flood of old comments).
State only advances for items fetched successfully, so a failed or missed run is caught up by the next one. A failed run marks the workflow red and GitHub emails you.
Run on demand: Actions tab -> daily-watch -> Run workflow.
