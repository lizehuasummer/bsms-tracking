"""
生成「每日状态变更」sheet

列布局 (共 20 列):
  A: 日期
  Bug::dev (8列):
    B: open  总数
    C: open  + 待修复
    D: open  + 测试中
    E: open  + 已完成
    F: closed 总数
    G: closed + 待修复
    H: closed + 测试中
    I: closed + 已完成
  Function::dev (10列):
    J: open  总数
    K: open  + 待开发
    L: open  + 开发中
    M: open  + 测试中
    N: open  + 已完成
    O: closed 总数
    P: closed + 待开发
    Q: closed + 开发中
    R: closed + 测试中
    S: closed + 已完成
  Function::dev + open + Process::pass (1列):
    T: open + Process::pass
"""
import json, os, re, sys, datetime, openpyxl

CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
EXCEL_PATH = r"D:\Users\LZH\Documents\opencode\bsms_tracking\【交付HK】BSMS项目整体进度计划 (更新中)20260702备份_new.xlsx"


def date_str(t):
    if not t:
        return None
    return t[:10]


def parse_notes(notes):
    result = []
    for n in notes:
        if not n.get("system"):
            continue
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


# ===== Load data =====
print("Loading data...")
all_issues_path = os.path.join(CACHE_DIR, "gitlab_all_issues_cache.json")
issues_path = os.path.join(CACHE_DIR, "gitlab_issues_cache.json")
notes_path = os.path.join(CACHE_DIR, "gitlab_notes_cache.json")

if os.path.exists(all_issues_path):
    with open(all_issues_path, "r", encoding="utf-8") as f:
        all_issues = json.load(f)
    print(f"  {len(all_issues)} issues from gitlab_all_issues_cache.json")
else:
    with open(issues_path, "r", encoding="utf-8") as f:
        ic = json.load(f)
    seen = set()
    all_issues = []
    for issue in ic["functiondev"] + ic["bugdev"]:
        if issue["iid"] not in seen:
            seen.add(issue["iid"])
            all_issues.append(issue)
    print(f"  {len(all_issues)} issues from gitlab_issues_cache.json (deduplicated)")

with open(notes_path, "r", encoding="utf-8") as f:
    notes_cache = json.load(f)
print(f"  {len(notes_cache)} notes entries")

# ===== Build per-issue data =====
print("Building per-issue data...")
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

    status_timeline = []
    for note in sys_notes:
        m = re.search(r"set status to \*\*(.+?)\*\*", note["body"])
        if m:
            ds = date_str(note["time"])
            if ds:
                status_timeline.append((ds, m.group(1)))
    status_timeline.sort(key=lambda x: x[0])

    pass_timeline = []
    for ev in label_events:
        if ev["label"] == "Process::pass":
            ds = date_str(ev["time"])
            if ds:
                pass_timeline.append((ds, ev["action"]))
    pass_timeline.sort(key=lambda x: x[0])

    issue_data.append({
        "iid": iid,
        "labels": labels,
        "created": created,
        "closed": closed,
        "status_timeline": status_timeline,
        "pass_timeline": pass_timeline,
    })

# ===== Date range =====
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

# ===== Helper functions =====
def get_latest_status_as_of(issue, ds):
    latest = None
    for status_ds, status in issue["status_timeline"]:
        if status_ds > ds:
            break
        latest = status
    return latest


def has_process_pass_as_of(issue, ds):
    has_pass = False
    for pass_ds, action in issue["pass_timeline"]:
        if pass_ds > ds:
            break
        if action == "add":
            has_pass = True
        elif action == "remove":
            has_pass = False
    return has_pass


# ===== Compute daily statistics =====
print("\nComputing daily statistics...")
results = []

BUG_STATUSES = ["待修复", "测试中", "已完成"]
FUNC_STATUSES = ["待开发", "开发中", "测试中", "已完成"]

