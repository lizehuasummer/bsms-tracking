"""
生成开发每日汇总看板 + 测试每日汇总看板

开发看板 (29列 A-AC):
  A-S: 原有列
  T: Func-all-总数
  U: Func-open-待开发
  V: Func-open-开发中
  W: Func-open-测试中
  X: Func-open-其他
  Y: Func-open-总数
  Z: Func-open-Process::pass
  AA: Func-closed-已完成
  AB: Func-closed-其他
  AC: Func-closed-总数

测试看板 (31列 A-AE):
  A-W: 原有列
  X: Bug-all-总数
  Y: Bug-open-待修复
  Z: Bug-open-测试中
  AA: Bug-open-其他
  AB: Bug-open-总数
  AC: Bug-closed-已完成
  AD: Bug-closed-其他
  AE: Bug-closed-总数
"""
import json, os, re, sys, datetime, openpyxl
from collections import defaultdict

CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
EXCEL_PATH = r"D:\Users\LZH\Documents\opencode\bsms_tracking\【交付HK】BSMS项目整体进度计划 (更新中)20260702备份_new.xlsx"
SCRIPTS_DIR = r"D:\Users\LZH\Documents\opencode\bsms_tracking\scripts"

sys.path.insert(0, SCRIPTS_DIR)
from gitlab_users import GITLAB_USERS

FRONTEND_USERS = set(u[3] for u in GITLAB_USERS if u[0] == "系统开发组（前端）")
BACKEND_USERS = set(u[3] for u in GITLAB_USERS if u[0] == "系统开发组（后端）")

STATUS_TESTING = "测试中"
STATUS_DONE = "已完成"
STATUS_FIX = "待修复"
STATUS_DEV = "待开发"
STATUS_DEVING = "开发中"


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


def classify_team(issue, action_time, action_user):
    labels = issue["labels"]
    has_frontend_before = False
    has_backend_before = False
    for act in issue["all_activities"]:
        if act["time"] >= action_time:
            break
        if act["user"] in FRONTEND_USERS:
            has_frontend_before = True
        if act["user"] in BACKEND_USERS:
            has_backend_before = True

    if "Port::fullstack" in labels:
        return "fullstack"
    if has_frontend_before and has_backend_before:
        return "fullstack"
    if action_user in FRONTEND_USERS:
        return "fullstack" if has_backend_before else "frontend"
    if action_user in BACKEND_USERS:
        return "fullstack" if has_frontend_before else "backend"
    if "Port::frontend" in labels and "Port::backend" not in labels:
        return "frontend"
    if "Port::backend" in labels and "Port::frontend" not in labels:
        return "backend"
    return "fullstack"


def get_latest_status_as_of(iid, ds, timelines):
    latest = None
    for entry in timelines.get(iid, []):
        if entry[0] > ds:
            break
        latest = entry[1]
    return latest


def has_pass_as_of(iid, ds, pass_timelines):
    has_pass = False
    for entry in pass_timelines.get(iid, []):
        if entry[0] > ds:
            break
        if entry[1] == "add":
            has_pass = True
        elif entry[1] == "remove":
            has_pass = False
    return has_pass


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
print(f"  Frontend: {len(FRONTEND_USERS)} users, Backend: {len(BACKEND_USERS)} users")

# ===== Build per-issue data =====
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

# ===== Build timelines =====
func_timelines = {}
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

func_status_timelines = {}
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
                tl.append((ds, m.group(1)))
    tl.sort(key=lambda x: x[0])
    func_status_timelines[iid] = tl

func_pass_timelines = {}
for issue in issue_data:
    if "Function::dev" not in issue["labels"]:
        continue
    iid = issue["iid"]
    tl = []
    for ev in issue["label_events"]:
        if ev["label"] == "Process::pass":
            ds = date_str(ev["time"])
            if ds:
                tl.append((ds, ev["action"]))
    tl.sort(key=lambda x: x[0])
    func_pass_timelines[iid] = tl

