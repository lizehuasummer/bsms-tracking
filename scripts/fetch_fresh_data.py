"""
重新拉取 GitLab issues + notes 数据，保存到缓存。
用法: python fetch_fresh_data.py
"""
import json
import os
import sys
import time
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
urllib3.disable_warnings()

GITLAB_URL = "https://gitlab.stpass.com"
GITLAB_TOKEN = "glpat-rO7mGLMblvELQu1iJbGMY286MQp1OnEH.01.0w0x3iets"
PROJECT_ID = 4
CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
ISSUES_CACHE = os.path.join(CACHE_DIR, "gitlab_issues_cache.json")
NOTES_CACHE = os.path.join(CACHE_DIR, "gitlab_notes_cache.json")
ALL_ISSUES_CACHE = os.path.join(CACHE_DIR, "gitlab_all_issues_cache.json")
CONCURRENT_WORKERS = 10

session = requests.Session()
session.headers.update({"Private-Token": GITLAB_TOKEN})
session.verify = False


def fetch_all_issues(label, state="all"):
    all_issues = []
    page = 1
    while True:
        r = session.get(
            f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues",
            params={"labels": label, "state": state, "per_page": 100, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        all_issues.extend(data)
        total_pages = int(r.headers.get("X-Total-Pages", "1"))
        print(f"  {label} page {page}/{total_pages} ({len(all_issues)}/{r.headers.get('X-Total', '?')})")
        if page >= total_pages:
            break
        page += 1
    return all_issues


def fetch_issue_notes(iid):
    key = str(iid)
    try:
        all_notes = []
        page = 1
        while True:
            r1 = session.get(
                f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues/{iid}/notes",
                params={"per_page": 100, "sort": "asc", "order_by": "created_at", "page": page},
                timeout=15,
            )
            r1.raise_for_status()
            data = r1.json()
            if not data:
                break
            all_notes.extend(data)
            total_pages = int(r1.headers.get("X-Total-Pages", "1"))
            if page >= total_pages:
                break
            page += 1

        all_events = []
        page = 1
        while True:
            r2 = session.get(
                f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues/{iid}/resource_label_events",
                params={"per_page": 100, "page": page},
                timeout=15,
            )
            r2.raise_for_status()
            data = r2.json()
            if not data:
                break
            all_events.extend(data)
            total_pages = int(r2.headers.get("X-Total-Pages", "1"))
            if page >= total_pages:
                break
            page += 1

        return key, {"notes": all_notes, "label_events": all_events}
    except Exception as e:
        print(f"  ERR iid {iid}: {e}")
        return key, {"notes": [], "label_events": []}


# ===== Step 1: Fetch all issues =====
print("=" * 60)
print("[1] Fetching issues...")
func_issues = fetch_all_issues("Function::dev")
print(f"  Function::dev: {len(func_issues)}")
bug_issues = fetch_all_issues("Bug::dev")
print(f"  Bug::dev: {len(bug_issues)}")

with open(ISSUES_CACHE, "w", encoding="utf-8") as f:
    json.dump({"functiondev": func_issues, "bugdev": bug_issues}, f, ensure_ascii=False)
print(f"  Saved issues cache: {ISSUES_CACHE}")

# Deduplicate by iid
seen = set()
all_issues = []
for issue in func_issues + bug_issues:
    iid = issue["iid"]
    if iid not in seen:
        seen.add(iid)
        all_issues.append(issue)
with open(ALL_ISSUES_CACHE, "w", encoding="utf-8") as f:
    json.dump(all_issues, f, ensure_ascii=False)
print(f"  All issues (deduplicated): {len(all_issues)} -> {ALL_ISSUES_CACHE}")

# ===== Step 2: Fetch notes for ALL issues (fresh) =====
print(f"\n[2] Fetching notes for {len(all_issues)} issues...")
notes_cache = {}
fetched = 0
t0 = time.time()
with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
    futures = {executor.submit(fetch_issue_notes, issue["iid"]): issue["iid"] for issue in all_issues}
    for future in as_completed(futures):
        key, data = future.result()
        notes_cache[key] = data
        fetched += 1
        if fetched % 200 == 0:
            elapsed = time.time() - t0
            eta = elapsed / fetched * (len(all_issues) - fetched)
            print(f"  Progress: {fetched}/{len(all_issues)} ({elapsed:.0f}s elapsed, ETA {eta:.0f}s)")
            with open(NOTES_CACHE, "w", encoding="utf-8") as f:
                json.dump(notes_cache, f, ensure_ascii=False)

with open(NOTES_CACHE, "w", encoding="utf-8") as f:
    json.dump(notes_cache, f, ensure_ascii=False)
print(f"  Done. {len(notes_cache)} notes entries cached. ({time.time()-t0:.0f}s)")

# ===== Summary =====
print("\n" + "=" * 60)
print("Summary:")
func_open = sum(1 for i in func_issues if i["state"] == "opened")
func_closed = sum(1 for i in func_issues if i["state"] == "closed")
bug_open = sum(1 for i in bug_issues if i["state"] == "opened")
bug_closed = sum(1 for i in bug_issues if i["state"] == "closed")
print(f"  Function::dev: {len(func_issues)} (open={func_open}, closed={func_closed})")
print(f"  Bug::dev:      {len(bug_issues)} (open={bug_open}, closed={bug_closed})")
print(f"  All (dedup):   {len(all_issues)}")
print(f"  Notes entries: {len(notes_cache)}")
print("\nFetch complete!")
