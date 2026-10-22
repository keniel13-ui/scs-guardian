"""Offline synthetic observation demo; no API, token, model or schedule."""
import difflib
import json
from test_guardian_watch import FakeAPI
from guardian_watch import collect, ScanError

api = FakeAPI()
before = collect(api, "demo", {})
print("SYNTHETIC FIXTURE — NOT A LIVE GUARDIAN INVESTIGATION")
print("1. Baseline: observed one repository; no change claimed.")
print("2. Unchanged:", before == collect(api, "demo", {}))
api.pulls.append(dict(number=7, user={"login": "contributor"}, state="open", html_url="https://example.invalid/pull/7"))
after = collect(api, "demo", {})
print("3. Same repo, new PR: snapshot changed.")
for line in difflib.unified_diff(json.dumps(before, indent=2).splitlines(), json.dumps(after, indent=2).splitlines(), fromfile="before", tofile="after"):
    print(line)
api.fail_collabs = True
try:
    collect(api, "demo", {})
except ScanError:
    print("4. Permission failure: scan failed, no successful snapshot.")
print("Human/model investigation of significance is a separate step; none ran here.")