bug_status_timelines = {}
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
                tl.append((ds, m.group(1)))
    tl.sort(key=lambda x: x[0])
    bug_status_timelines[iid] = tl

print(f"Function::dev timelines: {len(func_timelines)}")
print(f"Function::dev status timelines: {len(func_status_timelines)}")
print(f"Function::dev pass timelines: {len(func_pass_timelines)}")
print(f"Bug::dev status timelines: {len(bug_status_timelines)}")

# ===== Compute daily statistics =====
print("\nComputing daily statistics...")
dev_results = []
test_results = []

FUNC_KNOWN_STATUSES = {STATUS_DEV, STATUS_DEVING, STATUS_TESTING, STATUS_DONE}
BUG_KNOWN_STATUSES = {STATUS_FIX, STATUS_TESTING, STATUS_DONE}

for di, ds in enumerate(dates):
    # ===== Dev Dashboard (original A-S) =====
    dev_b = sum(1 for issue in issue_data
                if "Function::dev" in issue["labels"]
                and date_str(issue["created"]) == ds)

    dev_c = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for ev in issue["daily_label_events"].get(ds, []):
            if ev["label"] == "front::finished" and ev["action"] == "add" and ev["user"] in FRONTEND_USERS:
                dev_c += 1
                break

    dev_d = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for ev in issue["daily_label_events"].get(ds, []):
            if ev["label"] == "backend::finished" and ev["action"] == "add" and ev["user"] in BACKEND_USERS:
                dev_d += 1
                break

    dev_e = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for note in issue["daily_notes"].get(ds, []):
            if f"set status to **{STATUS_TESTING}**" in note["body"]:
                dev_e += 1
                break
    dev_f = dev_e

    dev_g = 0
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
        if is_closed:
            dev_g += 1
        elif latest_status == STATUS_TESTING:
            dev_g += 1

    dev_done_count = 0
    for iid, tl in func_timelines.items():
        for ds_ev, etype, status in tl:
            if ds_ev > ds:
                break
            if etype == "closed" or (etype == "status" and status == STATUS_DONE):
                dev_done_count += 1
                break
    dev_h = round(dev_done_count / dev_g * 100, 2) if dev_g > 0 else 0

    p_counts = {f"P{i}": 0 for i in range(5)}
    bug_test_issues_today = []
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        test_notes_today = [n for n in issue["daily_notes"].get(ds, []) if f"set status to **{STATUS_TESTING}**" in n["body"]]
        if not test_notes_today:
            continue
        labels = issue["labels"]
        for p in range(5):
            if f"Priority::P{p}" in labels:
                p_counts[f"P{p}"] += 1
        bug_test_issues_today.append((issue, test_notes_today[0]))

    dev_i = p_counts["P0"]
    dev_j = p_counts["P1"]
    dev_k = p_counts["P2"]
    dev_l = p_counts["P3"]
    dev_m = p_counts["P4"]
    dev_n = dev_i + dev_j + dev_k + dev_l + dev_m

    dev_o = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        if created_ds > ds:
            continue
        if issue["closed"] is not None:
            continue
        latest_status = get_latest_status_as_of(issue["iid"], ds, bug_status_timelines)
        if latest_status == STATUS_FIX:
            dev_o += 1

    dev_p = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        if "Priority::P0" not in issue["labels"] and "Priority::P1" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if created_ds <= ds and (closed_ds is None or closed_ds > ds):
            dev_p += 1

    dev_q = 0
    dev_r = 0
    dev_s = 0
    for issue, test_note in bug_test_issues_today:
        team = classify_team(issue, test_note["time"], test_note["user"])
        if team == "frontend":
            dev_q += 1
        elif team == "backend":
            dev_r += 1
        else:
            dev_s += 1

    # ===== Dev Dashboard: new Function::dev status breakdown (T-AC) =====
    dev_func_all = 0
    dev_func_open_status = {STATUS_DEV: 0, STATUS_DEVING: 0, STATUS_TESTING: 0}
    dev_func_open_total = 0
    dev_func_open_pass = 0
    dev_func_closed_done = 0
    dev_func_closed_total = 0

    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        if created_ds > ds:
            continue
        dev_func_all += 1

        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        is_open = closed_ds is None or closed_ds > ds

        latest_status = get_latest_status_as_of(issue["iid"], ds, func_status_timelines)

        if is_open:
            dev_func_open_total += 1
            if latest_status in dev_func_open_status:
                dev_func_open_status[latest_status] += 1
            if has_pass_as_of(issue["iid"], ds, func_pass_timelines):
                dev_func_open_pass += 1
        else:
            dev_func_closed_total += 1
            if latest_status == STATUS_DONE:
                dev_func_closed_done += 1

    dev_func_open_other = dev_func_open_total - sum(dev_func_open_status.values())
    dev_func_closed_other = dev_func_closed_total - dev_func_closed_done

    dev_results.append({
        "A": ds, "B": dev_b, "C": dev_c, "D": dev_d,
        "E": dev_e, "F": dev_f, "G": dev_g, "H": dev_h,
        "I": dev_i, "J": dev_j, "K": dev_k, "L": dev_l, "M": dev_m, "N": dev_n,
        "O": dev_o, "P": dev_p, "Q": dev_q, "R": dev_r, "S": dev_s,
        "T": dev_func_all,
        "U": dev_func_open_status[STATUS_DEV],
        "V": dev_func_open_status[STATUS_DEVING],
        "W": dev_func_open_status[STATUS_TESTING],
        "X": dev_func_open_other,
        "Y": dev_func_open_total,
        "Z": dev_func_open_pass,
        "AA": dev_func_closed_done,
        "AB": dev_func_closed_other,
        "AC": dev_func_closed_total,
    })

    # ===== Test Dashboard (original A-W) =====
    test_b = dev_e

    test_c = 0
    for issue in issue_data:
        if "Function::dev" not in issue["labels"]:
            continue
        for note in issue["daily_notes"].get(ds, []):
            if f"set status to **{STATUS_DONE}**" in note["body"]:
                test_c += 1
                break

    test_d = 0
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
        if not is_closed and latest_status == STATUS_TESTING:
            test_d += 1

    p_add = {f"P{i}": 0 for i in range(5)}
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        for ev in issue["daily_label_events"].get(ds, []):
            if ev["action"] == "add" and ev["label"].startswith("Priority::"):
                p = ev["label"].replace("Priority::", "")
                if p in p_add:
                    p_add[p] += 1

    test_e = p_add["P0"]
    test_f = p_add["P1"]
    test_g = p_add["P2"]
    test_h = p_add["P3"]
    test_i = p_add["P4"]
    test_j = test_e + test_f + test_g + test_h + test_i

    p_done = {f"P{i}": 0 for i in range(5)}
    bug_done_today = []
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        done_notes_today = [n for n in issue["daily_notes"].get(ds, []) if f"set status to **{STATUS_DONE}**" in n["body"]]
        if not done_notes_today:
            continue
        labels = issue["labels"]
        for p in range(5):
            if f"Priority::P{p}" in labels:
                p_done[f"P{p}"] += 1
        bug_done_today.append((issue, done_notes_today[0]))

    test_k = p_done["P0"]
    test_l = p_done["P1"]
    test_m = p_done["P2"]
    test_n = p_done["P3"]
    test_o = p_done["P4"]
    test_p = test_k + test_l + test_m + test_n + test_o

    test_q = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        if created_ds > ds:
            continue
        if issue["closed"] is not None:
            continue
        latest_status = get_latest_status_as_of(issue["iid"], ds, bug_status_timelines)
        if latest_status == STATUS_FIX:
            test_q += 1

    test_r = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if closed_ds and closed_ds <= ds:
            test_r += 1

    test_s = 0
    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        if "Priority::P0" not in issue["labels"] and "Priority::P1" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        if created_ds <= ds and (closed_ds is None or closed_ds > ds):
            test_s += 1

    test_t = 0
    test_u = 0
    test_v = 0
    for issue, done_note in bug_done_today:
        team = classify_team(issue, done_note["time"], done_note["user"])
        if team == "frontend":
            test_t += 1
        elif team == "backend":
            test_u += 1
        else:
            test_v += 1

    test_w = 0
    for iid, tl in func_timelines.items():
        for ds_ev, etype, status in tl:
            if ds_ev > ds:
                break
            if etype == "closed" or (etype == "status" and status == STATUS_DONE):
                test_w += 1
                break

    # ===== Test Dashboard: new Bug::dev status breakdown (X-AE) =====
    test_bug_all = 0
    test_bug_open_status = {STATUS_FIX: 0, STATUS_TESTING: 0}
    test_bug_open_total = 0
    test_bug_closed_done = 0
    test_bug_closed_total = 0

    for issue in issue_data:
        if "Bug::dev" not in issue["labels"]:
            continue
        created_ds = date_str(issue["created"])
        if created_ds > ds:
            continue
        test_bug_all += 1

        closed_ds = date_str(issue["closed"]) if issue["closed"] else None
        is_open = closed_ds is None or closed_ds > ds

        latest_status = get_latest_status_as_of(issue["iid"], ds, bug_status_timelines)

        if is_open:
            test_bug_open_total += 1
            if latest_status in test_bug_open_status:
                test_bug_open_status[latest_status] += 1
        else:
            test_bug_closed_total += 1
            if latest_status == STATUS_DONE:
                test_bug_closed_done += 1

    test_bug_open_other = test_bug_open_total - sum(test_bug_open_status.values())
    test_bug_closed_other = test_bug_closed_total - test_bug_closed_done

    test_results.append({
        "A": ds, "B": test_b, "C": test_c, "D": test_d,
        "E": test_e, "F": test_f, "G": test_g, "H": test_h, "I": test_i,
        "J": test_j,
        "K": test_k, "L": test_l, "M": test_m, "N": test_n, "O": test_o,
        "P": test_p,
        "Q": test_q, "R": test_r, "S": test_s,
        "T": test_t, "U": test_u, "V": test_v, "W": test_w,
        "X": test_bug_all,
        "Y": test_bug_open_status[STATUS_FIX],
        "Z": test_bug_open_status[STATUS_TESTING],
        "AA": test_bug_open_other,
        "AB": test_bug_open_total,
        "AC": test_bug_closed_done,
        "AD": test_bug_closed_other,
        "AE": test_bug_closed_total,
    })

    if (di + 1) % 60 == 0:
        print(f"  Progress: {di+1}/{len(dates)} days")

