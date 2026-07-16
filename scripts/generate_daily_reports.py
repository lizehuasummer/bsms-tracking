"""
生成 技术工作日报（填报）+ 测试工作日报（填报）
按 issue Activity（status changes + label events）逐日填充
"""
import json, re, openpyxl, os, sys
from datetime import datetime, date
from collections import defaultdict

CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
EXCEL_PATH = r"D:\Users\LZH\Documents\opencode\bsms_tracking\【交付HK】BSMS项目整体进度计划 (更新中)20260702备份_new.xlsx"

# ---- 加载数据 ----
ic = json.load(open(CACHE_DIR + "/gitlab_issues_cache.json", encoding="utf-8"))
all_issues = ic["all"]
func_issues = ic["functiondev"]
bug_issues = ic["bugdev"]

nc = json.load(open(CACHE_DIR + "/gitlab_notes_cache.json", encoding="utf-8"))
issue_by_iid = {i["iid"]: i for i in all_issues}

def extract_feature_id(title):
    m = re.search(r'([A-Z0-9]{2,5}-[A-Z]{1,5}\d{1,4}(?:-\d+)?)', title)
    return m.group(1) if m else ""

def parse_status_from_notes(notes):
    changes = []
    for note in notes:
        if not note.get("system"): continue
        m = re.search(r"set status to \*\*(.+?)\*\*", note.get("body", ""))
        if m:
            changes.append({"status": m.group(1), "time": note["created_at"], "user": note.get("author", {}).get("username", "")})
    return changes

def parse_processpass_from_events(events):
    result = []
    for ev in events:
        lbl = ev.get("label", {})
        if lbl.get("name") == "Process::pass" and ev.get("action") == "add":
            result.append({"time": ev["created_at"], "user": ev.get("user", {}).get("username", "")})
    return result

def get_subsystem(labels):
    for lbl in labels:
        if lbl.startswith("BSMS::"):
            return lbl.replace("BSMS::", "")
    return ""

def stage_status(latest_status, current_labels):
    if latest_status is None:
        return "待开发"
    if latest_status == "开发中":
        return "开发中"
    if latest_status == "测试中":
        if "Process::pass" in current_labels:
            return "processpass"
        return "测试中"
    if latest_status == "已完成":
        return "已完成"
    return latest_status

def fmt_time(ts):
    if not ts: return ""
    try:
        return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M")
    except:
        return str(ts)[:16]

def fmt_date(ts):
    if not ts: return ""
    try:
        return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
    except:
        return str(ts)[:10]

