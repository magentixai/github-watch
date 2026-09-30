#!/usr/bin/env python3
"""GitHub watch: compares live state with state.json, prints a JSON report.
Usage: python3 watch.py            -> check, print report, save new state
       python3 watch.py --dry-run  -> check and print, don't save
State is saved only for items that were fetched successfully, so failures are caught up next run."""
import json, os, sys, urllib.request, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
ISSUES = ["LF-Decentralized-Trust/lab-proposals#2",
          "Agent-Authority-Conformance/aps-conformance-suite#121"]
REPO = "giskard09/action-ref-conformance"
def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "martin-watch"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok: req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
def paged(url):
    out, page = [], 1
    while True:
        d = get(f"{url}{'&' if '?' in url else '?'}per_page=100&page={page}")
        out += d
        if len(d) < 100: return out
        page += 1
now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
state = json.load(open(STATE)) if os.path.exists(STATE) else {"issues": {}, "repo": {}}
report = {"checked_at": now, "previous_check": state.get("last_checked"), "changes": [], "failures": [], "summary": {}}
new_state = json.loads(json.dumps(state))
for key in ISSUES:
    repo, num = key.split("#")
    try:
        meta = get(f"https://api.github.com/repos/{repo}/issues/{num}")
        comments = paged(f"https://api.github.com/repos/{repo}/issues/{num}/comments")
        old = state["issues"].get(key, {})
        seen = set(old.get("comment_ids", []))
        new = [c for c in comments if c["id"] not in seen] if old else []
        for c in new:
            report["changes"].append({"item": key, "type": "comment", "author": c["user"]["login"],
                "at": c["created_at"], "url": c["html_url"], "text": c["body"][:600]})
        if old and old.get("state") != meta["state"]:
            report["changes"].append({"item": key, "type": "state", "from": old.get("state"), "to": meta["state"],
                "reason": meta.get("state_reason"), "url": meta["html_url"]})
        if old and old.get("title") != meta["title"]:
            report["changes"].append({"item": key, "type": "title", "to": meta["title"], "url": meta["html_url"]})
        last = comments[-1] if comments else None
        new_state["issues"][key] = {"title": meta["title"], "state": meta["state"], "state_reason": meta.get("state_reason"),
            "labels": [l["name"] for l in meta.get("labels", [])], "comments": len(comments),
            "comment_ids": [c["id"] for c in comments], "updated_at": meta["updated_at"],
            "last_comment": {"author": last["user"]["login"], "at": last["created_at"], "url": last["html_url"],
                             "text": last["body"][:600]} if last else None}
        report["summary"][key] = {k: v for k, v in new_state["issues"][key].items() if k != "comment_ids"}
    except Exception as e:
        report["failures"].append({"item": key, "error": repr(e)})
try:
    branches = {"refs/heads/" + b["name"]: b["commit"]["sha"] for b in paged(f"https://api.github.com/repos/{REPO}/branches")}
    tags = {"refs/tags/" + t["name"]: t["commit"]["sha"] for t in paged(f"https://api.github.com/repos/{REPO}/tags")}
    refs = {**branches, **tags}
    old_refs = state["repo"].get("refs", {})
    if old_refs:
        for r, sha in refs.items():
            if r not in old_refs:
                report["changes"].append({"item": REPO, "type": "new_ref", "ref": r, "sha": sha[:7]})
            elif old_refs[r] != sha:
                ch = {"item": REPO, "type": "ref_moved", "ref": r, "from": old_refs[r][:7], "to": sha[:7]}
                try:
                    cmp = get(f"https://api.github.com/repos/{REPO}/compare/{old_refs[r]}...{sha}")
                    ch["commits"] = [{"sha": c["sha"][:7], "author": c["commit"]["author"]["name"], "at": c["commit"]["author"]["date"],
                                      "msg": c["commit"]["message"].splitlines()[0]} for c in cmp.get("commits", [])]
                    ch["files"] = [{"file": f["filename"], "status": f["status"]} for f in cmp.get("files", [])]
                    ch["url"] = cmp.get("html_url")
                except Exception as e:
                    ch["compare_error"] = repr(e)
                report["changes"].append(ch)
        for r in old_refs:
            if r not in refs: report["changes"].append({"item": REPO, "type": "ref_deleted", "ref": r})
    head = get(f"https://api.github.com/repos/{REPO}/commits/main")
    new_state["repo"] = {"refs": refs, "main_latest": {"sha": head["sha"][:7], "at": head["commit"]["author"]["date"],
                          "msg": head["commit"]["message"].splitlines()[0]}}
    report["summary"][REPO] = new_state["repo"]
except Exception as e:
    report["failures"].append({"item": REPO, "error": repr(e)})
report["first_run"] = not state.get("last_checked")
if not report["failures"]:
    new_state["last_checked"] = now
if "--dry-run" not in sys.argv:
    json.dump(new_state, open(STATE, "w"), indent=1)
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    out = json.dumps(report, indent=1)
    open(os.path.join(HERE, "last-report.json"), "w").write(out)
    open(os.path.join(HERE, "reports", now.replace(":", "") + ".json"), "w").write(out)
print(json.dumps(report, indent=1))
sys.exit(1 if report["failures"] else 0)
