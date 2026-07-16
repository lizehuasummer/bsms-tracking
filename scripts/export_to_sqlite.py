"""
Read JSON caches (issues + notes) and write to SQLite.
Pre-computes all dashboard data for fast serving by FastAPI.
"""
import json, os, re, sys, datetime, sqlite3
from collections import defaultdict

CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(SCRIPTS_DIR), "web", "bsms.db")

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


def build_dashboards(conn, issue_data, notes_cache):
    print("  Building dashboards...")

    all_dates = set()
    for issue in issue_data:
        created = issue.get("created_at", "")
        if created:
            all_dates.add(date_str(created))

    # Enrich with parsed data
    enriched = []
    for issue in issue_data:
        iid = issue["iid"]
        key = str(iid)
        cdata = notes_cache.get(key, {"notes": [], "label_events": []})
        sys_notes = parse_notes(cdata.get("notes", []))
        label_evts = parse_label_events(cdata.get("label_events", []))
        labels = set(issue.get("labels", []))
        created = issue.get("created_at", "")
        closed = issue.get("closed_at")

        all_activities = []
        for n in sys_notes:
            all_activities.append({"time": n["time"], "user": n["user"], "type": "note", "body": n["body"]})
        for ev in label_evts:
            all_activities.append({"time": ev["time"], "user": ev["user"], "type": "label", "label": ev["label"], "action": ev["action"]})
        all_activities.sort(key=lambda x: x["time"])

        daily_notes = defaultdict(list)
        for note in sys_notes:
            ds = date_str(note["time"])
            if ds:
                daily_notes[ds].append(note)
        daily_label_events = defaultdict(list)
        for ev in label_evts:
            ds = date_str(ev["time"])
            if ds:
                daily_label_events[ds].append(ev)

        enriched.append({
            "iid": iid,
            "labels": labels,
            "created": created,
            "closed": closed,
            "sys_notes": sys_notes,
            "label_events": label_evts,
            "all_activities": all_activities,
            "daily_notes": dict(daily_notes),
            "daily_label_events": dict(daily_label_events),
        })

    # Date range
    min_date = min(all_dates)
    max_date = date_str(datetime.datetime.now().isoformat())
    start = datetime.datetime.strptime(min_date, "%Y-%m-%d")
    end = datetime.datetime.strptime(max_date, "%Y-%m-%d")
    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += datetime.timedelta(days=1)

    # Timelines
    func_timelines = {}
    func_status_timelines = {}
    func_pass_timelines = {}
    bug_status_timelines = {}

    for issue in enriched:
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

        tl2 = []
        for note in issue["sys_notes"]:
            m = re.search(r"set status to \*\*(.+?)\*\*", note["body"])
            if m:
                ds = date_str(note["time"])
                if ds:
                    tl2.append((ds, m.group(1)))
        tl2.sort(key=lambda x: x[0])
        func_status_timelines[iid] = tl2

        tl3 = []
        for ev in issue["label_events"]:
            if ev["label"] == "Process::pass":
                ds = date_str(ev["time"])
                if ds:
                    tl3.append((ds, ev["action"]))
        tl3.sort(key=lambda x: x[0])
        func_pass_timelines[iid] = tl3

    for issue in enriched:
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

    def get_latest_status_as_of(iid, ds):
        latest = None
        for entry in func_status_timelines.get(iid, []):
            if entry[0] > ds:
                break
            latest = entry[1]
        return latest

    def has_pass_as_of(iid, ds):
        has_pass = False
        for entry in func_pass_timelines.get(iid, []):
            if entry[0] > ds:
                break
            if entry[1] == "add":
                has_pass = True
            elif entry[1] == "remove":
                has_pass = False
        return has_pass

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

    FUNC_KNOWN_STATUSES = {STATUS_DEV, STATUS_DEVING, STATUS_TESTING, STATUS_DONE}
    BUG_KNOWN_STATUSES = {STATUS_FIX, STATUS_TESTING, STATUS_DONE}

    dev_rows = []
    test_rows = []
    status_rows = []

    for di, ds in enumerate(dates):
        # Dev dashboard
        dev_b = sum(1 for issue in enriched
                    if "Function::dev" in issue["labels"]
                    and date_str(issue["created"]) == ds)

        dev_c = 0
        for issue in enriched:
            if "Function::dev" not in issue["labels"]:
                continue
            for ev in issue["daily_label_events"].get(ds, []):
                if ev["label"] == "front::finished" and ev["action"] == "add" and ev["user"] in FRONTEND_USERS:
                    dev_c += 1
                    break

        dev_d = 0
        for issue in enriched:
            if "Function::dev" not in issue["labels"]:
                continue
            for ev in issue["daily_label_events"].get(ds, []):
                if ev["label"] == "backend::finished" and ev["action"] == "add" and ev["user"] in BACKEND_USERS:
                    dev_d += 1
                    break

        dev_e = 0
        for issue in enriched:
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
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for ev in issue["daily_label_events"].get(ds, []):
                if ev["action"] == "add" and ev["label"].startswith("Priority::"):
                    p = ev["label"].replace("Priority::", "")
                    if p in p_counts:
                        p_counts[p] += 1

        dev_i = sum(p_counts.values())
        dev_j = sum(p_counts[p] for p in ["P0", "P1", "P2"])

        dev_k = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for ev in issue["daily_label_events"].get(ds, []):
                if ev["action"] == "remove" and ev["label"].startswith("Priority::"):
                    dev_k += 1
                    break

        dev_l = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for note in issue["daily_notes"].get(ds, []):
                if "set status to **待修复**" in note["body"]:
                    dev_l += 1
                    break

        dev_m = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for ev in issue["daily_label_events"].get(ds, []):
                if ev["label"] == "Process::pass" and ev["action"] == "add":
                    dev_m += 1
                    break

        dev_n = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for note in issue["daily_notes"].get(ds, []):
                if "set status to **已完成**" in note["body"]:
                    dev_n += 1
                    break

        dev_o = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            latest_status = None
            for ds_ev, status in bug_status_timelines.get(issue["iid"], []):
                if ds_ev > ds:
                    break
                latest_status = status
            if issue["closed"] and date_str(issue["closed"]) <= ds:
                pass
            elif latest_status == STATUS_FIX:
                dev_o += 1

        dev_p = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for note in issue["daily_notes"].get(ds, []):
                if "set status to **测试中**" in note["body"]:
                    dev_p += 1
                    break
        dev_q = dev_o

        dev_r = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            closed_ds = date_str(issue["closed"])
            if closed_ds and closed_ds <= ds:
                dev_r += 1

        dev_s = 0
        dev_r_count = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for note in issue["daily_notes"].get(ds, []):
                if f"set status to **{STATUS_DONE}**" in note["body"]:
                    dev_s += 1
                    break
            if issue["closed"] and date_str(issue["closed"]) == ds:
                dev_r_count += 1

        # Dev dashboard extended columns (T-AC)
        dev_func_all = sum(1 for issue in enriched if "Function::dev" in issue["labels"])

        dev_func_open_status = {s: 0 for s in FUNC_KNOWN_STATUSES}
        dev_func_open_total = 0
        dev_func_open_pass = 0
        dev_func_closed_done = 0
        dev_func_closed_total = 0

        for issue in enriched:
            if "Function::dev" not in issue["labels"]:
                continue
            closed_ds = date_str(issue["closed"])
            is_open = closed_ds is None or closed_ds > ds
            latest_status = get_latest_status_as_of(issue["iid"], ds)

            if is_open:
                dev_func_open_total += 1
                if latest_status in dev_func_open_status:
                    dev_func_open_status[latest_status] += 1
                if has_pass_as_of(issue["iid"], ds):
                    dev_func_open_pass += 1
            else:
                dev_func_closed_total += 1
                if latest_status == STATUS_DONE:
                    dev_func_closed_done += 1

        dev_func_open_other = dev_func_open_total - sum(dev_func_open_status.values())
        dev_func_closed_other = dev_func_closed_total - dev_func_closed_done

        dev_rows.append((
            ds, dev_b, dev_c, dev_d, dev_e, dev_f, dev_g, dev_h,
            dev_i, dev_j, dev_k, dev_l, dev_m, dev_n, dev_o, dev_p,
            dev_q, dev_r, dev_s,
            dev_func_all,
            dev_func_open_status[STATUS_DEV],
            dev_func_open_status[STATUS_DEVING],
            dev_func_open_status[STATUS_TESTING],
            dev_func_open_other,
            dev_func_open_total,
            dev_func_open_pass,
            dev_func_closed_done,
            dev_func_closed_other,
            dev_func_closed_total,
        ))

        # Test dashboard
        test_b = dev_e
        test_c = 0
        for issue in enriched:
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
        for issue in enriched:
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
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            done_notes_today = [n for n in issue["daily_notes"].get(ds, []) if f"set status to **{STATUS_DONE}**" in n["body"]]
            if not done_notes_today:
                continue
            labels = issue["labels"]
            for p in range(5):
                if f"Priority::P{p}" in labels:
                    p_done[f"P{p}"] += 1
        test_k = p_done["P0"]
        test_l = p_done["P1"]
        test_m = p_done["P2"]
        test_n = p_done["P3"]
        test_o = p_done["P4"]
        test_p = test_k + test_l + test_m + test_n + test_o

        test_q = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            latest_status = None
            for ds_ev, status in bug_status_timelines.get(issue["iid"], []):
                if ds_ev > ds:
                    break
                latest_status = status
            if issue["closed"] and date_str(issue["closed"]) <= ds:
                pass
            elif latest_status == STATUS_FIX:
                test_q += 1

        test_r = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            if issue["closed"] and date_str(issue["closed"]) <= ds:
                test_r += 1

        # Test total
        test_s = 0
        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            for note in issue["daily_notes"].get(ds, []):
                if f"set status to **{STATUS_DONE}**" in note["body"]:
                    test_s += 1
                    break

        # Bug counts
        bug_total = sum(1 for issue in enriched if "Bug::dev" in issue["labels"])
        bug_open_fix = 0
        bug_open_test = 0
        bug_open_other = 0
        bug_closed_done = 0
        bug_closed_other = 0

        for issue in enriched:
            if "Bug::dev" not in issue["labels"]:
                continue
            closed_ds = date_str(issue["closed"])
            is_open = closed_ds is None or closed_ds > ds
            latest_status = None
            for ds_ev, status in bug_status_timelines.get(issue["iid"], []):
                if ds_ev > ds:
                    break
                latest_status = status
            if is_open:
                if latest_status == STATUS_FIX:
                    bug_open_fix += 1
                elif latest_status == STATUS_TESTING:
                    bug_open_test += 1
                else:
                    bug_open_other += 1
            else:
                if latest_status == STATUS_DONE:
                    bug_closed_done += 1
                else:
                    bug_closed_other += 1

        bug_open_total = bug_open_fix + bug_open_test + bug_open_other
        bug_closed_total = bug_closed_done + bug_closed_other

        test_rows.append((
            ds, test_b, test_c, test_d, test_e, test_f, test_g, test_h,
            test_i, test_j, test_k, test_l, test_m, test_n, test_o,
            test_p, test_q, test_r, test_s,
            bug_total, bug_open_fix, bug_open_test, bug_open_other,
            bug_open_total, bug_closed_done, bug_closed_other, bug_closed_total,
        ))

        # Status change dashboard
        # Bug counts per status
        bug_open_fix_count = 0
        bug_open_test_count = 0
        bug_open_other_count = 0
        bug_closed_fix_count = 0
        bug_closed_test_count = 0
        bug_closed_done_count = 0
        bug_closed_other_count = 0
        func_open_dev_count = 0
        func_open_deving_count = 0
        func_open_testing_count = 0
        func_open_other_count = 0
        func_closed_done_count = 0
        func_closed_other_count = 0
        func_open_pass_count = 0

        for issue in enriched:
            labels = issue["labels"]
            closed_ds = date_str(issue["closed"])
            is_open = closed_ds is None or closed_ds > ds

            if "Bug::dev" in labels:
                latest_status = None
                for ds_ev, status in bug_status_timelines.get(issue["iid"], []):
                    if ds_ev > ds:
                        break
                    latest_status = status
                if is_open:
                    if latest_status == STATUS_FIX:
                        bug_open_fix_count += 1
                    elif latest_status == STATUS_TESTING:
                        bug_open_test_count += 1
                    else:
                        bug_open_other_count += 1
                else:
                    if latest_status == STATUS_FIX:
                        bug_closed_fix_count += 1
                    elif latest_status == STATUS_TESTING:
                        bug_closed_test_count += 1
                    elif latest_status == STATUS_DONE:
                        bug_closed_done_count += 1
                    else:
                        bug_closed_other_count += 1

            if "Function::dev" in labels:
                latest_status = get_latest_status_as_of(issue["iid"], ds)
                has_pass = has_pass_as_of(issue["iid"], ds)
                if is_open:
                    if latest_status == STATUS_DEV:
                        func_open_dev_count += 1
                    elif latest_status == STATUS_DEVING:
                        func_open_deving_count += 1
                    elif latest_status == STATUS_TESTING:
                        func_open_testing_count += 1
                    else:
                        func_open_other_count += 1
                    if has_pass:
                        func_open_pass_count += 1
                else:
                    if latest_status == STATUS_DONE:
                        func_closed_done_count += 1
                    else:
                        func_closed_other_count += 1

        status_rows.append((
            ds,
            bug_open_fix_count, bug_open_test_count, bug_open_other_count,
            bug_open_fix_count + bug_open_test_count + bug_open_other_count,
            bug_closed_fix_count, bug_closed_test_count, bug_closed_done_count,
            bug_closed_other_count,
            bug_closed_fix_count + bug_closed_test_count + bug_closed_done_count + bug_closed_other_count,
            func_open_dev_count, func_open_deving_count, func_open_testing_count,
            func_open_other_count,
            func_open_dev_count + func_open_deving_count + func_open_testing_count + func_open_other_count,
            func_closed_done_count, func_closed_other_count,
            func_closed_done_count + func_closed_other_count,
            func_open_pass_count,
        ))

    # Write dev dashboard
    conn.executemany("""
        INSERT OR REPLACE INTO dev_dashboard VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, dev_rows)

    conn.executemany("""
        INSERT OR REPLACE INTO test_dashboard VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, test_rows)

    conn.executemany("""
        INSERT OR REPLACE INTO status_dashboard VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, status_rows)

    print(f"  Dashboards: {len(dates)} days (dev={len(dev_rows)}, test={len(test_rows)}, status={len(status_rows)})")


def build_daily_reports(conn, issue_data, notes_cache):
    print("  Building daily reports...")
    from gitlab_users import GITLAB_USERS
    username_to_name = {u[3]: u[2] for u in GITLAB_USERS}

    # System mapping from labels
    system_labels = {}
    for u in GITLAB_USERS:
        if u[0] in ("系统开发组（前端）", "系统开发组（后端）") and u[1] and u[4]:
            system_labels[u[4]] = u[1]

    # Tech daily report
    tech_rows = []
    seen = set()
    for issue in issue_data:
        iid = issue["iid"]
        key = str(iid)
        cdata = notes_cache.get(key, {"notes": [], "label_events": []})
        sys_notes = parse_notes(cdata.get("notes", []))
        label_evts = parse_label_events(cdata.get("label_events", []))
        labels = issue.get("labels", [])
        title = issue.get("title", "")

        # Get system and module from title
        system = ""
        func_module = ""
        for lbl in labels:
            if lbl.startswith("BSMS::") and lbl in system_labels:
                system = system_labels[lbl]
                break
        module_match = re.search(r'【(.+?)】', title)
        func_module = module_match.group(1) if module_match else ""

        # Get dev user
        dev_user = ""
        assignee = issue.get("assignee")
        if assignee:
            dev_user = username_to_name.get(assignee.get("username", ""), assignee.get("name", ""))

        events_by_date = defaultdict(list)
        for note in sys_notes:
            ds = date_str(note["time"])
            if ds:
                events_by_date[ds].append(("note", note["user"], note["body"]))
        for ev in label_evts:
            ds = date_str(ev["time"])
            if ds:
                if ev["label"] in ("front::finished", "backend::finished") and ev["action"] == "add":
                    events_by_date[ds].append(("finish", ev["user"], ev["label"]))

        for ds in sorted(events_by_date.keys()):
            if (ds, iid) in seen:
                continue
            seen.add((ds, iid))
            events = events_by_date[ds]
            # determine front/backend user from events
            front_user = ""
            backend_user = ""
            for etype, user, body in events:
                if etype == "finish":
                    label_name = body
                    if label_name == "front::finished" and user in FRONTEND_USERS:
                        front_user = username_to_name.get(user, user)
                    elif label_name == "backend::finished" and user in BACKEND_USERS:
                        backend_user = username_to_name.get(user, user)

            # simplified daily plan from status changes
            dev_plan = ""
            for etype, user, body in events:
                if etype == "note":
                    m = re.search(r"set status to \*\*(.+?)\*\*", body)
                    if m:
                        dev_plan = m.group(1)

            tech_rows.append((ds, iid, system, func_module, "", dev_plan, dev_user, front_user, backend_user))

    # Test daily report
    test_rows = []
    seen = set()
    for issue in issue_data:
        if "Bug::dev" not in issue.get("labels", []):
            continue
        iid = issue["iid"]
        key = str(iid)
        cdata = notes_cache.get(key, {"notes": [], "label_events": []})
        sys_notes = parse_notes(cdata.get("notes", []))
        label_evts = parse_label_events(cdata.get("label_events", []))
        labels = issue.get("labels", [])
        title = issue.get("title", "")
        created = issue.get("created_at", "")

        system = ""
        func_module = ""
        for lbl in labels:
            if lbl.startswith("BSMS::") and lbl in system_labels:
                system = system_labels[lbl]
                break

        priority = ""
        for lbl in labels:
            if lbl.startswith("Priority::"):
                priority = lbl.replace("Priority::", "")
                break

        reporter = ""
        author = issue.get("author")
        if author:
            reporter = username_to_name.get(author.get("username", ""), author.get("name", ""))

        # Bug reporter from Process::pass events
        for ev in label_evts:
            if ev["label"] == "Process::pass" and ev["action"] == "add":
                ds = date_str(ev["time"])
                if ds:
                    fixer = username_to_name.get(ev["user"], ev["user"])
                    if (ds, iid) not in seen:
                        seen.add((ds, iid))
                        test_rows.append((ds, iid, system, func_module, title, priority, reporter, fixer))

        # Also add creation date rows
        ds = date_str(created)
        if ds and (ds, iid) not in seen and "Process::pass" not in [e["label"] for e in label_evts if e["action"] == "add"]:
            seen.add((ds, iid))
            test_rows.append((ds, iid, system, func_module, title, priority, reporter, ""))

    test_rows.sort(key=lambda x: x[0])

    conn.executemany("""
        INSERT OR REPLACE INTO daily_report_dev (date, iid, system, func_module, detail_module, dev_plan, dev_user, front_user, backend_user)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, tech_rows)

    conn.executemany("""
        INSERT OR REPLACE INTO daily_report_test (date, iid, system, func_module, defect, priority, reporter, fixer)
        VALUES (?,?,?,?,?,?,?,?)
    """, test_rows)

    print(f"  Daily reports: tech={len(tech_rows)}, test={len(test_rows)}")