print(f"  Done. {len(dev_results)} days computed.")

# ===== Write to Excel =====
print("\nWriting to Excel...")
wb = openpyxl.load_workbook(EXCEL_PATH)

# --- Dev Dashboard ---
dev_sheet = "开发每日汇总看板"
if dev_sheet in wb.sheetnames:
    del wb[dev_sheet]
ws1 = wb.create_sheet(dev_sheet)

dev_headers = [
    "日期", "当日新增功能需求", "当日前端完成开发数", "当日后端完成开发数",
    "当日联调完成数", "当日联调完成数", "累计提交测试总数", "累计提交测试完成率",
    "当日提交P0", "当日提交P1", "当日提交P2", "当日提交P3", "当日提交P4",
    "当日提交合计", "当日剩余待修复Bug总量", "高级别(P0+P1)剩余存量",
    "仅前端BUG当日提交测试验证数", "仅后端BUG当日提交测试验证数", "前+后端BUG当日提交测试验证数",
    "Func-all-总数",
    "Func-open-待开发", "Func-open-开发中", "Func-open-测试中", "Func-open-其他",
    "Func-open-总数", "Func-open-Process::pass",
    "Func-closed-已完成", "Func-closed-其他", "Func-closed-总数",
]
for ci, h in enumerate(dev_headers, 1):
    ws1.cell(1, ci, value=h)

