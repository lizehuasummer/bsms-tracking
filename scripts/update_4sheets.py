"""
独立脚本：只更新前 4 个 Sheet（issue / Sprint详细安排 / EX开发功能点 / bug）

用法：
  python update_4sheets.py              # 使用缓存
  python update_4sheets.py --fresh       # 删除缓存，重新抓取
  python update_4sheets.py --excel-only  # 仅用缓存填表，跳过抓取
"""
import json, re, time, os, sys, requests, urllib3, openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
urllib3.disable_warnings()

# ============ 配置 ============
GITLAB_URL = "https://gitlab.stpass.com"
GITLAB_TOKEN = "glpat-rO7mGLMblvELQu1iJbGMY286MQp1OnEH.01.0w0x3iets"
PROJECT_ID = 4
EXCEL_PATH = r"D:\Users\LZH\Documents\opencode\bsms_tracking\【交付HK】BSMS项目整体进度计划 (更新中)20260702备份_new.xlsx"
CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
ISSUES_CACHE = os.path.join(CACHE_DIR, "gitlab_issues_cache.json")
NOTES_CACHE = os.path.join(CACHE_DIR, "gitlab_notes_cache.json")
CONCURRENT = 10

session = requests.Session()
session.headers.update({"Private-Token": GITLAB_TOKEN})
session.verify = False

