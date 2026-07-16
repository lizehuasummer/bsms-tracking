"""
寮€鍙戞瘡鏃ユ眹鎬荤湅鏉?鈥?淇鐗?淇鐐?
1. G鍒? 鍙粺璁?Function::dev issue 鐨勬祴璇曚腑鏁伴噺
2. I-N鍒? 缁熻 Bug::dev + Priority issue 鐨?set status to 娴嬭瘯涓?浜嬩欢锛堜笉鏄痩abel娣诲姞锛?3. Q-S鍒? 鍚屼笂锛屾寜鍓嶇/鍚庣/鍏ㄦ爤鍒嗙被
"""
import json, os, re, sys, datetime, openpyxl
from collections import defaultdict

CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
EXCEL_PATH = r"D:\Users\LZH\Documents\opencode\bsms_tracking\銆愪氦浠楬K銆態SMS椤圭洰鏁翠綋杩涘害璁″垝 (鏇存柊涓?20260702澶囦唤_new2.xlsx"
SCRIPTS_DIR = r"D:\Users\LZH\Documents\opencode\bsms_tracking\scripts"

sys.path.insert(0, SCRIPTS_DIR)
from gitlab_users import GITLAB_USERS

FRONTEND_USERS = set(u[3] for u in GITLAB_USERS if u[0] == "绯荤粺寮€鍙戠粍锛堝墠绔級")
BACKEND_USERS = set(u[3] for u in GITLAB_USERS if u[0] == "绯荤粺寮€鍙戠粍锛堝悗绔級")

def date_str(t):
    if not t: return None
    return t[:10]

def parse_notes(notes):
    result = []
    for n in notes:
        if not n.get("system"): continue
        result.append({
            "time": n.get("created_at", ""),
            "user": n.get("author", {}).get("username", ""),
            "body": n.get("body", ""),
        })
    result.sort(key=lambda x: x["time"])
    return result

def parse_label_events(events):
    result = []
    for ev in events:
        lbl = ev.get("label")
        result.append({
            "time": ev.get("created_at", ""),
            "user": (ev.get("user") or {}).get("username", ""),
            "label": (lbl or {}).get("name", "") if lbl else "",
            "action": ev.get("action", ""),
        })
    result.sort(key=lambda x: x["time"])
    return result

# Load data
print("Loading data...")
with open(os.path.join(CACHE_DIR, "gitlab_all_issues_cache.json"), "r", encoding="utf-8") as f:
    all_issues = json.load(f)
with open(os.path.join(CACHE_DIR, "gitlab_notes_cache.json"), "r", encoding="utf-8") as f:
    notes_cache = json.load(f)

print(f"Issues: {len(all_issues)}, Notes: {len(notes_cache)}")
print(f"Frontend: {len(FRONTEND_USERS)} users, Backend: {len(BACKEND_USERS)} users")

# Build per-issue data
print("Building per-issue activity...")
all_dates = set()
issue_data = []

for issue in all_issues:
    iid = issue["iid"]
    key = str(iid)
    cdata = notes_cache.get(key, {"notes": [], "label_events": []})
    
    sys_notes = parse_notes(cdata.get("notes", []))
    label_events = parse_label_events(cdata.get("label_events", []))
    
    labels = set(issue.get("labels", []))
    created = issue.get("created_at", "")
    closed = issue.get("closed_at")
    
    if created:
        all_dates.add(date_str(created))
    
    all_activities = []
    for n in sys_notes:
        all_activities.append({"time": n["time"], "user": n["user"], "type": "note", "body": n["body"]})
    for ev in label_events:
        all_activities.append({"time": ev["time"], "user": ev["user"], "type": "label", "label": ev["label"], "action": ev["action"]})
    all_activities.sort(key=lambda x: x["time"])
    
    issue_data.append({
        "iid": iid,
        "labels": labels,
        "created": created,
        "closed": closed,
        "sys_notes": sys_notes,
        "label_events": label_events,
        "all_activities": all_activities,
    })

# Build daily indexes
for issue in issue_data:
    issue["daily_notes"] = defaultdict(list)
    for note in issue["sys_notes"]:
        ds = date_str(note["time"])
        if ds:
            issue["daily_notes"][ds].append(note)
    issue["daily_label_events"] = defaultdict(list)
    for ev in issue["label_events"]:
        ds = date_str(ev["time"])
        if ds:
            issue["daily_label_events"][ds].append(ev)

# Determine date range
min_date = min(all_dates)
max_date = date_str(datetime.datetime.now().isoformat())
print(f"Date range: {min_date} to {max_date}")

start = datetime.datetime.strptime(min_date, "%Y-%m-%d")
end = datetime.datetime.strptime(max_date, "%Y-%m-%d")
dates = []
d = start
while d <= end:
    dates.append(d.strftime("%Y-%m-%d"))
    d += datetime.timedelta(days=1)