dev_keys = [
    "A", "B", "C", "D", "E", "F", "G", "H",
    "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S",
    "T", "U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC",
]
for ri, r in enumerate(dev_results, 2):
    for ci, key in enumerate(dev_keys, 1):
        val = r[key]
        if key == "H":
            val = f"{val}%"
        ws1.cell(ri, ci, value=val)

# --- Test Dashboard ---
test_sheet = "测试每日汇总看板"
if test_sheet in wb.sheetnames:
    del wb[test_sheet]
ws2 = wb.create_sheet(test_sheet)

test_headers = [
    "日期",
    "当日新提交功能测试", "当日完成功能测试", "当日剩余功能测试",
    "当日新增P0", "当日新增P1", "当日新增P2", "当日新增P3", "当日新增P4",
    "当日新增合计",
    "当日完成P0", "当日完成P1", "当日完成P2", "当日完成P3", "当日完成P4",
    "当日完成合计",
    "当日剩余待验证Bug总量", "累计关闭Bug总量", "高级别(P0+P1)剩余存量",
    "仅前端BUG当日测试通过数", "仅后端BUG当日测试通过数", "前+后端BUG当日测试通过数",
    "累计完成功能测试",
    "Bug-all-总数",
    "Bug-open-待修复", "Bug-open-测试中", "Bug-open-其他", "Bug-open-总数",
    "Bug-closed-已完成", "Bug-closed-其他", "Bug-closed-总数",
]
for ci, h in enumerate(test_headers, 1):
    ws2.cell(1, ci, value=h)