# ============ GitLab API ============
def fetch_all_issues(label=None, state="all"):
    """获取全部 issue。label=None 时不按 label 过滤，获取全部。"""
    all_issues = []
    page = 1
    params = {"state": state, "per_page": 100, "page": page}
    if label:
        params["labels"] = label
    while True:
        r = session.get(
            f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues",
            params=params, timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        all_issues.extend(data)
        total = int(r.headers.get("X-Total-Pages", "1"))
        tag = f"all({label})" if label else "all"
        print(f"  {tag} page {page}/{total} ({len(all_issues)}/{r.headers.get('X-Total', '?')})")
        if page >= total:
            break
        page += 1
        params["page"] = page
    return all_issues


def fetch_issue_notes(iid):
    key = str(iid)
    try:
        r1 = session.get(
            f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues/{iid}/notes",
            params={"per_page": 100, "sort": "asc", "order_by": "created_at"},
            timeout=15,
        )
        r1.raise_for_status()
        r2 = session.get(
            f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues/{iid}/resource_label_events",
            params={"per_page": 100},
            timeout=15,
        )
        r2.raise_for_status()
        return key, {"notes": r1.json(), "label_events": r2.json()}
    except Exception as e:
        print(f"  ERR iid {iid}: {e}")
        return key, {"notes": [], "label_events": []}


# ============ 解析工具 ============
def fmt_time(t):
    if not t:
        return None
    return t[:16].replace("T", " ")


def extract_feature_id(title):
    if not title:
        return None
    m = re.search(r"([A-Z0-9]{2,5}-[A-Z]{1,5}\d{1,4}(?:-\d+)?)", title)
    return m.group(1) if m else None


def parse_status_from_notes(notes):
    changes = []
    for note in notes:
        if not note.get("system"):
            continue
        m = re.search(r"set status to \*\*(.+?)\*\*", note.get("body", ""))
        if m:
            changes.append({
                "status": m.group(1),
                "time": note["created_at"],
                "user": note.get("author", {}).get("username", ""),
            })
    return changes


def parse_processpass_from_events(events):
    result = []
    for ev in events:
        if ev.get("label", {}).get("name") == "Process::pass" and ev.get("action") == "add":
            result.append({"time": ev["created_at"], "user": ev.get("user", {}).get("username", "")})
    return result


def calc_duration(created_at, done_sc, issue_closed_at):
    start = created_at[:10] if created_at else None
    if done_sc:
        end = done_sc["time"][:10]
    elif issue_closed_at:
        end = issue_closed_at[:10]
    else:
        from datetime import datetime
        end = datetime.now().strftime("%Y-%m-%d")
    if not start:
        return ""
    try:
        from datetime import datetime
        d1 = datetime.strptime(start, "%Y-%m-%d")
        d2 = datetime.strptime(end, "%Y-%m-%d")
        days = (d2 - d1).days
        if days < 0:
            days = 0
        return f"{days}天"
    except:
        return ""


def find_last(items, status_name):
    for item in reversed(items):
        if item["status"] == status_name:
            return item
    return None


# ============ 生成 issue sheet 的工具 ============
def extract_activity_records(notes, label_events):
    """
    将所有 notes + label_events 合并为活动列表，按时间排序。
    每项: {time, user, content}
    """
    activities = []
    for note in notes:
        activities.append({
            "time": note.get("created_at", ""),
            "user": note.get("author", {}).get("username", ""),
            "content": note.get("body", ""),
        })
    for ev in label_events:
        lbl_obj = ev.get("label")
        lbl_name = lbl_obj.get("name", "") if lbl_obj else ""
        action = ev.get("action", "")
        desc = f"{action} label **{lbl_name}**" if lbl_name else ""
        activities.append({
            "time": ev.get("created_at", ""),
            "user": ev.get("user", {}).get("username", ""),
            "content": desc,
        })
    activities.sort(key=lambda x: x["time"])
    return activities


def get_subsystem(labels):
    for lbl in labels:
        if lbl.startswith("BSMS::"):
            return lbl.replace("BSMS::", "")
    return ""


def get_source_labels(labels):
    """提取 功能点来源 标签（Bug::dev / Function::dev / Change::dev / Story::dev）"""
    sources = [lbl for lbl in labels if lbl in ("Bug::dev", "Function::dev", "Change::dev", "Story::dev")]
    return sources


def get_priority(labels):
    for lbl in labels:
        if lbl.startswith("Priority::"):
            return lbl
    return ""


# ============ 主流程 ============
def step1_fetch_all_issues():
    """获取项目下所有 issue（不含 label 过滤），同时获取 Function::dev + Bug::dev 用于后续 sheet。"""
    cache_file = ISSUES_CACHE
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < 3600:
            print("[1] 加载 issues 缓存...")
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
            return cache.get("all", []), cache.get("functiondev", []), cache.get("bugdev", [])

    print("[1] 抓取 GitLab 全部 issues...")
    all_issues = fetch_all_issues()
    func_issues = [i for i in all_issues if "Function::dev" in i.get("labels", [])]
    bug_issues = [i for i in all_issues if "Bug::dev" in i.get("labels", [])]
    print(f"  总计: {len(all_issues)}, Function::dev: {len(func_issues)}, Bug::dev: {len(bug_issues)}")

    # 写入缓存
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"all": all_issues, "functiondev": func_issues, "bugdev": bug_issues}, f, ensure_ascii=False)

    return all_issues, func_issues, bug_issues


def step2_fetch_notes(all_issues):
    print("[2] 抓取 notes + label events...")

    if os.path.exists(NOTES_CACHE):
        with open(NOTES_CACHE, "r", encoding="utf-8") as f:
            notes_cache = json.load(f)
    else:
        notes_cache = {}

    all_iids = [i["iid"] for i in all_issues]
    to_fetch = [iid for iid in all_iids if str(iid) not in notes_cache]
    print(f"  已缓存: {len(notes_cache)}, 需抓取: {len(to_fetch)}")

    if not to_fetch:
        print("  全部已缓存，跳过")
        return notes_cache

    fetched = 0
    with ThreadPoolExecutor(max_workers=CONCURRENT) as executor:
        futures = {executor.submit(fetch_issue_notes, iid): iid for iid in to_fetch}
        for future in as_completed(futures):
            key, data = future.result()
            notes_cache[key] = data
            fetched += 1
            if fetched % 100 == 0:
                print(f"  进度: {fetched}/{len(to_fetch)}")
                with open(NOTES_CACHE, "w", encoding="utf-8") as f:
                    json.dump(notes_cache, f, ensure_ascii=False)

    with open(NOTES_CACHE, "w", encoding="utf-8") as f:
        json.dump(notes_cache, f, ensure_ascii=False)
    print(f"  完成，总缓存: {len(notes_cache)}")

    return notes_cache


