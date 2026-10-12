#!/usr/bin/env python3
"""Pull the last year of daily contribution counts for a GitHub user and write
data/contributions.json (the days plus streaks, totals and monthly sums).

The numbers come from the public calendar fragment GitHub serves for every
profile page, so no token is needed and the graph matches github.com exactly.

    python scripts/fetch_contributions.py             # username from profile.json
    python scripts/fetch_contributions.py <username>  # explicit username
"""
import datetime as dt
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "data", "contributions.json")


def resolve_username():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    if os.environ.get("GH_PROFILE_USER", "").strip():
        return os.environ["GH_PROFILE_USER"].strip()
    with open(os.path.join(ROOT, "profile.json"), encoding="utf-8") as f:
        return json.load(f)["github_username"]


def fetch_days(user):
    url = f"https://github.com/users/{user}/contributions"
    resp = requests.get(url, headers={"User-Agent": "profile-art/1.0 (profile README refresh)"}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tooltips = {t.get("for"): t.get_text(" ", strip=True) for t in soup.find_all("tool-tip")}
    days = []
    for cell in soup.select("td.ContributionCalendar-day[data-date]"):
        text = tooltips.get(cell.get("id"), "")
        match = re.match(r"(\d[\d,]*)\s+contribution", text)
        count = int(match.group(1).replace(",", "")) if match else 0
        days.append({
            "date": cell["data-date"],
            "count": count,
            "level": int(cell.get("data-level") or 0),
        })
    if not days:
        sys.exit(f"no calendar cells found for {user!r}: the user may not exist or GitHub changed its markup")
    days.sort(key=lambda d: d["date"])
    return days


def current_streak(days):
    i = len(days) - 1
    if days[i]["count"] == 0:
        i -= 1  # today is not over yet, so a quiet today does not end the streak
    end = i
    while i >= 0 and days[i]["count"] > 0:
        i -= 1
    length = end - i
    if length <= 0:
        return {"length": 0, "start": None, "end": None}
    return {"length": length, "start": days[i + 1]["date"], "end": days[end]["date"]}


def longest_streak(days):
    best = {"length": 0, "start": None, "end": None}
    run_start = None
    run = 0
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start = i
            run += 1
            if run > best["length"]:
                best = {"length": run, "start": days[run_start]["date"], "end": d["date"]}
        else:
            run = 0
    return best


def build(user, days):
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"] > 0)
    best_day = max(days, key=lambda d: d["count"])
    monthly = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]
    return {
        "username": user,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active,
        "avg_per_active_day": round(total / active, 1) if active else 0,
        "current_streak": current_streak(days),
        "longest_streak": longest_streak(days),
        "best_day": {"date": best_day["date"], "count": best_day["count"]},
        "monthly": [{"month": k, "total": v} for k, v in sorted(monthly.items())],
        "days": days,
    }


if __name__ == "__main__":
    user = resolve_username()
    data = build(user, fetch_days(user))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {OUT}: {data['total_contributions']} contributions in the last year, "
          f"current streak {data['current_streak']['length']}, longest {data['longest_streak']['length']}")