test_keys = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    "K", "L", "M", "N", "O", "P", "Q", "R", "S",
    "T", "U", "V", "W",
    "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE",
]
for ri, r in enumerate(test_results, 2):
    for ci, key in enumerate(test_keys, 1):
        ws2.cell(ri, ci, value=r[key])

# ===== Summary =====
print("\n=== Dev Dashboard ===")
last = dev_results[-1]
print(f"Last day {last['A']}:")
print(f"  O(待修复)={last['O']}, P(P0+P1)={last['P']}, G={last['G']}, H={last['H']}%")
print(f"  Func-all={last['T']}, open(待开发={last['U']},开发中={last['V']},测试中={last['W']},其他={last['X']},总数={last['Y']},Pass={last['Z']})")
print(f"  Func-closed(已完成={last['AA']},其他={last['AB']},总数={last['AC']})")

print("\n=== Test Dashboard ===")
last = test_results[-1]
print(f"Last day {last['A']}:")
print(f"  Q(待验证)={last['Q']}, R(累计关闭)={last['R']}, W(累计完成)={last['W']}")
print(f"  Bug-all={last['X']}, open(待修复={last['Y']},测试中={last['Z']},其他={last['AA']},总数={last['AB']})")
print(f"  Bug-closed(已完成={last['AC']},其他={last['AD']},总数={last['AE']})")

print("\n=== Last 7 days (new columns) ===")
for r in dev_results[-7:]:
    print(f"  {r['A']} Dev: Func-all={r['T']} open(待开发={r['U']},开发中={r['V']},测试中={r['W']},其他={r['X']},总={r['Y']},Pass={r['Z']}) closed(完成={r['AA']},其他={r['AB']},总={r['AC']})")
for r in test_results[-7:]:
    print(f"  {r['A']} Test: Bug-all={r['X']} open(待修复={r['Y']},测试中={r['Z']},其他={r['AA']},总={r['AB']}) closed(完成={r['AC']},其他={r['AD']},总={r['AE']})")

# Save
try:
    wb.save(EXCEL_PATH)
    print(f"\nSaved: {EXCEL_PATH}")
except PermissionError:
    alt = EXCEL_PATH.replace("_new_v2.xlsx", "_new_v3.xlsx")
    wb.save(alt)
    print(f"\nOriginal occupied, saved to: {alt}")
print("Done!")