def shift_columns_right(ws, start_col=9, shift=1):
    """Shift all content in worksheet to the right from start_col."""
    merges_to_shift = []
    for mr in list(ws.merged_cells.ranges):
        if mr.min_col >= start_col:
            merges_to_shift.append((mr.min_row, mr.max_row, mr.min_col, mr.max_col))
            ws.unmerge_cells(str(mr))

    for row in range(1, ws.max_row + 1):
        for col in range(ws.max_column, start_col - 1, -1):
            source = ws.cell(row, col)
            target = ws.cell(row, col + shift)
            target.value = source.value
            source.value = None

    for min_row, max_row, min_col, max_col in merges_to_shift:
        ws.merge_cells(start_row=min_row, start_column=min_col + shift,
                       end_row=max_row, end_column=max_col + shift)


def stage_status(latest_status, current_labels):
    """Map gitlab status to 5-stage progressive status."""
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


def step3_fill_excel(all_issues, func_issues, bug_issues, notes_cache):
    print("[3] 填写 4 个 Sheet...")

    # ---- 预处理：功能点编号索引
    func_by_fid = {}
    for issue in func_issues:
        fid = extract_feature_id(issue.get("title", ""))
        if fid:
            func_by_fid.setdefault(fid, []).append(issue)
    print(f"  Function::dev 功能点编号: {len(func_by_fid)} 个")

    wb = openpyxl.load_workbook(EXCEL_PATH)

    # ===================== Sheet 1: issue =====================
    print("\n  --- Sheet 1: issue ---")
    if "issue" in wb.sheetnames:
        del wb["issue"]
    ws_issue = wb.create_sheet("issue", 0)  # 插入到最前面

    # 写表头（252列 = 9个固定列 + 81组×3列记录）
    issue_headers = ["子系统", "issue编号", "issue标题", "功能点",
                     "功能点来源1", "功能点来源2", "功能点来源3", "优先级", "最新状态"]
    for ri in range(1, 82):
        issue_headers.extend([f"记录{ri}时间", f"记录{ri}操作人", f"记录{ri}内容"])
    for ci, h in enumerate(issue_headers, 1):
        ws_issue.cell(1, ci, value=h)

    # 写数据
    row_idx = 2
    for issue in all_issues:
        iid = issue["iid"]
        title = issue.get("title", "")
        labels = issue.get("labels", [])
        key = str(iid)
        cdata = notes_cache.get(key, {"notes": [], "label_events": []})
        notes = cdata.get("notes", [])
        label_events = cdata.get("label_events", [])

        # 固定列
        ws_issue.cell(row_idx, 1, value=get_subsystem(labels))
        ws_issue.cell(row_idx, 2, value=f"#{iid}")
        ws_issue.cell(row_idx, 3, value=title)
        ws_issue.cell(row_idx, 4, value=extract_feature_id(title))

        sources = get_source_labels(labels)
        for si in range(3):
            if si < len(sources):
                ws_issue.cell(row_idx, 5 + si, value=sources[si])

        ws_issue.cell(row_idx, 8, value=get_priority(labels))

        # 最新状态
        status_changes = parse_status_from_notes(notes)
        if status_changes:
            ws_issue.cell(row_idx, 9, value=status_changes[-1]["status"])

        # 活动记录
        activities = extract_activity_records(notes, label_events)
        for ai, act in enumerate(activities[:81]):
            base = 10 + ai * 3
            ws_issue.cell(row_idx, base, value=fmt_time(act["time"]))
            ws_issue.cell(row_idx, base + 1, value=act["user"])
            ws_issue.cell(row_idx, base + 2, value=act["content"])

        row_idx += 1
        if row_idx % 500 == 0:
            print(f"  issue 进度: {row_idx - 2}/{len(all_issues)}")

    print(f"  issue: {row_idx - 2} 行")

    # ===================== Sheet 2: Sprint详细安排 =====================
    print("\n  --- Sheet 2: Sprint详细安排 ---")
    ws1 = None
    for name in wb.sheetnames:
        if "Sprint" in name or "sprint" in name:
            ws1 = wb[name]
            break
    if ws1:
        # 插入 iid 列（H列后），幂等：如果已存在则跳过
        if ws1.cell(1, 9).value != "iid":
            shift_columns_right(ws1, 9)
            ws1.cell(1, 9).value = "iid"
            ws1.cell(2, 9).value = ""

        matched1 = 0
        for row in range(5, ws1.max_row + 1):
            fid = ws1.cell(row, 5).value
            fname = ws1.cell(row, 6).value
            if not fid:
                continue
            fid = str(fid).strip()
            candidates = func_by_fid.get(fid, [])
            used_suffix = False
            if not candidates:
                base = re.sub(r'-\d+$', '', fid)
                if base != fid:
                    candidates = func_by_fid.get(base, [])
                    used_suffix = True
            if not candidates:
                ws1.cell(row, 9).value = "N/A"
                ws1.cell(row, 10).value = None
                continue

            matched_issue = candidates[0]
            # 后缀截断匹配：若 issue 标题不含原始 fid（如 DMM-F081-1），视为无匹配 → N/A
            if used_suffix:
                t_fid = extract_feature_id(matched_issue.get("title", ""))
                if t_fid and t_fid != fid:
                    ws1.cell(row, 9).value = "N/A"
                    ws1.cell(row, 10).value = None
                    continue
            if len(candidates) > 1 and fname:
                for c in candidates:
                    if str(fname).strip() in c.get("title", ""):
                        matched_issue = c
                        break

            key = str(matched_issue["iid"])
            cdata = notes_cache.get(key, {"notes": [], "label_events": []})
            status_changes = parse_status_from_notes(cdata.get("notes", []))
            pass_events = parse_processpass_from_events(cdata.get("label_events", []))
            current_labels = set(matched_issue.get("labels", []))

            # I 列: iid
            ws1.cell(row, 9).value = f"#{matched_issue['iid']}"

            # H 列: 根据 GitLab Sprint:: 标签更新（优先标准格式 Sprint::）
            sprint_label = None
            for lbl in sorted(current_labels, key=lambda x: 0 if x.startswith("Sprint::") else 1):
                if lbl.startswith("Sprint::") or lbl.startswith("sprint::"):
                    sprint_label = lbl.split("::")[1].lstrip("0")
                    break
            if sprint_label:
                ws1.cell(row, 8).value = f"sprint{sprint_label}"

            # J 列: 5 阶段渐进状态（若gitlab已closed则视为已完成）
            if matched_issue.get("state") == "closed":
                display_status = "已完成"
            else:
                latest_status = status_changes[-1]["status"] if status_changes else None
                display_status = stage_status(latest_status, current_labels)
            ws1.cell(row, 10).value = display_status

            # M/N: 测试中
            test_sc = find_last(status_changes, "测试中")
            if test_sc:
                ws1.cell(row, 14).value = fmt_time(test_sc["time"])
                ws1.cell(row, 13).value = test_sc["user"]

            # O/P: Process::pass
            if pass_events:
                ws1.cell(row, 16).value = fmt_time(pass_events[-1]["time"])
                ws1.cell(row, 15).value = pass_events[-1]["user"]

            # S/T: 已完成
            done_sc = find_last(status_changes, "已完成")
            if done_sc:
                ws1.cell(row, 20).value = fmt_time(done_sc["time"])
                ws1.cell(row, 19).value = done_sc["user"]

            matched1 += 1
        print(f"  匹配: {matched1}")

    # ===================== Sheet 3: EX开发功能点 =====================
    print("\n  --- Sheet 3: EX开发功能点 ---")
    ws2 = None
    for name in wb.sheetnames:
        if "EX" in name:
            ws2 = wb[name]
            break
    if ws2:
        # 插入 iid 列（H列后），幂等：如果已存在则跳过
        if ws2.cell(2, 9).value != "iid":
            shift_columns_right(ws2, 9)
            ws2.cell(2, 9).value = "iid"
            ws2.cell(3, 9).value = None
            ws2.cell(4, 9).value = None

        matched2 = 0
        for row in range(5, ws2.max_row + 1):
            fid = ws2.cell(row, 5).value
            fname = ws2.cell(row, 6).value
            if not fid:
                continue
            fid = str(fid).strip()
            candidates = func_by_fid.get(fid, [])
            used_suffix = False
            if not candidates:
                base = re.sub(r'-\d+$', '', fid)
                if base != fid:
                    candidates = func_by_fid.get(base, [])
                    used_suffix = True
            if not candidates:
                ws2.cell(row, 9).value = "N/A"
                ws2.cell(row, 10).value = None
                continue

            matched_issue = candidates[0]
            if used_suffix:
                t_fid = extract_feature_id(matched_issue.get("title", ""))
                if t_fid and t_fid != fid:
                    ws2.cell(row, 9).value = "N/A"
                    ws2.cell(row, 10).value = None
                    continue
            if len(candidates) > 1 and fname:
                for c in candidates:
                    if str(fname).strip() in c.get("title", ""):
                        matched_issue = c
                        break

            key = str(matched_issue["iid"])
            cdata = notes_cache.get(key, {"notes": [], "label_events": []})
            status_changes = parse_status_from_notes(cdata.get("notes", []))
            pass_events = parse_processpass_from_events(cdata.get("label_events", []))
            current_labels = set(matched_issue.get("labels", []))

            # I 列: iid
            ws2.cell(row, 9).value = f"#{matched_issue['iid']}"

            # H 列: 根据 GitLab Sprint:: 标签更新
            sprint_label = None
            for lbl in sorted(current_labels, key=lambda x: 0 if x.startswith("Sprint::") else 1):
                if lbl.startswith("Sprint::") or lbl.startswith("sprint::"):
                    sprint_label = lbl.split("::")[1].lstrip("0")
                    break
            if sprint_label:
                ws2.cell(row, 8).value = f"sprint{sprint_label}"

            # J 列: 5 阶段渐进状态
            if matched_issue.get("state") == "closed":
                display_status = "已完成"
            else:
                latest_status = status_changes[-1]["status"] if status_changes else None
                display_status = stage_status(latest_status, current_labels)
            ws2.cell(row, 10).value = display_status

            # M/N: 测试中
            test_sc = find_last(status_changes, "测试中")
            if test_sc:
                ws2.cell(row, 14).value = fmt_time(test_sc["time"])
                ws2.cell(row, 13).value = test_sc["user"]

            # O/P: Process::pass
            if pass_events:
                ws2.cell(row, 16).value = fmt_time(pass_events[-1]["time"])
                ws2.cell(row, 15).value = pass_events[-1]["user"]

            # S/T: 已完成
            done_sc = find_last(status_changes, "已完成")
            if done_sc:
                ws2.cell(row, 20).value = fmt_time(done_sc["time"])
                ws2.cell(row, 19).value = done_sc["user"]

            matched2 += 1
        print(f"  匹配: {matched2}")

    # ===================== Sheet 4: bug =====================
    print("\n  --- Sheet 4: bug ---")
    ws3 = None
    for name in wb.sheetnames:
        if name.lower() == "bug":
            ws3 = wb[name]
            break
    if ws3:
        # 清空
        for row in range(2, ws3.max_row + 1):
            for col in range(1, 15):
                cell = ws3.cell(row, col)
                if not isinstance(cell, openpyxl.cell.cell.MergedCell):
                    cell.value = None

        bug_row = 2
        for issue in bug_issues:
            key = str(issue["iid"])
            cdata = notes_cache.get(key, {"notes": [], "label_events": []})
            status_changes = parse_status_from_notes(cdata.get("notes", []))

            subsystem = priority = None
            for lbl in issue.get("labels", []):
                if lbl.startswith("BSMS::"):
                    subsystem = lbl.replace("BSMS::", "")
                elif lbl.startswith("Priority::"):
                    priority = lbl.replace("Priority::", "")

            latest_status = status_changes[-1]["status"] if status_changes else issue.get("state", "")

            fix_sc = find_last(status_changes, "待修复")
            test_sc = find_last(status_changes, "测试中")
            done_sc = find_last(status_changes, "已完成")

            ws3.cell(bug_row, 1).value = subsystem
            ws3.cell(bug_row, 2).value = f"#{issue['iid']}"
            ws3.cell(bug_row, 3).value = issue.get("title", "")
            ws3.cell(bug_row, 4).value = priority
            ws3.cell(bug_row, 5).value = latest_status
            ws3.cell(bug_row, 6).value = issue.get("author", {}).get("username", "")
            ws3.cell(bug_row, 7).value = fmt_time(issue.get("created_at"))

            if fix_sc:
                ws3.cell(bug_row, 8).value = fix_sc["user"]
                ws3.cell(bug_row, 9).value = fmt_time(fix_sc["time"])
            if test_sc:
                ws3.cell(bug_row, 10).value = test_sc["user"]
                ws3.cell(bug_row, 11).value = fmt_time(test_sc["time"])
            if done_sc:
                ws3.cell(bug_row, 12).value = done_sc["user"]
                ws3.cell(bug_row, 13).value = fmt_time(done_sc["time"])

            duration = calc_duration(issue.get("created_at"), done_sc, issue.get("closed_at"))
            ws3.cell(bug_row, 14).value = duration

            bug_row += 1
        print(f"  Bug 行数: {bug_row - 2}")

    # ===== 技术工作日报 & 测试工作日报 =====
    print("\n  --- 5/6: 技术工作日报（填报）---")
    try:
        _generate_tech_daily(wb, func_issues, notes_cache)
    except Exception as e:
        print(f"  [SKIP] 技术工作日报出错: {e}")

    print("  --- 6/6: 测试工作日报（填报）---")
    try:
        _generate_test_daily(wb, func_issues, bug_issues, notes_cache)
    except Exception as e:
        print(f"  [SKIP] 测试工作日报出错: {e}")

    # ===== 保存 =====
    try:
        wb.save(EXCEL_PATH)
        print(f"\n  已保存: {EXCEL_PATH}")
    except PermissionError:
        alt = EXCEL_PATH.replace("_new.xlsx", "_new3.xlsx")
        wb.save(alt)
        print(f"\n  原文件被占用，已保存到: {alt}")