# ============ 1. 技术工作日报（填报）============
def build_tech_daily():
    """
    对每个 Function::dev issue，提取每日 activity，
    合并 status_changes + front::finished/backend::finished 事件，
    按 (iid, date) 聚合，一天一条。
    """
    rows = []

    for issue in func_issues:
        iid = issue["iid"]
        title = issue.get("title", "")
        labels = set(issue.get("labels", []))
        state = issue.get("state", "")
        fid = extract_feature_id(title)
        subsystem = get_subsystem(labels)
        fname = title.split(" ", 1)[1] if " " in title else title

        key = str(iid)
        cdata = nc.get(key, {"notes": [], "label_events": []})
        notes = cdata.get("notes", [])
        events = cdata.get("label_events", [])

        # 解析 status_changes
        sc = parse_status_from_notes(notes)

        # 收集 front::finished / backend::finished 事件
        front_events = []
        backend_events = []
        for ev in events:
            lbl = ev.get("label", {})
            name = lbl.get("name", "")
            action = ev.get("action", "")
            t = ev.get("created_at", "")
            u = ev.get("user", {}).get("username", "")
            if action == "add" and name == "front::finished":
                front_events.append({"time": t, "user": u})
            elif action == "add" and name == "backend::finished":
                backend_events.append({"time": t, "user": u})

        # 合并所有活动并排序
        activities = []
        for s in sc:
            activities.append({"time": s["time"], "type": "status", "status": s["status"], "user": s["user"]})
        for fe in front_events:
            activities.append({"time": fe["time"], "type": "front_finished", "user": fe["user"]})
        for be in backend_events:
            activities.append({"time": be["time"], "type": "backend_finished", "user": be["user"]})
        activities.sort(key=lambda x: x["time"])

        # 按 date 聚合
        daily = defaultdict(list)
        for act in activities:
            d = fmt_date(act["time"])
            daily[d].append(act)

        # 确定开发类型
        dev_type = "前+后端"
        fe_username = ""
        be_username = ""
        sc_by_date = defaultdict(list)

        # 按日期追踪前端/后端负责人
        for act in activities:
            if act["type"] == "front_finished":
                fe_username = act["user"]
            elif act["type"] == "backend_finished":
                be_username = act["user"]

        if fe_username and not be_username:
            dev_type = "前端"
        elif be_username and not fe_username:
            dev_type = "后端"
        elif fe_username and be_username:
            dev_type = "前+后端"

        # 备选：检查 Port:: 标签
        if not fe_username and not be_username:
            if "Port::frontend" in labels:
                dev_type = "前端"
            elif "Port::backend" in labels:
                dev_type = "后端"
            elif "Port::fullstack" in labels:
                dev_type = "前+后端"

        # Sprint 计划
        sprint = ""
        for lbl in sorted(labels, key=lambda x: 0 if x.startswith("Sprint::") else 1):
            if lbl.startswith("Sprint::") or lbl.startswith("sprint::"):
                sprint = "Sprint " + lbl.split("::")[1].lstrip("0")
                break

        # 构建每日行
        for d in sorted(daily.keys()):
            acts = daily[d]
            # 该日的最新 status
            day_last_status = None
            day_front = ""
            day_back = ""
            for act in sorted(acts, key=lambda x: x["time"]):
                if act["type"] == "status":
                    day_last_status = act["status"]
                elif act["type"] == "front_finished":
                    day_front = act["user"]
                elif act["type"] == "backend_finished":
                    day_back = act["user"]

            # 前端/后端状态
            front_status = "已完成" if day_front else (stage_status(day_last_status, labels) if day_last_status else "待开发")
            back_status = "已完成" if day_back else (stage_status(day_last_status, labels) if day_last_status else "待开发")

            # 提交测试标记
            pass_events = parse_processpass_from_events(events)
            submitted_test = ""
            for pe in pass_events:
                pd = fmt_date(pe["time"])
                if pd <= d:
                    submitted_test = "是"

            rows.append({
                "date": d,
                "iid": iid,
                "subsystem": subsystem,
                "fid": fid,
                "fname": fname,
                "sprint": sprint,
                "dev_type": dev_type,
                "fe_user": day_front or fe_username,
                "fe_status": front_status,
                "be_user": day_back or be_username,
                "be_status": back_status,
                "submitted": submitted_test,
                "status": day_last_status or "待开发",
            })

    # 按 date + iid 排序
    rows.sort(key=lambda x: (x["date"], x["iid"]))
    return rows

# ============ 2. 测试工作日报（填报）============
def build_test_daily():
    """
    基于 Bug::dev issues，按日期和关联功能点聚合。
    同时包含功能测试和缺陷登记。
    """
    rows = []

    # 先建立 bug 关联到 feature 的索引（通过 fid 匹配）
    # Bug issues 可能没有直接的 fid，需要看 title 或 notes
    for bug in bug_issues:
        iid = bug["iid"]
        title = bug.get("title", "")
        labels = set(bug.get("labels", []))
        created = bug.get("created_at", "")
        d = fmt_date(created)
        state = bug.get("state", "")
        closed_at = bug.get("closed_at", "")

        subsystem = get_subsystem(labels)
        fid = extract_feature_id(title)
        priority = ""
        for lbl in labels:
            if lbl.startswith("Priority::"):
                priority = lbl.replace("Priority::", "")
                break

        # 查找关联的 Function::dev feature
        related_feature = ""
        related_fid = fid
        if fid:
            for fi in func_issues:
                t = fi.get("title", "")
                if fid in t:
                    related_feature = t.split(" ", 1)[1] if " " in t else t
                    related_fid = fid
                    break

        # 测试人员 - 从 notes 中找
        key = str(iid)
        cdata = nc.get(key, {"notes": [], "label_events": []})
        notes = cdata.get("notes", [])
        events = cdata.get("label_events", [])

        # 状态变化
        sc = parse_status_from_notes(notes)
        test_sc = None
        for s in reversed(sc):
            if s["status"] == "测试中":
                test_sc = s
                break

        # Bug 修复人
        fix_user = ""
        done_sc = None
        for s in reversed(sc):
            if s["status"] == "已完成":
                done_sc = s
                break
        if done_sc:
            fix_user = done_sc["user"]

        tester = test_sc["user"] if test_sc else ""

        rows.append({
            "date": d,
            "iid": iid,
            "subsystem": subsystem,
            "fid": related_fid,
            "fname": related_feature,
            "title": title,
            "priority": priority,
            "tester": tester,
            "fix_user": fix_user,
            "status": "待修复" if state == "opened" else ("已修复" if state == "closed" else ""),
            "state": state,
        })

    # 添加功能测试记录（Function::dev 的测试活动）
    for issue in func_issues:
        iid = issue["iid"]
        title = issue.get("title", "")
        labels = set(issue.get("labels", []))
        fid = extract_feature_id(title)
        subsystem = get_subsystem(labels)
        fname = title.split(" ", 1)[1] if " " in title else title

        key = str(iid)
        cdata = nc.get(key, {"notes": [], "label_events": []})
        events = cdata.get("label_events", [])

        # 当 Process::pass 添加时 → 功能测试
        for ev in events:
            lbl = ev.get("label", {})
            name = lbl.get("name", "")
            action = ev.get("action", "")
            t = ev.get("created_at", "")
            u = ev.get("user", {}).get("username", "")
            d = fmt_date(t)

            if name == "Process::pass" and action == "add":
                # 检查当天是否已有同 iid 记录
                exists = False
                for r in rows:
                    if r.get("date") == d and r.get("iid") == iid and r.get("type") == "功能测试":
                        exists = True
                        break
                if not exists:
                    rows.append({
                        "date": d,
                        "iid": iid,
                        "subsystem": subsystem,
                        "fid": fid,
                        "fname": fname,
                        "title": title,
                        "priority": "",
                        "tester": u,
                        "fix_user": "",
                        "status": "完成测试",
                        "state": issue.get("state", ""),
                        "type": "功能测试",
                    })

    rows.sort(key=lambda x: (x.get("date", ""), x.get("iid", 0)))
    return rows

