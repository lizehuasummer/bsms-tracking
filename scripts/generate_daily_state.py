"""
生成「每日状态变更」sheet：每日 Bug + Function 各状态计数快照。
"""
import json, os, re, sys, datetime, openpyxl
from collections import defaultdict

CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
EXCEL_PATH = r"D:\Users\LZH\Documents\opencode\bsms_tracking\【交付HK】BSMS项目整体进度计划 (更新中)20260702备份_new.xlsx"

def date_str(t):
    if not t:
        return None
    return t[:10]

# ===== Load data =====
print("Loading data...")
issues_path = os.path.join(CACHE_DIR, "gitlab_issues_cache.json")
notes_path = os.path.join(CACHE_DIR, "gitlab_notes_cache.json")

with open(issues_path, "r", encoding="utf-8") as f:
    ic = json.load(f)
all_issues = ic["functiondev"] + ic["bugdev"]

with open(notes_path, "r", encoding="utf-8") as f:
    notes_cache = json.load(f)
print(f"  {len(all_issues)} issues, {len(notes_cache)} notes")

# ===== Build per-issue data =====
issue_data = []
all_dates = set()

for issue in all_issues:
    iid = issue["iid"]
    key = str(iid)
    cdata = notes_cache.get(key, {"notes": [], "label_events": []})
    notes = cdata.get("notes", [])
    label_events = cdata.get("label_events", [])

    labels = set(issue.get("labels", []))
    created = issue.get("created_at", "")
    closed = issue.get("closed_at")
    if created:
        all_dates.add(date_str(created))

    # Parse status changes
    status_changes = []
    for note in notes:
        if not note.get("system"):
            continue
        m = re.search(r"set status to \*\*(.+?)\*\*", note.get("body", ""))
        if m:
            ds = date_str(note["created_at"])
            if ds:
                status_changes.append((ds, m.group(1)))
    status_changes.sort(key=lambda x: x[0])

    # Parse Process::pass events
    has_process_pass = False
    for ev in label_events:
        lbl_obj = ev.get("label")
        if lbl_obj and lbl_obj.get("name") == "Process::pass" and ev.get("action") == "add":
            has_process_pass = True
            break

    issue_data.append({
        "iid": iid,
        "labels": labels,
        "created": created,
        "closed": closed,
        "status_changes": status_changes,
        "has_process_pass": has_process_pass,
    })

# ===== Date range =====
min_date = min(all_dates)
max_date = date_str(datetime.datetime.now().isoformat())
start = datetime.datetime.strptime(min_date, "%Y-%m-%d")
end = datetime.datetime.strptime(max_date, "%Y-%m-%d")
dates = []
d = start
while d <= end:
    dates.append(d.strftime("%Y-%m-%d"))
    d += datetime.timedelta(days=1)
print(f"Date range: {min_date} to {max_date}, {len(dates)} days")

# ===== Compute daily counts =====
print("Computing daily state counts...")
results = []

for ds in dates:
    # Counters
    bug_open = {"待修复": 0, "测试中": 0, "已完成": 0}
    bug_closed = {"待修复": 0, "测试中": 0, "已完成": 0}
    func_open = {"待开发": 0, "开发中": 0, "测试中": 0, "已完成": 0}
    func_closed = {"待开发": 0, "开发中": 0, "测试中": 0, "已完成": 0}
    func_open_process_pass = 0

    for issue in issue_data:
        labels = issue["labels"]
        created_ds = date_str(issue["created"])
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None

        if created_ds is None or created_ds > ds:
            continue

        is_closed = closed_ds is not None and closed_ds <= ds
        is_open = not is_closed or (closed_ds is not None and closed_ds > ds)

        sc = issue["status_changes"]
        latest_status = None
        for s_ds, s_status in sc:
            if s_ds > ds:
                break
            latest_status = s_status

        if "Bug::dev" in labels:
            if latest_status and latest_status in bug_open:
                if is_open:
                    bug_open[latest_status] += 1
                elif is_closed:
                    bug_closed[latest_status] += 1

        elif "Function::dev" in labels:
            if latest_status and latest_status in func_open:
                if is_open:
                    func_open[latest_status] += 1
                    if issue["has_process_pass"]:
                        func_open_process_pass += 1
                elif is_closed:
                    func_closed[latest_status] += 1

    results.append({
        "A": ds,
        "B": bug_open["待修复"], "C": bug_open["测试中"], "D": bug_open["已完成"],
        "E": bug_closed["待修复"], "F": bug_closed["测试中"], "G": bug_closed["已完成"],
        "H": func_open["待开发"], "I": func_open["开发中"], "J": func_open["测试中"], "K": func_open["已完成"],
        "L": func_closed["待开发"], "M": func_closed["开发中"], "N": func_closed["测试中"], "O": func_closed["已完成"],
        "P": func_open_process_pass,
    })

# ===== Write to Excel =====
print("Writing to Excel...")
wb = openpyxl.load_workbook(EXCEL_PATH)

sheet_name = "每日状态变更"
if sheet_name in wb.sheetnames:
    del wb[sheet_name]
ws = wb.create_sheet(sheet_name)

headers = [
    "日期",
    "Bug-open-待修复", "Bug-open-测试中", "Bug-open-已完成",
    "Bug-closed-待修复", "Bug-closed-测试中", "Bug-closed-已完成",
    "Func-open-待开发", "Func-open-开发中", "Func-open-测试中", "Func-open-已完成",
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

print(f"\n=== Last day ({results[-1]['A']}) ===")
last = results[-1]
print(f"  Bug-open: 待修复={last['B']}, 测试中={last['C']}, 已完成={last['D']}")
print(f"  Bug-closed: 待修复={last['E']}, 测试中={last['F']}, 已完成={last['G']}")
print(f"  Func-open: 待开发={last['H']}, 开发中={last['I']}, 测试中={last['J']}, 已完成={last['K']}")
print(f"  Func-closed: 待开发={last['L']}, 开发中={last['M']}, 测试中={last['N']}, 已完成={last['O']}")
print(f"  Func-open-Process::pass: {last['P']}")

try:
    wb.save(EXCEL_PATH)
    print(f"Saved: {EXCEL_PATH}")
except PermissionError:
    alt = EXCEL_PATH.replace(".xlsx", "_alt.xlsx")
    wb.save(alt)
    print(f"Saved to: {alt}")
print("Done!")
