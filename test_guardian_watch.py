import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import guardian_watch as w


class FakeAPI:
    def __init__(self):
        self.pulls = []
        self.fail_collabs = False
        self.repos = [dict(name="project", owner={"login": "demo"}, private=False, fork=False, default_branch="main")]

    def pages(self, path):
        if path.startswith("/users/"):
            return copy.deepcopy(self.repos)
        if "/pulls?" in path:
            return copy.deepcopy(self.pulls)
        if "/collaborators?" in path and self.fail_collabs:
            raise w.ScanError("API HTTP 403; scan incomplete")
        return []

    def get(self, path, **kwargs):
        if "/branches/" in path:
            return {"commit": {"sha": "abc123"}}, ""
        if "/contents/" in path:
            return [], ""
        if "/actions/" in path:
            return {"total_count": 2, "workflow_runs": [
                dict(id=101, workflow_id=1, head_sha="abc123", status="completed", conclusion="failure"),
                dict(id=102, workflow_id=2, head_sha="abc123", status="completed", conclusion="success"),
            ]}, ""
        raise AssertionError(path)


class WatchTests(unittest.TestCase):
    def test_stable_snapshot(self):
        self.assertEqual(w.collect(FakeAPI(), "demo", {}), w.collect(FakeAPI(), "demo", {}))

    def test_second_pr_same_author_is_visible(self):
        api = FakeAPI()
        p = dict(number=1, user={"login": "contributor"}, state="open", html_url="https://example.invalid/1")
        api.pulls.append(p)
        first = w.collect(api, "demo", {})
        api.pulls.append(dict(p, number=2, html_url="https://example.invalid/2"))
        self.assertNotEqual(first, w.collect(api, "demo", {}))

    def test_green_workflow_does_not_hide_failure(self):
        ci = w.collect(FakeAPI(), "demo", {})["repos"][0]["ci"]
        self.assertEqual([r["conclusion"] for r in ci], ["failure", "success"])

    def test_permission_failure_is_not_empty_collaborators(self):
        api = FakeAPI(); api.fail_collabs = True
        with self.assertRaisesRegex(w.ScanError, "403"):
            w.collect(api, "demo", {})

    def test_private_and_foreign_repos_excluded(self):
        api = FakeAPI()
        api.repos += [dict(api.repos[0], name="private", private=True),
                      dict(api.repos[0], name="foreign", owner={"login": "other"})]
        self.assertEqual([r["name"] for r in w.collect(api, "demo", {})["repos"]], ["project"])

    def test_pagination_limit_is_failure(self):
        api = w.GitHub("FAKE", max_pages=2)
        api.get = lambda *a, **k: ([], '<https://api.github.com/next>; rel="next"')
        with self.assertRaisesRegex(w.ScanError, "pagination limit"):
            api.pages("/first")

    def test_redirect_denied(self):
        with self.assertRaisesRegex(w.ScanError, "redirect refused"):
            w.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")
        with self.assertRaisesRegex(w.ScanError, "destination refused"):
            w.GitHub("FAKE").get("https://example.invalid/path")

    def test_failed_main_does_not_emit_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d)/"config.json"
            log = Path(d)/"run.jsonl"
            cfg.write_text(json.dumps(dict(owner="demo", token_path="unused", run_log=str(log))))
            out, err = io.StringIO(), io.StringIO()
            with patch("sys.argv", ["watch", "--config", str(cfg)]), patch.object(w, "load_token", return_value="FAKE"), patch.object(w, "collect", side_effect=w.ScanError("failure")), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(w.main(), 1)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(json.loads(log.read_text())["status"], "error")


if __name__ == "__main__":
    unittest.main()