print(f"Total days: {len(dates)}")

# Pre-compute: for each Function::dev issue, find the earliest date it entered "testing"
# Logic matches user's definition:
#   G(date) = (open issues with latest status = 娴嬭瘯涓?as of that date) + (issues closed by that date)
# For cumulative: count issues that have "entered testing" = first reached 娴嬭瘯涓?OR 宸插畬鎴?OR closed
# But to match user's 1089: we need status-as-of-date approach

# For each Function::dev issue, compute status timeline:
#   list of (date, status) from system notes, plus closed_at
# Then for each date, determine if issue is "in testing" (latest status = 娴嬭瘯涓? or "done" (closed or latest = 宸插畬鎴?

func_issue_timelines = {}  # iid -> list of (date_str, event_type, status_or_none)
# event_type: "status" (status change), "closed" (issue closed)

for issue in issue_data:
    if "Function::dev" not in issue["labels"]:
        continue
    iid = issue["iid"]
    timeline = []
    for note in issue["sys_notes"]:
        m = re.search(r"set status to \*\*(.+?)\*\*", note["body"])
        if m:
            ds = date_str(note["time"])
            if ds:
                timeline.append((ds, "status", m.group(1)))
    if issue["closed"]:
        ds = date_str(issue["closed"])
        if ds:
            timeline.append((ds, "closed", None))
    timeline.sort(key=lambda x: x[0])
    func_issue_timelines[iid] = timeline

# For each Function::dev issue, find first date it "entered testing":
#   - First 娴嬭瘯涓?status date
#   - Elif first 宸插畬鎴?status date (must have passed through testing)
#   - Elif closed_at date
func_first_test = {}

for iid, timeline in func_issue_timelines.items():
    test_date = None
    done_date = None
    closed_date = None
    for ds, etype, status in timeline:
        if etype == "status" and status == "娴嬭瘯涓? and test_date is None:
            test_date = ds
        elif etype == "status" and status == "宸插畬鎴? and done_date is None:
            done_date = ds
        elif etype == "closed" and closed_date is None:
            closed_date = ds
    
    if test_date:
        func_first_test[iid] = test_date
    elif done_date:
        func_first_test[iid] = done_date
    elif closed_date:
        func_first_test[iid] = closed_date

# For H: issues that reached 宸插畬鎴?or closed
func_first_done = {}
for iid, timeline in func_issue_timelines.items():
    done_date = None
    closed_date = None
    for ds, etype, status in timeline:
        if etype == "status" and status == "宸插畬鎴? and done_date is None:
            done_date = ds
        elif etype == "closed" and closed_date is None:
            closed_date = ds
    if done_date:
        func_first_done[iid] = done_date
    elif closed_date:
        func_first_done[iid] = closed_date

print(f"Function::dev issues entered testing (娴嬭瘯涓?宸插畬鎴?closed): {len(func_first_test)}")
print(f"Function::dev issues reached 宸插畬鎴? {len(func_first_done)}")

# ===== Compute daily statistics =====
print("\nComputing daily statistics...")
results = []

