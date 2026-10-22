#!/usr/bin/env python3
"""Portable observation source for Hermes monitor jobs. Python 3.10+.

No LLM call, scheduler installation, or GitHub mutation. stdout is a stable
snapshot on success; failures exit nonzero without publishing partial state.
"""
import argparse
import hashlib
import json
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
MAX_BODY = 4 * 1024 * 1024


class ScanError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ScanError("redirect refused; update the configured repository name")


class GitHub:
    def __init__(self, token, max_pages=20):
        self.token = token
        self.max_pages = max_pages
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, path, allow404=False):
        url = path if path.startswith("https://") else API + path
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "api.github.com":
            raise ScanError("non-GitHub API destination refused")
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "scs-guardian-watch",
        }, method="GET")
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    raise ScanError("API response exceeds size limit")
                return json.loads(raw), response.headers.get("Link", "")
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and allow404:
                return None, ""
            raise ScanError(f"API HTTP {exc.code}; scan incomplete") from None
        except (urllib.error.URLError, OSError, ValueError):
            raise ScanError("API transport or JSON error; scan incomplete") from None

    def pages(self, path):
        rows = []
        for _ in range(self.max_pages):
            body, links = self.get(path)
            if not isinstance(body, list):
                raise ScanError("expected API list")
            rows.extend(body)
            match = re.search(r'<([^>]+)>;\s*rel="next"', links)
            if not match:
                return rows
            path = match.group(1)
        raise ScanError("pagination limit reached; scan incomplete")


def collect(api, owner, config, now=None):
    now = now or datetime.now(timezone.utc)
    repos = api.pages(f"/users/{owner}/repos?type=owner&per_page=100")
    result = {"schema": 1, "owner": owner, "repos": [], "coverage": {
        "repos": "owned public non-forks", "pulls": "all states, paginated",
        "ci": "latest run per workflow in up to 100 returned runs on current HEAD",
        "workflow_404": "absent_or_unavailable, not proven absent",
        "between_polls": "transient events can be missed",
    }}
    for repo in sorted(repos, key=lambda r: r["name"]):
        if repo.get("private") is not False or repo.get("fork"):
            continue
        if repo.get("owner", {}).get("login", "").lower() != owner.lower():
            continue
        name, branch = repo["name"], repo["default_branch"]
        base = f"/repos/{owner}/{urllib.parse.quote(name, safe='')}"
        branch_info, _ = api.get(base + "/branches/" + urllib.parse.quote(branch, safe=""))
        head = branch_info["commit"]["sha"]
        pulls = api.pages(base + "/pulls?state=all&per_page=100")
        forks = api.pages(base + "/forks?per_page=100")
        workflows, _ = api.get(base + "/contents/.github/workflows?ref=" + head, allow404=True)
        if workflows is not None and not isinstance(workflows, list):
            raise ScanError("unexpected workflow directory response")
        collabs = api.pages(base + "/collaborators?per_page=100")
        runs, _ = api.get(base + "/actions/runs?" + urllib.parse.urlencode({
            "branch": branch, "head_sha": head, "per_page": 100,
        }))
        if not isinstance(runs, dict) or not isinstance(runs.get("workflow_runs"), list):
            raise ScanError("unexpected Actions response")
        latest = {}
        for run in runs["workflow_runs"]:
            if run.get("head_sha") != head:
                continue
            key = str(run["workflow_id"])
            rank = (run["id"], run.get("run_attempt", 1))
            if key not in latest or rank > latest[key][0]:
                latest[key] = (rank, {k: run.get(k) for k in (
                    "id", "workflow_id", "run_attempt", "head_sha", "status", "conclusion", "html_url")})
        result["repos"].append({
            "name": name, "branch": branch, "head": head,
            "pulls": sorted([{
                "number": p["number"], "author": p["user"]["login"],
                "state": p["state"], "merged_at": p.get("merged_at"),
                "head": p.get("head", {}).get("sha"), "url": p["html_url"],
            } for p in pulls], key=lambda p: p["number"]),
            "forks": sorted([{"id": f["id"], "owner": f["owner"]["login"]} for f in forks], key=lambda f: f["id"]),
            "workflows": None if workflows is None else sorted([
                {"path": w["path"], "sha": w["sha"]} for w in workflows
            ], key=lambda w: w["path"]),
            "collaborators": sorted([{
                "login": c["login"], "permissions": c.get("permissions", {}),
                "role_name": c.get("role_name"),
            } for c in collabs], key=lambda c: c["login"]),
            "ci": [latest[k][1] for k in sorted(latest)],
            "ci_sample_truncated": runs.get("total_count", 0) > len(runs["workflow_runs"]),
        })
    if config.get("board_path"):
        board = Path(config["board_path"]).expanduser()
        result["board"] = {"sha256": hashlib.sha256(board.read_bytes()).hexdigest(),
            "stale": now.timestamp() - board.stat().st_mtime > config.get("stale_hours", 12) * 3600}
    if config.get("ground_path"):
        marker = json.loads(Path(config["ground_path"]).expanduser().read_text())
        result["ground"] = marker["state"]
    return result


def load_token(path):
    path = Path(path).expanduser()
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ScanError("token file must not be readable or writable by group/others")
    token = path.read_text().strip()
    if not token.startswith("github_pat_") or any(c.isspace() for c in token) or "=" in token:
        raise ScanError("expected raw fine-grained GitHub token")
    return token


def receipt(path, status, repo_count=None):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
            "status": status, "repos": repo_count}) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path.home() / ".hermes/guardian/config.json"))
    args = parser.parse_args()
    config = None
    try:
        config = json.loads(Path(args.config).read_text())
        owner = config["owner"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner):
            raise ScanError("invalid GitHub owner")
        api = GitHub(load_token(config["token_path"]))
        output = collect(api, owner, config)
        receipt(config["run_log"], "ok", len(output["repos"]))
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        # Do not stringify arbitrary exceptions: they may contain request details.
        print("guardian scan failed: " + type(exc).__name__, file=sys.stderr)
        if config and config.get("run_log"):
            try:
                receipt(config["run_log"], "error")
            except OSError:
                print("error receipt could not be written", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
