"""
娴嬭瘯姣忔棩姹囨€荤湅鏉?A: 鏃ユ湡
B: Function::dev 褰撴棩 set status to 娴嬭瘯涓?C: Function::dev 褰撴棩 set status to 宸插畬鎴?D: Function::dev 褰撴棩 open 涓?latest status = 娴嬭瘯涓?E-I: Bug::dev 褰撴棩娣诲姞 Priority::P0-P4 label
J: E+I sum
K-O: Bug::dev 褰撴棩 set status to 宸插畬鎴? by Priority P0-P4
P: K+O sum
Q: Bug::dev 褰撴棩 open
R: Bug::dev 鎴褰撴棩 closed 绱
S: Bug::dev 褰撴棩 open 涓旀湁 P0 or P1
T-V: Bug::dev 褰撴棩 set status to 宸插畬鎴?or closed, by frontend/backend/fullstack
W: Function::dev 鎴褰撴棩 绱 宸插畬鎴?or closed
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

# Date range
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

# Pre-build status timelines for Function::dev issues
func_timelines = {}  # iid -> [(date, "status", status_value) | (date, "closed", None)]
for issue in issue_data:
    if "Function::dev" not in issue["labels"]:
        continue
    iid = issue["iid"]
    tl = []
    for note in issue["sys_notes"]:
        m = re.search(r"set status to \*\*(.+?)\*\*", note["body"])
        if m:
            ds = date_str(note["time"])
            if ds:
                tl.append((ds, "status", m.group(1)))
    if issue["closed"]:
        ds = date_str(issue["closed"])
        if ds:
            tl.append((ds, "closed", None))
    tl.sort(key=lambda x: x[0])
    func_timelines[iid] = tl

# Pre-build status timelines for Bug::dev issues
bug_timelines = {}
for issue in issue_data:
    if "Bug::dev" not in issue["labels"]:
        continue
    iid = issue["iid"]
    tl = []
    for note in issue["sys_notes"]:
        m = re.search(r"set status to \*\*(.+?)\*\*", note["body"])
        if m:
            ds = date_str(note["time"])
            if ds:
                tl.append((ds, "status", m.group(1), note["user"]))
    if issue["closed"]:
        ds = date_str(issue["closed"])
        if ds:
            tl.append((ds, "closed", None, ""))
    tl.sort(key=lambda x: x[0])
    bug_timelines[iid] = tl

print(f"Function::dev timelines: {len(func_timelines)}")
print(f"Bug::dev timelines: {len(bug_timelines)}")

# ===== Compute daily statistics =====
print("\nComputing daily statistics...")
results = []

for di, ds in enumerate(dates):
    # A: date

    # B: Function::dev 褰撴棩 set status to 娴嬭瘯涓?    b_count = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for note in issue["daily_notes"].get(ds, []):
            if "set status to **娴嬭瘯涓?*" in note["body"]:
                b_count += 1
                break

    # C: Function::dev 褰撴棩 set status to 宸插畬鎴?    c_count = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for note in issue["daily_notes"].get(ds, []):
            if "set status to **宸插畬鎴?*" in note["body"]:
                c_count += 1
                break

    # D: Function::dev 褰撴棩 open 涓?latest status = 娴嬭瘯涓?    d_count = 0
    for iid, tl in func_timelines.items():
        latest_status = None
        is_closed = False
        for ds_ev, etype, status in tl:
            if ds_ev > ds:
                break
            if etype == "status":
                latest_status = status
            elif etype == "closed":
                is_closed = True
        if not is_closed and latest_status == "娴嬭瘯涓?:
            d_count += 1

    # W: Function::dev 鎴褰撴棩 绱 宸插畬鎴?or closed
    w_count = 0
    for iid, tl in func_timelines.items():
        for ds_ev, etype, status in tl:
            if ds_ev > ds:
                break
            if etype == "closed" or (etype == "status" and status == "宸插畬鎴?):
                w_count += 1
                break

    # E-I: Bug::dev 褰撴棩娣诲姞 Priority::P0-P4 label
    p_add = {f"P{i}": 0 for i in range(5)}
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        for ev in issue["daily_label_events"].get(ds, []):
            if ev["action"] == "add" and ev["label"].startswith("Priority::"):
                p = ev["label"].replace("Priority::", "")
                if p in p_add:
                    p_add[p] += 1

    e_count = p_add["P0"]
    f_count = p_add["P1"]
    g_count = p_add["P2"]
    h_count = p_add["P3"]
    i_count = p_add["P4"]

    # J: E+I sum
    j_count = e_count + f_count + g_count + h_count + i_count

    # K-O: Bug::dev 褰撴棩 set status to 宸插畬鎴? by Priority P0-P4
    p_done = {f"P{i}": 0 for i in range(5)}
    bug_done_today = []  # (issue, note) for T/V classification
    
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        done_notes_today = [n for n in issue["daily_notes"].get(ds, []) if "set status to **宸插畬鎴?*" in n["body"]]
        if not done_notes_today:
            continue
        
        labels = issue["labels"]
        for p in range(5):
            if f"Priority::P{p}" in labels:
                p_done[f"P{p}"] += 1
        
        bug_done_today.append((issue, done_notes_today[0]))

    k_count = p_done["P0"]
    l_count = p_done["P1"]
    m_count = p_done["P2"]
    n_count = p_done["P3"]
    o_count = p_done["P4"]

    # P: K+O sum
    p_count = k_count + l_count + m_count + n_count + o_count

    # Q: Bug::dev 褰撴棩 open
    q_count = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if created_ds <= ds and (closed_ds is None or closed_ds > ds):
            q_count += 1

    # R: Bug::dev 鎴褰撴棩 closed 绱
    r_count = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if closed_ds and closed_ds <= ds:
            r_count += 1

    # S: Bug::dev 褰撴棩 open 涓旀湁 P0 or P1
    s_count = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        if "Priority::P0" not in issue["labels"] and "Priority::P1" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if created_ds <= ds and (closed_ds is None or closed_ds > ds):
            s_count += 1

    # T-V: Bug::dev 褰撴棩 set status to 宸插畬鎴? classify by team
    t_count = 0  # frontend only
    u_count = 0  # backend only
    v_count = 0  # fullstack

    for issue, done_note in bug_done_today:
        completer = done_note["user"]
        done_time = done_note["time"]
        labels = issue["labels"]

        # Check all activity before this done note
        has_frontend_before = False
        has_backend_before = False
        for act in issue["all_activities"]:
            if act["time"] >= done_time:
                break
            if act["user"] in FRONTEND_USERS:
                has_frontend_before = True
            if act["user"] in BACKEND_USERS:
                has_backend_before = True

        if "Port::fullstack" in labels:
            v_count += 1
        elif has_frontend_before and has_backend_before:
            v_count += 1
        elif completer in FRONTEND_USERS:
            if has_backend_before:
                v_count += 1
            else:
                t_count += 1
        elif completer in BACKEND_USERS:
            if has_frontend_before:
                v_count += 1
            else:
                u_count += 1
        elif "Port::frontend" in labels and "Port::backend" not in labels:
            t_count += 1
        elif "Port::backend" in labels and "Port::frontend" not in labels:
            u_count += 1
        else:
            v_count += 1

    results.append({
        "A": ds,
        "B": b_count, "C": c_count, "D": d_count,
        "E": e_count, "F": f_count, "G": g_count, "H": h_count, "I": i_count,
        "J": j_count,
        "K": k_count, "L": l_count, "M": m_count, "N": n_count, "O": o_count,
        "P": p_count,
        "Q": q_count, "R": r_count, "S": s_count,
        "T": t_count, "U": u_count, "V": v_count,
        "W": w_count,
    })

    if (di + 1) % 60 == 0:
        print(f"  Progress: {di+1}/{len(dates)} days")

print(f"  Done. {len(results)} days computed.")

# ===== Write to Excel =====
print("\nWriting to Excel...")
wb = openpyxl.load_workbook(EXCEL_PATH)

if "娴嬭瘯姣忔棩姹囨€荤湅鏉? in wb.sheetnames:
    del wb["娴嬭瘯姣忔棩姹囨€荤湅鏉?]
ws = wb.create_sheet("娴嬭瘯姣忔棩姹囨€荤湅鏉?)

headers = [
    "鏃ユ湡",                                          # A
    "褰撴棩鏂版彁浜ゅ姛鑳芥祴璇?,                              # B
    "褰撴棩瀹屾垚鍔熻兘娴嬭瘯",                                # C
    "褰撴棩鍓╀綑鍔熻兘娴嬭瘯",                                # D
    "褰撴棩鏂板P0",                                     # E
    "褰撴棩鏂板P1",                                     # F
    "褰撴棩鏂板P2",                                     # G
    "褰撴棩鏂板P3",                                     # H
    "褰撴棩鏂板P4",                                     # I
    "褰撴棩鏂板鍚堣",                                   # J
    "褰撴棩瀹屾垚P0",                                     # K
    "褰撴棩瀹屾垚P1",                                     # L
    "褰撴棩瀹屾垚P2",                                     # M
    "褰撴棩瀹屾垚P3",                                     # N
    "褰撴棩瀹屾垚P4",                                     # O
    "褰撴棩瀹屾垚鍚堣",                                   # P
    "褰撴棩鍓╀綑Bug鎬婚噺",                                # Q
    "绱鍏抽棴Bug鎬婚噺",                                # R
    "楂樼骇鍒?P0+P1)鍓╀綑瀛橀噺",                          # S
    "浠呭墠绔疊UG褰撴棩娴嬭瘯閫氳繃鏁?,                        # T
    "浠呭悗绔疊UG褰撴棩娴嬭瘯閫氳繃鏁?,                        # U
    "鍓?鍚庣BUG褰撴棩娴嬭瘯閫氳繃鏁?,                       # V
    "绱瀹屾垚鍔熻兘娴嬭瘯",                               # W
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
    ws.cell(ri, 8, value=r["H"])
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
    ws.cell(ri, 20, value=r["T"])
    ws.cell(ri, 21, value=r["U"])
    ws.cell(ri, 22, value=r["V"])
    ws.cell(ri, 23, value=r["W"])

# Validation
print("\n=== Summary ===")
print(f"Total days: {len(results)}")
print(f"Total B (鍔熻兘娴嬭瘯鎻愪氦): {sum(r['B'] for r in results)}")
print(f"Total C (鍔熻兘娴嬭瘯瀹屾垚): {sum(r['C'] for r in results)}")
print(f"Final D (鍓╀綑鍔熻兘娴嬭瘯): {results[-1]['D']}")
print(f"Final W (绱瀹屾垚鍔熻兘娴嬭瘯): {results[-1]['W']}")
print(f"Total J (鏂板Priority鍚堣): {sum(r['J'] for r in results)}")
print(f"Total P (瀹屾垚Priority鍚堣): {sum(r['P'] for r in results)}")
print(f"Total T: {sum(r['T'] for r in results)}")
print(f"Total U: {sum(r['U'] for r in results)}")
print(f"Total V: {sum(r['V'] for r in results)}")
print(f"T+U+V: {sum(r['T']+r['U']+r['V'] for r in results)}")

# Check T+U+V = P per day
mismatches = 0
for r in results:
    if r["T"] + r["U"] + r["V"] != r["P"]:
        mismatches += 1
        if mismatches <= 5:
            print(f"  MISMATCH {r['A']}: P={r['P']} T+U+V={r['T']+r['U']+r['V']}")
print(f"\nT+U+V vs P mismatches: {mismatches}/{len(results)} days")

# Check J = E+F+G+H+I
j_mismatches = 0
for r in results:
    if r["J"] != r["E"]+r["F"]+r["G"]+r["H"]+r["I"]:
        j_mismatches += 1
print(f"J vs E+F+G+H+I mismatches: {j_mismatches}/{len(results)} days")

# Last 7 days
print("\n=== Last 7 days ===")
for r in results[-7:]:
    print(f"  {r['A']}: B={r['B']} C={r['C']} D={r['D']} W={r['W']} | J={r['J']} P={r['P']} Q={r['Q']} R={r['R']} S={r['S']} T={r['T']} U={r['U']} V={r['V']}")

try:
    wb.save(EXCEL_PATH)
    print(f"\nSaved: {EXCEL_PATH}")
except PermissionError:
    alt = EXCEL_PATH.replace("_new2.xlsx", "_new2.xlsx")
    wb.save(alt)
    print(f"\nSaved (original occupied): {alt}")
print("Done!")