for di, ds in enumerate(dates):
    bug_open_total = 0
    bug_open_status = {s: 0 for s in BUG_STATUSES}
    bug_closed_total = 0
    bug_closed_status = {s: 0 for s in BUG_STATUSES}

    func_open_total = 0
    func_open_status = {s: 0 for s in FUNC_STATUSES}
    func_closed_total = 0
    func_closed_status = {s: 0 for s in FUNC_STATUSES}

    func_open_pass = 0

    for issue in issue_data:
        labels = issue["labels"]
        is_bug = "Bug::dev" in labels
        is_func = "Function::dev" in labels

        if not is_bug and not is_func:
            continue

        created_ds = date_str(issue["created"])
        if created_ds > ds:
            continue

        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        is_open = closed_ds is None or closed_ds > ds
        is_closed = closed_ds is not None and closed_ds <= ds

        latest_status = get_latest_status_as_of(issue, ds)

        if is_bug:
            if is_open:
                bug_open_total += 1
                if latest_status in bug_open_status:
                    bug_open_status[latest_status] += 1
            elif is_closed:
                bug_closed_total += 1
                if latest_status in bug_closed_status:
                    bug_closed_status[latest_status] += 1

        if is_func:
            if is_open:
                func_open_total += 1
                if latest_status in func_open_status:
                    func_open_status[latest_status] += 1
                if has_process_pass_as_of(issue, ds):
                    func_open_pass += 1
            elif is_closed:
                func_closed_total += 1
                if latest_status in func_closed_status:
                    func_closed_status[latest_status] += 1

    row = {
        "A": ds,
        "B": bug_open_total,
        "C": bug_open_status["待修复"], "D": bug_open_status["测试中"], "E": bug_open_status["已完成"],
        "F": bug_closed_total,
        "G": bug_closed_status["待修复"], "H": bug_closed_status["测试中"], "I": bug_closed_status["已完成"],
        "J": func_open_total,
        "K": func_open_status["待开发"], "L": func_open_status["开发中"], "M": func_open_status["测试中"], "N": func_open_status["已完成"],
        "O": func_closed_total,
        "P": func_closed_status["待开发"], "Q": func_closed_status["开发中"], "R": func_closed_status["测试中"], "S": func_closed_status["已完成"],
        "T": func_open_pass,
    }
    results.append(row)

    if (di + 1) % 60 == 0:
        print(f"  Progress: {di+1}/{len(dates)} days")

print(f"  Done. {len(results)} days computed.")

# ===== Write to Excel =====
print("\nWriting to Excel...")
wb = openpyxl.load_workbook(EXCEL_PATH)

sheet_name = "每日状态变更"
if sheet_name in wb.sheetnames:
    del wb[sheet_name]
ws = wb.create_sheet(sheet_name)

headers = [
    "日期",
    "Bug-open-总数",
    "Bug-open-待修复", "Bug-open-测试中", "Bug-open-已完成",
    "Bug-closed-总数",
    "Bug-closed-待修复", "Bug-closed-测试中", "Bug-closed-已完成",
    "Func-open-总数",
    "Func-open-待开发", "Func-open-开发中", "Func-open-测试中", "Func-open-已完成",
    "Func-closed-总数",
    "Func-closed-待开发", "Func-closed-开发中", "Func-closed-测试中", "Func-closed-已完成",
    "Func-open-Process::pass",
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

# ===== Summary =====
print("\n=== Summary ===")
print(f"Total days: {len(results)}")
last = results[-1]
print(f"Last day {last['A']}:")
print(f"  Bug open:    total={last['B']}, 待修复={last['C']}, 测试中={last['D']}, 已完成={last['E']}")
print(f"  Bug closed:  total={last['F']}, 待修复={last['G']}, 测试中={last['H']}, 已完成={last['I']}")
print(f"  Func open:   total={last['J']}, 待开发={last['K']}, 开发中={last['L']}, 测试中={last['M']}, 已完成={last['N']}")
print(f"  Func closed: total={last['O']}, 待开发={last['P']}, 开发中={last['Q']}, 测试中={last['R']}, 已完成={last['S']}")
print(f"  Func open + Process::pass: {last['T']}")

print("\n=== Last 7 days ===")
for r in results[-7:]:
    print(f"  {r['A']}:")
    print(f"    Bug  open({r['B']}): 待修复={r['C']}, 测试中={r['D']}, 已完成={r['E']}")
    print(f"    Bug  closed({r['F']}): 待修复={r['G']}, 测试中={r['H']}, 已完成={r['I']}")
    print(f"    Func open({r['J']}): 待开发={r['K']}, 开发中={r['L']}, 测试中={r['M']}, 已完成={r['N']}")
    print(f"    Func closed({r['O']}): 待开发={r['P']}, 开发中={r['Q']}, 测试中={r['R']}, 已完成={r['S']}")
    print(f"    Pass={r['T']}")

# Save
try:
    wb.save(EXCEL_PATH)
    print(f"\nSaved: {EXCEL_PATH}")
except PermissionError:
    alt = EXCEL_PATH.replace("_new.xlsx", "_new3.xlsx")
    wb.save(alt)
    print(f"\nOriginal occupied, saved to: {alt}")
print("Done!")
