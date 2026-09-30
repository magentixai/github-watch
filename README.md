# github-watch

Daily check (11:50 Mauritius) of:
- LF-Decentralized-Trust/lab-proposals #2
- Agent-Authority-Conformance/aps-conformance-suite #121
- giskard09/action-ref-conformance (branches, tags, commits)

`watch.py` diffs live GitHub API data against `state.json`. Each run writes `last-report.json` and `reports/<timestamp>.json`, then commits.
State only advances for items fetched successfully, so a failed or missed run is caught up by the next one. A failed run marks the workflow red and GitHub emails you.
Run on demand: Actions tab -> daily-watch -> Run workflow.