def main():
    fresh = "--fresh" in sys.argv
    excel_only = "--excel-only" in sys.argv

    if fresh:
        for f in [ISSUES_CACHE, NOTES_CACHE]:
            if os.path.exists(f):
                os.remove(f)
                print(f"已删除缓存: {f}")

    if not excel_only:
        all_issues, func_issues, bug_issues = step1_fetch_all_issues()
        notes_cache = step2_fetch_notes(all_issues)
    else:
        print("[1] 仅使用缓存填表")
        with open(ISSUES_CACHE, "r", encoding="utf-8") as f:
            ic = json.load(f)
        all_issues = ic["all"]
        func_issues = ic["functiondev"]
        bug_issues = ic["bugdev"]
        with open(NOTES_CACHE, "r", encoding="utf-8") as f:
            notes_cache = json.load(f)

    print(f"\n  总计: {len(all_issues)}, Function::dev: {len(func_issues)}, Bug::dev: {len(bug_issues)}, Notes: {len(notes_cache)}")

    # 更新 Excel 4 个 Sheet + 日报
    step3_fill_excel(all_issues, func_issues, bug_issues, notes_cache)

def _generate_tech_daily(wb, func_issues, notes_cache):
    """技术工作日报（填报）：按 issue Activity 逐日填充"""
    from collections import defaultdict

    def _status_changes(notes):
        ch = []
        for n in notes:
            if not n.get("system"): continue
            m = re.search(r"set status to \*\*(.+?)\*\*", n.get("body", ""))
            if m:
                ch.append({"status": m.group(1), "time": n["created_at"], "user": n.get("author",{}).get("username","")})
        return ch

    def _pass_events(events):
        return [{"time": e["created_at"], "user": e.get("user",{}).get("username","")} for e in events
                if e.get("label",{}).get("name") == "Process::pass" and e.get("action") == "add"]

    def _subsys(labels):
        for l in labels:
            if l.startswith("BSMS::"): return l.replace("BSMS::", "")
        return ""

    rows = []
    for issue in func_issues:
        iid = issue["iid"]
        labels = set(issue.get("labels", []))
        fid = extract_feature_id(issue.get("title", ""))
        fname = issue.get("title", "")[len(fid)+1:] if fid and fid+" " in issue.get("title","") else issue.get("title","")
        sub = _subsys(labels)

        key = str(iid)
        cd = notes_cache.get(key, {"notes":[], "label_events":[]})
        sc = _status_changes(cd.get("notes", []))
        events = cd.get("label_events", [])

        act = []
        for s in sc:
            act.append({"time": s["time"], "type":"status","status":s["status"],"user":s["user"]})
        for ev in events:
            ln = ev.get("label",{}).get("name","")
            a = ev.get("action","")
            if a == "add" and ln in ("front::finished","backend::finished"):
                act.append({"time": ev["created_at"], "type":ln,"user":ev.get("user",{}).get("username","")})
        act.sort(key=lambda x: x["time"])

        daily = defaultdict(list)
        for a in act:
            d = a["time"][:10] if a["time"] else ""
            if d: daily[d].append(a)

        dt = "前+后端"
        fe_u = be_u = ""
        for a in act:
            if a["type"] == "front::finished": fe_u = a["user"]
            elif a["type"] == "backend::finished": be_u = a["user"]
        if fe_u and not be_u: dt = "前端"
        elif be_u and not fe_u: dt = "后端"
        elif "Port::fullstack" in labels: dt = "前+后端"
        elif "Port::frontend" in labels: dt = "前端"
        elif "Port::backend" in labels: dt = "后端"

        sprint = ""
        for lbl in sorted(labels, key=lambda x: 0 if x.startswith("Sprint::") else 1):
            if lbl.startswith("Sprint::") or lbl.startswith("sprint::"):
                sprint = "Sprint " + lbl.split("::")[1].lstrip("0")
                break

        pe = _pass_events(events)
        for d in sorted(daily.keys()):
            acts = daily[d]
            last_st = None
            for a in sorted(acts, key=lambda x: x["time"]):
                if a["type"] == "status": last_st = a["status"]
            fs = "已完成" if any(a["type"]=="front::finished" for a in acts) else (stage_status(last_st, labels) if last_st else "待开发")
            bs = "已完成" if any(a["type"]=="backend::finished" for a in acts) else (stage_status(last_st, labels) if last_st else "待开发")
            sub_test = "是" if any(pd[:10] <= d for pd in [p["time"] for p in pe]) else ""
            rows.append({"date":d, "iid":iid, "sub":sub, "fid":fid, "fname":fname, "sprint":sprint,
                         "dt":dt, "fe_u":fe_u, "fs":fs, "be_u":be_u, "bs":bs, "st":last_st or "", "sub_test":sub_test})

    rows.sort(key=lambda x: (x["date"], x["iid"]))
    sn = "技术工作日报（填报）"
    if sn in wb.sheetnames: del wb[sn]
    ws = wb.create_sheet(sn)
    for c, h in enumerate(["日期","iid","子系统","功能点号","详细功能点","开发计划","开发类型",
                           "前端负责人","前端开发完成状态","登记时间","后端负责人","后端开发完成状态","登记时间","当前状态","是否提交测试"], 1):
        ws.cell(1, c).value = h
    for i, r in enumerate(rows, 2):
        for c, v in [(1,r["date"]),(2,r["iid"]),(3,r["sub"]),(4,r["fid"]),(5,r["fname"]),(6,r["sprint"]),
                     (7,r["dt"]),(8,r["fe_u"]),(9,r["fs"]),(10,r["date"]),(11,r["be_u"]),(12,r["bs"]),
                     (13,r["date"]),(14,r["st"]),(15,r["sub_test"])]:
            ws.cell(i, c).value = v
    print(f"  技术工作日报: {len(rows)} 行")


