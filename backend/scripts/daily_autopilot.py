import json
import os
import sys
import urllib.error
import urllib.request

base_url = os.environ["AUTOPILOT_API_URL"].rstrip("/")
token = os.environ["AUTOPILOT_TOKEN"]
request = urllib.request.Request(
    base_url + "/api/autopilot/run",
    data=b"{}",
    headers={"Content-Type": "application/json", "X-Autopilot-Token": token},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
        print(json.dumps({"result": "success", **payload}))
except urllib.error.HTTPError as exc:
    print(f"Autopilot API returned HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
    raise SystemExit(1)
except Exception as exc:
    print(f"Autopilot run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    raise SystemExit(1)