# ============ 填充 Excel ============
wb = openpyxl.load_workbook(EXCEL_PATH)

# ---- Sheet: 技术工作日报（填报）----
tech_rows = build_tech_daily()
sheet_name1 = "技术工作日报（填报）"
if sheet_name1 in wb.sheetnames:
    del wb[sheet_name1]
ws1 = wb.create_sheet(sheet_name1)

# 表头
headers1 = ["日期", "iid", "子系统", "功能点号", "详细功能点", "开发计划",
            "开发类型", "前端负责人", "前端开发完成状态", "登记时间",
            "后端负责人", "后端开发完成状态", "登记时间", "当前状态", "是否提交测试"]
for c, h in enumerate(headers1, 1):
    ws1.cell(1, c).value = h

# 数据
idx = 2
for r in tech_rows:
    ws1.cell(idx, 1).value = r["date"]
    ws1.cell(idx, 2).value = r["iid"]
    ws1.cell(idx, 3).value = r["subsystem"]
    ws1.cell(idx, 4).value = r["fid"]
    ws1.cell(idx, 5).value = r["fname"]
    ws1.cell(idx, 6).value = r["sprint"]
    ws1.cell(idx, 7).value = r["dev_type"]
    ws1.cell(idx, 8).value = r["fe_user"]
    ws1.cell(idx, 9).value = r["fe_status"]
    ws1.cell(idx, 10).value = r["date"]
    ws1.cell(idx, 11).value = r["be_user"]
    ws1.cell(idx, 12).value = r["be_status"]
    ws1.cell(idx, 13).value = r["date"]
    ws1.cell(idx, 14).value = r["status"]
    ws1.cell(idx, 15).value = r["submitted"]
    idx += 1
print(f"  技术工作日报: {len(tech_rows)} 行")

# ---- Sheet: 测试工作日报（填报）----
test_rows = build_test_daily()
sheet_name2 = "测试工作日报（填报）"
if sheet_name2 in wb.sheetnames:
    del wb[sheet_name2]
ws2 = wb.create_sheet(sheet_name2)

headers2 = ["日期", "iid", "子系统", "功能点号", "详细功能点", "缺陷标题",
            "优先级", "测试人员", "修复人员", "状态"]
for c, h in enumerate(headers2, 1):
    ws2.cell(1, c).value = h

idx = 2
for r in test_rows:
    ws2.cell(idx, 1).value = r.get("date", "")
    ws2.cell(idx, 2).value = r.get("iid", "")
    ws2.cell(idx, 3).value = r.get("subsystem", "")
    ws2.cell(idx, 4).value = r.get("fid", "")
    ws2.cell(idx, 5).value = r.get("fname", "")
    ws2.cell(idx, 6).value = r.get("title", "")
    ws2.cell(idx, 7).value = r.get("priority", "")
    ws2.cell(idx, 8).value = r.get("tester", "")
    ws2.cell(idx, 9).value = r.get("fix_user", "")
    ws2.cell(idx, 10).value = r.get("status", "")
    idx += 1
print(f"  测试工作日报: {len(test_rows)} 行")

try:
    wb.save(EXCEL_PATH)
    print(f"\n已保存: {EXCEL_PATH}")
except PermissionError:
    alt = EXCEL_PATH.replace("_new.xlsx", "_new3.xlsx")
    wb.save(alt)
    print(f"\n已保存到: {alt}")
