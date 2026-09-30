"""Save a snapshot of the analytics API for the frontend's offline demo mode.

    # backend running on 127.0.0.1:8000, demo accounts created (python -m app.cli.demo_users)
    $env:DEMO_USER_PASSWORD = "<the demo password>"
    ..\\backend\\.venv\\Scripts\\python.exe scripts\\snapshot_demo.py

Writes src/lib/demo/snapshot.json. Everything in it comes from the SYNTHETIC demo world, and
the UI always shows it with a "Demo data" badge. Re-run after regenerating the synthetic data.
"""

import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("KAUSHALSETU_API", "http://127.0.0.1:8000")
OUT = pathlib.Path(__file__).resolve().parents[1] / "src/lib/demo/snapshot.json"
EMAIL = os.environ.get("DEMO_USER_EMAIL", "admin@kaushalsetu.example")


def call(path: str, token: str | None = None, body: dict | None = None):
    request = urllib.request.Request(BASE + path, method="POST" if body else "GET")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, json.dumps(body).encode() if body else None) as r:
        return json.loads(r.read())


def main() -> None:
    password = os.environ["DEMO_USER_PASSWORD"]
    token = call("/api/v1/auth/login", body={"email": EMAIL, "password": password})["access_token"]

    def get(path: str, **params: str):
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        return call(f"/api/v1{path}" + (f"?{query}" if query else ""), token)

    latest = get("/analytics/demand")
    quarter = latest["quarter"]
    quarters = [f"{y}Q{q}" for y in range(2025, 2027) for q in range(1, 5)]
    quarters = [q for q in quarters if "2025Q2" <= q <= quarter]
    districts = get("/districts")
    district_mismatch = {}
    for d in districts:
        item = get(f"/analytics/districts/{d['code']}/mismatch")
        district_mismatch[d["code"]] = {k: v for k, v in item.items() if k != "roles"}
    role_history, skill_history = [], []
    for q in quarters:
        for item in get("/analytics/demand", quarter=q)["items"]:
            postings = next((c for c in item["components"] if c["name"] == "postings"), {})
            role_history.append(
                {
                    "district": item["district"]["code"],
                    "role": item["role"]["code"],
                    "quarter": q,
                    "score": item["demand_score"],
                    "postings": (postings.get("observed") or {}).get("postings_this_quarter"),
                }
            )
        for item in get("/analytics/demand", quarter=q, level="skill")["items"]:
            skill_history.append(
                {
                    "district": item["district"]["code"],
                    "skill": item["skill"]["code"],
                    "quarter": q,
                    "score": item["demand_score"],
                    "mentions": item["mention_count"],
                }
            )
    snapshot = {
        "about": (
            "Snapshot of the KaushalSetu analytics API over the SYNTHETIC demo world. "
            "Not real labour-market data and not official statistics."
        ),
        "pipeline_run_id": latest["pipeline_run_id"],
        "computed_at": latest["computed_at"],
        "quarter": quarter,
        "quarters": quarters,
        "districts": districts,
        "role_demand": latest["items"],
        "skill_demand": get("/analytics/demand", level="skill")["items"],
        "mismatch": get("/analytics/mismatch")["items"],
        "district_mismatch": district_mismatch,
        "supply_course": get("/analytics/supply", group_by="course")["items"],
        "supply_role": get("/analytics/supply")["items"],
        "role_history": role_history,
        "skill_history": skill_history,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(snapshot, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not reach the API at {BASE}: {exc}") from None