def _generate_test_daily(wb, func_issues, bug_issues, notes_cache):
    """测试工作日报（填报）：按 Bug 创建日 + 功能测试日填充"""
    from collections import defaultdict

    def _subsys(labels):
        for l in labels:
            if l.startswith("BSMS::"): return l.replace("BSMS::", "")
        return ""

    rows = []
    # Bug issues
    for bug in bug_issues:
        iid = bug["iid"]
        labels = set(bug.get("labels", []))
        title = bug.get("title", "")
        fid = extract_feature_id(title)
        sub = _subsys(labels)
        d = bug.get("created_at", "")[:10]
        priority = next((l.replace("Priority::","") for l in labels if l.startswith("Priority::")), "")

        key = str(iid)
        cd = notes_cache.get(key, {"notes":[], "label_events":[]})
        sc = []
        for n in cd.get("notes", []):
            if n.get("system"):
                m = re.search(r"set status to \*\*(.+?)\*\*", n.get("body", ""))
                if m:
                    sc.append({"status": m.group(1), "time": n["created_at"], "user": n.get("author",{}).get("username","")})

        tester = ""
        fix_user = ""
        for s in reversed(sc):
            if s["status"] == "测试中" and not tester: tester = s["user"]
            if s["status"] == "已完成" and not fix_user: fix_user = s["user"]

        rows.append({"date":d, "iid":iid, "sub":sub, "fid":fid, "title":title,
                     "priority":priority, "tester":tester, "fix_user":fix_user,
                     "status":"待修复" if bug.get("state")=="opened" else "已修复"})

    # Function::dev Process::pass events as 功能测试 records
    for issue in func_issues:
        iid = issue["iid"]
        labels = set(issue.get("labels", []))
        fid = extract_feature_id(issue.get("title", ""))
        sub = _subsys(labels)
        key = str(iid)
        cd = notes_cache.get(key, {"notes":[], "label_events":[]})
        for ev in cd.get("label_events", []):
            if ev.get("label",{}).get("name") == "Process::pass" and ev.get("action") == "add":
                d = ev.get("created_at","")[:10]
                u = ev.get("user",{}).get("username","")
                # dedup
                if not any(r.get("date")==d and r.get("iid")==iid and r.get("type")=="func_test" for r in rows):
                    rows.append({"date":d, "iid":iid, "sub":sub, "fid":fid, "title":issue.get("title",""),
                                 "priority":"", "tester":u, "fix_user":"", "status":"完成测试", "type":"func_test"})

    rows.sort(key=lambda x: (x.get("date",""), x.get("iid",0)))
    sn = "测试工作日报（填报）"
    if sn in wb.sheetnames: del wb[sn]
    ws = wb.create_sheet(sn)
    for c, h in enumerate(["日期","iid","子系统","功能点号","缺陷标题","优先级","测试人员","修复人员","状态"], 1):
        ws.cell(1, c).value = h
    for i, r in enumerate(rows, 2):
        for c, v in [(1,r.get("date","")),(2,r.get("iid","")),(3,r.get("sub","")),(4,r.get("fid","")),
                     (5,r.get("title","")),(6,r.get("priority","")),(7,r.get("tester","")),
                     (8,r.get("fix_user","")),(9,r.get("status",""))]:
            ws.cell(i, c).value = v
    print(f"  测试工作日报: {len(rows)} 行")


if __name__ == "__main__":
    main()
