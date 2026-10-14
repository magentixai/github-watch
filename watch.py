#!/usr/bin/env python3
"""GitHub watch: compares live state with state.json, prints a JSON report.
Usage: python3 watch.py            -> check, print report, save new state
       python3 watch.py --dry-run  -> check and print, don't save
State is saved only for items that were fetched successfully, so failures are caught up next run."""
import json, os, sys, urllib.request, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
ISSUES = ["LF-Decentralized-Trust/lab-proposals#2",
          "Agent-Authority-Conformance/aps-conformance-suite#121",
          "x402-foundation/tsc#4",          # evidence-record WG chartering
          "x402-foundation/x402#2887",      # correctness / evidence thread
          "x402-foundation/x402#3220"]      # authority extension PR (reviews tracked too)
REPO = "giskard09/action-ref-conformance"
WATCH_REPOS = ["magentixai/axes"]           # every issue/PR, comment, state change, plus stars/forks
AXES_BACKFILL_SINCE = "2026-10-10T21:54:27+00:00"  # first AXES baseline; one-time catch-up of missed comments
def ts(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
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
        if meta.get("pull_request"):
            pr = get(f"https://api.github.com/repos/{repo}/pulls/{num}")
            for rv in paged(f"https://api.github.com/repos/{repo}/pulls/{num}/reviews"):
                if rv.get("submitted_at"):
                    comments.append({"id": rv["id"], "user": rv["user"], "created_at": rv["submitted_at"],
                                     "html_url": rv["html_url"], "body": f"[review: {rv['state']}] " + (rv.get("body") or "")})
            for rc in paged(f"https://api.github.com/repos/{repo}/pulls/{num}/comments"):
                comments.append({"id": rc["id"], "user": rc["user"], "created_at": rc["created_at"],
                                 "html_url": rc["html_url"], "body": f"[review comment on {rc.get('path')}] " + (rc.get("body") or "")})
            comments.sort(key=lambda c: c["created_at"])
            if pr.get("merged"): meta["state"] = "merged"
        old = state["issues"].get(key, {})
        seen = set(old.get("comment_ids", []))
        new = [c for c in comments if c["id"] not in seen] if old else []
        for c in new:
            report["changes"].append({"item": key, "type": "comment", "author": c["user"]["login"],
                "at": c["created_at"], "url": c["html_url"], "text": (c["body"] or "")[:600]})
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
                             "text": (last["body"] or "")[:600]} if last else None}
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
state.setdefault("repos", {}); new_state.setdefault("repos", {})
for r in WATCH_REPOS:
    try:
        old = state["repos"].get(r, {})
        info = get(f"https://api.github.com/repos/{r}")
        items = paged(f"https://api.github.com/repos/{r}/issues?state=all")
        cur = {str(i["number"]): {"title": i["title"], "state": i["state"], "pr": bool(i.get("pull_request")),
               "comments": i["comments"], "author": i["user"]["login"], "url": i["html_url"]} for i in items}
        # Comments are diffed by id (like ISSUES above), not by a server-side ?since= filter:
        # the unencoded "+00:00" in since= turned into a space and GitHub silently dropped every comment.
        comments = paged(f"https://api.github.com/repos/{r}/issues/comments")
        if old:
            for n, i in cur.items():
                o = old["items"].get(n)
                if not o:
                    report["changes"].append({"item": f"{r}#{n}", "type": "new_pr" if i["pr"] else "new_issue",
                        "author": i["author"], "title": i["title"], "url": i["url"]})
                elif o["state"] != i["state"]:
                    report["changes"].append({"item": f"{r}#{n}", "type": "state", "from": o["state"], "to": i["state"], "url": i["url"]})
            if "comment_ids" in old:
                seen = set(old["comment_ids"])
                fresh = [c for c in comments if c["id"] not in seen]
            else:  # first run after the fix: catch up on comments missed since AXES was added
                fresh = [c for c in comments if ts(c["created_at"]) > ts(AXES_BACKFILL_SINCE)]
            for c in fresh:
                report["changes"].append({"item": f"{r}#{c['issue_url'].rsplit('/',1)[1]}", "type": "comment",
                        "author": c["user"]["login"], "at": c["created_at"], "url": c["html_url"], "text": (c["body"] or "")[:600]})
            for k in ("stargazers_count", "forks_count", "subscribers_count"):
                if old.get(k) is not None and old[k] != info.get(k):
                    report["changes"].append({"item": r, "type": "count", "field": k, "from": old[k], "to": info.get(k)})
        new_state["repos"][r] = {"checked": now, "items": cur, "comment_ids": [c["id"] for c in comments], "stargazers_count": info.get("stargazers_count"),
            "forks_count": info.get("forks_count"), "subscribers_count": info.get("subscribers_count"),
            "open_issues_count": info.get("open_issues_count"), "pushed_at": info.get("pushed_at")}
        report["summary"][r] = {k: v for k, v in new_state["repos"][r].items() if k not in ("items", "comment_ids")} | {"issues_tracked": len(cur)}
    except Exception as e:
        report["failures"].append({"item": r, "error": repr(e)})
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