for di, ds in enumerate(dates):
    # A: date
    
    # B: 褰撴棩鏂板鍔熻兘闇€姹?- Function::dev issues created that day
    b_count = sum(1 for issue in issue_data 
                  if "Function::dev" in issue["labels"] 
                  and date_str(issue["created"]) == ds)
    
    # C: 褰撴棩鍓嶇瀹屾垚寮€鍙戞暟 - Function::dev, front::finished added by frontend user that day
    c_count = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for ev in issue["daily_label_events"].get(ds, []):
            if ev["label"] == "front::finished" and ev["action"] == "add" and ev["user"] in FRONTEND_USERS:
                c_count += 1
                break
    
    # D: 褰撴棩鍚庣瀹屾垚寮€鍙戞暟 - Function::dev, backend::finished added by backend user that day
    d_count = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for ev in issue["daily_label_events"].get(ds, []):
            if ev["label"] == "backend::finished" and ev["action"] == "add" and ev["user"] in BACKEND_USERS:
                d_count += 1
                break
    
    # E/F: 褰撴棩鑱旇皟瀹屾垚鏁?- Function::dev, set status to 娴嬭瘯涓?that day
    e_count = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for note in issue["daily_notes"].get(ds, []):
            if "set status to **娴嬭瘯涓?*" in note["body"]:
                e_count += 1
                break
    f_count = e_count
    
    # G: 绱鎻愪氦娴嬭瘯鎬绘暟
    # User's logic: G(date) = (open issues whose latest status as of date = 娴嬭瘯涓? + (issues closed by that date)
    g_count = 0
    for iid, timeline in func_issue_timelines.items():
        latest_status = None
        is_closed = False
        for ds_ev, etype, status in timeline:
            if ds_ev > ds:
                break
            if etype == "status":
                latest_status = status
            elif etype == "closed":
                is_closed = True
        if is_closed:
            g_count += 1
        elif latest_status == "娴嬭瘯涓?:
            g_count += 1
    
    # H: 绱鎻愪氦娴嬭瘯瀹屾垚鐜?    # A = G (issues in testing or completed)
    # B = issues completed/closed by this date
    a_val = g_count
    b_val = 0
    for iid, timeline in func_issue_timelines.items():
        for ds_ev, etype, status in timeline:
            if ds_ev > ds:
                break
            if etype == "closed" or (etype == "status" and status == "宸插畬鎴?):
                b_val += 1
                break
    h_rate = round(b_val / a_val * 100, 2) if a_val > 0 else 0
    
    # I-M: Bug::dev + Priority::PX issues set to 娴嬭瘯涓?that day
    p_counts = {f"P{i}": 0 for i in range(5)}
    bug_test_issues_today = []  # track for Q/R/S
    
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        # Check if set to 娴嬭瘯涓?that day
        test_notes_today = [n for n in issue["daily_notes"].get(ds, []) if "set status to **娴嬭瘯涓?*" in n["body"]]
        if not test_notes_today:
            continue
        
        # This issue was set to 娴嬭瘯涓?today, check Priority
        labels = issue["labels"]
        for p in range(5):
            if f"Priority::P{p}" in labels:
                p_counts[f"P{p}"] += 1
        
        bug_test_issues_today.append((issue, test_notes_today[0]))
    
    i_count = p_counts["P0"]
    j_count = p_counts["P1"]
    k_count = p_counts["P2"]
    l_count = p_counts["P3"]
    m_count = p_counts["P4"]
    
    # N: 褰撴棩鎻愪氦鍚堣 = I+J+K+L+M
    n_count = i_count + j_count + k_count + l_count + m_count
    
    # O: 褰撴棩鍓╀綑Bug鎬婚噺 - open Bug::dev issues on that day
    o_count = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if created_ds <= ds and (closed_ds is None or closed_ds > ds):
            o_count += 1
    
    # P: 楂樼骇鍒?P0+P1)鍓╀綑瀛橀噺
    p_count = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        if "Priority::P0" not in issue["labels"] and "Priority::P1" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if created_ds <= ds and (closed_ds is None or closed_ds > ds):
            p_count += 1
    
    # Q/R/S: classify Bug::dev issues set to 娴嬭瘯涓?that day by team
    q_count = 0  # frontend only
    r_count = 0  # backend only
    s_count = 0  # fullstack (both)
    
    for issue, test_note in bug_test_issues_today:
        tester = test_note["user"]
        test_time = test_note["time"]
        labels = issue["labels"]
        
        # Check all activity before this test note
        has_frontend_before = False
        has_backend_before = False
        for act in issue["all_activities"]:
            if act["time"] >= test_time:
                break
            if act["user"] in FRONTEND_USERS:
                has_frontend_before = True
            if act["user"] in BACKEND_USERS:
                has_backend_before = True
        
        # Determine type
        if "Port::fullstack" in labels:
            s_count += 1
        elif has_frontend_before and has_backend_before:
            s_count += 1
        elif tester in FRONTEND_USERS:
            if has_backend_before:
                s_count += 1
            else:
                q_count += 1
        elif tester in BACKEND_USERS:
            if has_frontend_before:
                s_count += 1
            else:
                r_count += 1
        elif "Port::frontend" in labels and "Port::backend" not in labels:
            q_count += 1
        elif "Port::backend" in labels and "Port::frontend" not in labels:
            r_count += 1
        else:
            # Can't determine, skip (shouldn't happen often)
            s_count += 1
    
    results.append({
        "A": ds, "B": b_count, "C": c_count, "D": d_count,
        "E": e_count, "F": f_count, "G": g_count,
        "H": h_rate,
        "I": i_count, "J": j_count, "K": k_count,
        "L": l_count, "M": m_count, "N": n_count,
        "O": o_count, "P": p_count,
        "Q": q_count, "R": r_count, "S": s_count,
    })
    
    if (di + 1) % 60 == 0:
        print(f"  Progress: {di+1}/{len(dates)} days")

print(f"  Done. {len(results)} days computed.")

# ===== Write to Excel =====
print("\nWriting to Excel...")
wb = openpyxl.load_workbook(EXCEL_PATH)

if "寮€鍙戞瘡鏃ユ眹鎬荤湅鏉? in wb.sheetnames:
    del wb["寮€鍙戞瘡鏃ユ眹鎬荤湅鏉?]
ws = wb.create_sheet("寮€鍙戞瘡鏃ユ眹鎬荤湅鏉?)

headers = [
    "鏃ユ湡", "褰撴棩鏂板鍔熻兘闇€姹?, "褰撴棩鍓嶇瀹屾垚寮€鍙戞暟", "褰撴棩鍚庣瀹屾垚寮€鍙戞暟",
    "褰撴棩鑱旇皟瀹屾垚鏁?, "褰撴棩鑱旇皟瀹屾垚鏁?, "绱鎻愪氦娴嬭瘯鎬绘暟", "绱鎻愪氦娴嬭瘯瀹屾垚鐜?,
    "褰撴棩鎻愪氦P0", "褰撴棩鎻愪氦P1", "褰撴棩鎻愪氦P2", "褰撴棩鎻愪氦P3", "褰撴棩鎻愪氦P4",
    "褰撴棩鎻愪氦鍚堣", "褰撴棩鍓╀綑Bug鎬婚噺", "楂樼骇鍒?P0+P1)鍓╀綑瀛橀噺",
    "浠呭墠绔疊UG褰撴棩鎻愪氦娴嬭瘯楠岃瘉鏁?, "浠呭悗绔疊UG褰撴棩鎻愪氦娴嬭瘯楠岃瘉鏁?, "鍓?鍚庣BUG褰撴棩鎻愪氦娴嬭瘯楠岃瘉鏁?,
]

for ci, h in enumerate(headers, 1):
    ws.cell(1, ci, value=h)

for ri, r in enumerate(results, 2):
    ws.cell(ri, 1, value=r["A"])
    ws.cell(ri, 2, value=r["B"])
    ws.cell(ri, 3, value=r["C"])
    ws.cell(ri, 4, value=r["D"])
    ws.cell(ri, 5, value=r["E"])
    ws.cell(ri, 6, value=r["F"])
    ws.cell(ri, 7, value=r["G"])
    ws.cell(ri, 8, value=f'{r["H"]}%')
    ws.cell(ri, 9, value=r["I"])
    ws.cell(ri, 10, value=r["J"])
    ws.cell(ri, 11, value=r["K"])
    ws.cell(ri, 12, value=r["L"])
    ws.cell(ri, 13, value=r["M"])
    ws.cell(ri, 14, value=r["N"])
    ws.cell(ri, 15, value=r["O"])
    ws.cell(ri, 16, value=r["P"])
    ws.cell(ri, 17, value=r["Q"])
    ws.cell(ri, 18, value=r["R"])
    ws.cell(ri, 19, value=r["S"])

# Print summary & validation
print("\n=== Summary ===")
print(f"Total days: {len(results)}")
print(f"Total new features (B): {sum(r['B'] for r in results)}")
print(f"Total frontend finished (C): {sum(r['C'] for r in results)}")
print(f"Total backend finished (D): {sum(r['D'] for r in results)}")
print(f"Total test submissions (E): {sum(r['E'] for r in results)}")
print(f"Final G (绱娴嬭瘯): {results[-1]['G']}")
print(f"Final H (瀹屾垚鐜?: {results[-1]['H']}%")
print(f"Total P0 (I): {sum(r['I'] for r in results)}")
print(f"Total P1 (J): {sum(r['J'] for r in results)}")
print(f"Total P2 (K): {sum(r['K'] for r in results)}")
print(f"Total P3 (L): {sum(r['L'] for r in results)}")
print(f"Total P4 (M): {sum(r['M'] for r in results)}")
print(f"Total N: {sum(r['N'] for r in results)}")
print(f"Total Q: {sum(r['Q'] for r in results)}")
print(f"Total R: {sum(r['R'] for r in results)}")
print(f"Total S: {sum(r['S'] for r in results)}")
print(f"Q+R+S: {sum(r['Q']+r['R']+r['S'] for r in results)}")

# Validation: N should equal Q+R+S per day
mismatches = 0
for r in results:
    if r["N"] != r["Q"] + r["R"] + r["S"]:
        mismatches += 1
        if mismatches <= 5:
            print(f"  MISMATCH {r['A']}: N={r['N']} Q+R+S={r['Q']+r['R']+r['S']}")
print(f"\nN vs Q+R+S mismatches: {mismatches}/{len(results)} days")

# Last 7 days
print("\n=== Last 7 days ===")
for r in results[-7:]:
    print(f"  {r['A']}: B={r['B']} C={r['C']} D={r['D']} E={r['E']} G={r['G']} H={r['H']}% I={r['I']} J={r['J']} K={r['K']} L={r['L']} M={r['M']} N={r['N']} O={r['O']} P={r['P']} Q={r['Q']} R={r['R']} S={r['S']}")

try:
    wb.save(EXCEL_PATH)
    print(f"\nSaved: {EXCEL_PATH}")
except PermissionError:
    alt = EXCEL_PATH.replace("_new2.xlsx", "_new2.xlsx")
    wb.save(alt)
    print(f"\nSaved (original occupied): {alt}")
print("Done!")