def build_issues_list(conn, issue_data):
    print("  Building issues list...")
    conn.executemany("""
        INSERT OR REPLACE INTO issues (iid, system, title, state, labels, priority, assignee, author, created_at, updated_at, closed_at, milestone, web_url, data_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        i["iid"],
        next((l for l in i.get("labels", []) if l.startswith("BSMS::")), ""),
        i.get("title", ""),
        i.get("state", ""),
        ",".join(i.get("labels", [])),
        next((l.replace("Priority::", "") for l in i.get("labels", []) if l.startswith("Priority::")), ""),
        (i.get("assignee") or {}).get("name", ""),
        (i.get("author") or {}).get("name", ""),
        i.get("created_at", ""),
        i.get("updated_at", ""),
        i.get("closed_at", ""),
        (i.get("milestone") or {}).get("title", "") if i.get("milestone") else "",
        i.get("web_url", ""),
        json.dumps(i, ensure_ascii=False),
    ) for i in issue_data])


def extract_feature_id(title):
    m = re.search(r'([A-Z]+-[F]\d{3})', title)
    if m:
        return m.group(1)
    return None


def build_sprint_ex(conn, issue_data, notes_cache):
    print("  Building Sprint/EX data...")
    sprint_rows = []
    ex_rows = []
    for issue in issue_data:
        iid = issue["iid"]
        title = issue.get("title", "")
        labels = issue.get("labels", [])
        state = issue.get("state", "")

        feature_id = extract_feature_id(title)
        if not feature_id:
            continue

        sprint_label = ""
        for lbl in labels:
            if lbl.lower().startswith("sprint::"):
                sprint_label = lbl.split("::")[1].lstrip("0")
                break

        stage_status = "已完成" if state == "closed" else ""

        # Check for notes status
        key = str(iid)
        cdata = notes_cache.get(key, {"notes": [], "label_events": []})
        sys_notes = parse_notes(cdata.get("notes", []))
        if state != "closed":
            for note in sys_notes:
                m = re.search(r"set status to \*\*(.+?)\*\*", note["body"])
                if m:
                    stage_status = m.group(1)

        system = ""
        for lbl in labels:
            if lbl.startswith("BSMS::"):
                m = re.search(r"BSMS::(.+)", lbl)
                if m:
                    system = m.group(1)
                break

        sprint_rows.append((feature_id, iid, title, system, sprint_label, stage_status, state))
        ex_rows.append((feature_id, iid, title, system, sprint_label, stage_status, state))

    conn.executemany("""
        INSERT OR REPLACE INTO sprint_data (feature_id, iid, title, system, sprint, stage_status, state)
        VALUES (?,?,?,?,?,?,?)
    """, sprint_rows)
    conn.executemany("""
        INSERT OR REPLACE INTO ex_data (feature_id, iid, title, system, sprint, stage_status, state)
        VALUES (?,?,?,?,?,?,?)
    """, ex_rows)
    print(f"  Sprint: {len(sprint_rows)}, EX: {len(ex_rows)}")


def build_bug_list(conn, issue_data):
    print("  Building bug list...")
    bugs = [i for i in issue_data if "Bug::dev" in i.get("labels", [])]
    bug_rows = []
    for i in bugs:
        labels = i.get("labels", [])
        priority = ""
        for lbl in labels:
            if lbl.startswith("Priority::"):
                priority = lbl.replace("Priority::", "")
                break
        system = ""
        for lbl in labels:
            if lbl.startswith("BSMS::"):
                m = re.search(r"BSMS::(.+)", lbl)
                if m:
                    system = m.group(1)
                break
        bug_rows.append((
            i["iid"], system, i.get("title", ""), priority,
            i.get("state", ""), i.get("created_at", ""),
            i.get("updated_at", ""),
            (i.get("assignee") or {}).get("name", ""),
        ))
    conn.executemany("""
        INSERT OR REPLACE INTO bugs (iid, system, title, priority, state, created_at, updated_at, assignee)
        VALUES (?,?,?,?,?,?,?,?)
    """, bug_rows)
    print(f"  Bugs: {len(bug_rows)}")


def main():
    print("Loading JSON caches...")
    cache_path = os.path.join(CACHE_DIR, "gitlab_issues_cache.json")
    notes_path = os.path.join(CACHE_DIR, "gitlab_notes_cache.json")

    with open(cache_path, "r", encoding="utf-8") as f:
        ic = json.load(f)

    with open(notes_path, "r", encoding="utf-8") as f:
        notes_cache = json.load(f)

    # Get all unique issues
    seen = set()
    all_issues = []
    for issue in ic["functiondev"] + ic["bugdev"]:
        if issue["iid"] not in seen:
            seen.add(issue["iid"])
            all_issues.append(issue)

    print(f"  Issues: {len(all_issues)} (func={len(ic['functiondev'])}, bug={len(ic['bugdev'])})")
    print(f"  Notes entries: {len(notes_cache)}")

    # Setup DB
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")

    # Create tables
    conn.executescript("""
        DROP TABLE IF EXISTS dev_dashboard;
        CREATE TABLE dev_dashboard (
            date TEXT PRIMARY KEY,
            b INTEGER, c INTEGER, d INTEGER, e INTEGER, f INTEGER,
            g INTEGER, h REAL, i INTEGER, j INTEGER, k INTEGER,
            l INTEGER, m INTEGER, n INTEGER, o INTEGER, p INTEGER,
            q INTEGER, r INTEGER, s INTEGER,
            func_all INTEGER, func_dev INTEGER, func_deving INTEGER,
            func_testing INTEGER, func_other INTEGER, func_open_total INTEGER,
            func_pass INTEGER, func_done INTEGER, func_closed_other INTEGER,
            func_closed_total INTEGER
        );

        DROP TABLE IF EXISTS test_dashboard;
        CREATE TABLE test_dashboard (
            date TEXT PRIMARY KEY,
            b INTEGER, c INTEGER, d INTEGER, e INTEGER, f INTEGER,
            g INTEGER, h INTEGER, i INTEGER, j INTEGER, k INTEGER,
            l INTEGER, m INTEGER, n INTEGER, o INTEGER, p INTEGER,
            q INTEGER, r INTEGER, s INTEGER,
            bug_all INTEGER, bug_open_fix INTEGER, bug_open_test INTEGER,
            bug_open_other INTEGER, bug_open_total INTEGER,
            bug_done INTEGER, bug_closed_other INTEGER, bug_closed_total INTEGER
        );

        DROP TABLE IF EXISTS status_dashboard;
        CREATE TABLE status_dashboard (
            date TEXT PRIMARY KEY,
            bug_open_fix INTEGER, bug_open_test INTEGER, bug_open_other INTEGER,
            bug_open_total INTEGER,
            bug_closed_fix INTEGER, bug_closed_test INTEGER, bug_closed_done INTEGER,
            bug_closed_other INTEGER, bug_closed_total INTEGER,
            func_open_dev INTEGER, func_open_deving INTEGER, func_open_testing INTEGER,
            func_open_other INTEGER, func_open_total INTEGER,
            func_closed_done INTEGER, func_closed_other INTEGER, func_closed_total INTEGER,
            func_open_pass INTEGER
        );

        DROP TABLE IF EXISTS daily_report_dev;
        CREATE TABLE daily_report_dev (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, iid INTEGER, system TEXT, func_module TEXT,
            detail_module TEXT, dev_plan TEXT, dev_user TEXT,
            front_user TEXT, backend_user TEXT
        );

        DROP TABLE IF EXISTS daily_report_test;
        CREATE TABLE daily_report_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, iid INTEGER, system TEXT, func_module TEXT,
            defect TEXT, priority TEXT, reporter TEXT, fixer TEXT
        );

        DROP TABLE IF EXISTS issues;
        CREATE TABLE issues (
            iid INTEGER PRIMARY KEY,
            system TEXT, title TEXT, state TEXT, labels TEXT,
            priority TEXT, assignee TEXT, author TEXT,
            created_at TEXT, updated_at TEXT, closed_at TEXT,
            milestone TEXT, web_url TEXT, data_json TEXT
        );

        DROP TABLE IF EXISTS bugs;
        CREATE TABLE bugs (
            iid INTEGER PRIMARY KEY,
            system TEXT, title TEXT, priority TEXT,
            state TEXT, created_at TEXT, updated_at TEXT, assignee TEXT
        );

        DROP TABLE IF EXISTS sprint_data;
        CREATE TABLE sprint_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_id TEXT, iid INTEGER, title TEXT, system TEXT,
            sprint TEXT, stage_status TEXT, state TEXT
        );

        DROP TABLE IF EXISTS ex_data;
        CREATE TABLE ex_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_id TEXT, iid INTEGER, title TEXT, system TEXT,
            sprint TEXT, stage_status TEXT, state TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state);
        CREATE INDEX IF NOT EXISTS idx_issues_labels ON issues(labels);
        CREATE INDEX IF NOT EXISTS idx_bugs_state ON bugs(state);
        CREATE INDEX IF NOT EXISTS idx_daily_report_dev_date ON daily_report_dev(date);
        CREATE INDEX IF NOT EXISTS idx_daily_report_test_date ON daily_report_test(date);
    """)

    build_issues_list(conn, all_issues)
    build_sprint_ex(conn, all_issues, notes_cache)
    build_bug_list(conn, all_issues)
    build_dashboards(conn, all_issues, notes_cache)
    build_daily_reports(conn, all_issues, notes_cache)

    conn.commit()
    conn.close()
    print(f"\nDone! DB saved to: {DB_PATH}")
    print(f"  Issues: {len(all_issues)}, Bugs: {len([i for i in all_issues if 'Bug::dev' in i.get('labels',[])])}")
    print(f"  Sprint: {sum(1 for i in all_issues if re.search(r'[A-Z]+-[F]\\d{3}', i.get('title','')))}")


if __name__ == "__main__":
    main()
