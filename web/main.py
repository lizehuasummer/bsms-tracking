"""
BSMS 项目跟踪看板 — FastAPI 网页应用
"""
import json, os, datetime
from pathlib import Path
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3

BASE = Path(__file__).parent
DB_PATH = BASE / "bsms.db"
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="BSMS 项目跟踪看板")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def dicts_from_rows(rows):
    return [dict(r) for r in rows]


# ===== API routes =====

@app.get("/api/stats")
def api_stats():
    """Overview stats for the homepage"""
    conn = get_db()
    issues = conn.execute("SELECT state FROM issues").fetchall()
    bugs = conn.execute("SELECT state FROM bugs").fetchall()
    total = len(issues)
    closed = sum(1 for i in issues if i["state"] == "closed")
    bug_total = len(bugs)
    bug_closed = sum(1 for b in bugs if b["state"] == "closed")

    latest_dev = conn.execute("SELECT * FROM dev_dashboard ORDER BY date DESC LIMIT 1").fetchone()
    latest_test = conn.execute("SELECT * FROM test_dashboard ORDER BY date DESC LIMIT 1").fetchone()

    conn.close()
    return {
        "total_issues": total,
        "closed_issues": closed,
        "open_issues": total - closed,
        "total_bugs": bug_total,
        "closed_bugs": bug_closed,
        "open_bugs": bug_total - bug_closed,
        "latest_dev": dict(latest_dev) if latest_dev else None,
        "latest_test": dict(latest_test) if latest_test else None,
    }


@app.get("/api/issues")
def api_issues(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    state: str = None,
    system: str = None,
    search: str = None,
):
    conn = get_db()
    where = []
    params = []
    if state:
        where.append("state = ?")
        params.append(state)
    if system:
        where.append("system = ?")
        params.append(system)
    if search:
        where.append("(title LIKE ? OR iid = ?)")
        params.extend([f"%{search}%", search])
    where_sql = " AND ".join(where) if where else "1=1"

    total = conn.execute(f"SELECT COUNT(*) FROM issues WHERE {where_sql}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT iid, system, title, state, priority, assignee, created_at, web_url FROM issues WHERE {where_sql} ORDER BY iid DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    conn.close()
    return {"total": total, "page": page, "per_page": per_page, "items": dicts_from_rows(rows)}


@app.get("/api/issues/{iid}")
def api_issue_detail(iid: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM issues WHERE iid = ?", (iid,)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "not found"}, status_code=404)
    return dict(row)


@app.get("/api/bugs")
def api_bugs(state: str = None):
    conn = get_db()
    if state:
        rows = conn.execute("SELECT * FROM bugs WHERE state = ? ORDER BY iid", (state,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM bugs ORDER BY iid").fetchall()
    conn.close()
    return {"total": len(rows), "items": dicts_from_rows(rows)}


@app.get("/api/sprint")
def api_sprint():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sprint_data ORDER BY feature_id").fetchall()
    conn.close()
    return {"total": len(rows), "items": dicts_from_rows(rows)}


@app.get("/api/ex")
def api_ex():
    conn = get_db()
    rows = conn.execute("SELECT * FROM ex_data ORDER BY feature_id").fetchall()
    conn.close()
    return {"total": len(rows), "items": dicts_from_rows(rows)}


@app.get("/api/dashboard/dev")
def api_dashboard_dev(days: int = Query(30, ge=1, le=365)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM dev_dashboard ORDER BY date DESC LIMIT ?", (days,)).fetchall()
    conn.close()
    return {"days": len(rows), "items": dicts_from_rows(rows)}


@app.get("/api/dashboard/test")
def api_dashboard_test(days: int = Query(30, ge=1, le=365)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM test_dashboard ORDER BY date DESC LIMIT ?", (days,)).fetchall()
    conn.close()
    return {"days": len(rows), "items": dicts_from_rows(rows)}


@app.get("/api/dashboard/status")
def api_dashboard_status(days: int = Query(30, ge=1, le=365)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM status_dashboard ORDER BY date DESC LIMIT ?", (days,)).fetchall()
    conn.close()
    return {"days": len(rows), "items": dicts_from_rows(rows)}


@app.get("/api/daily-report/dev")
def api_daily_report_dev(date: str = None, page: int = Query(1, ge=1), per_page: int = Query(100, ge=10, le=500)):
    conn = get_db()
    if date:
        total = conn.execute("SELECT COUNT(*) FROM daily_report_dev WHERE date = ?", (date,)).fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute("SELECT * FROM daily_report_dev WHERE date = ? ORDER BY iid LIMIT ? OFFSET ?", (date, per_page, offset)).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) FROM daily_report_dev").fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute("SELECT * FROM daily_report_dev ORDER BY date DESC, iid LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    conn.close()
    return {"total": total, "page": page, "per_page": per_page, "items": dicts_from_rows(rows)}


@app.get("/api/daily-report/test")
def api_daily_report_test(date: str = None, page: int = Query(1, ge=1), per_page: int = Query(100, ge=10, le=500)):
    conn = get_db()
    if date:
        total = conn.execute("SELECT COUNT(*) FROM daily_report_test WHERE date = ?", (date,)).fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute("SELECT * FROM daily_report_test WHERE date = ? ORDER BY iid LIMIT ? OFFSET ?", (date, per_page, offset)).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) FROM daily_report_test").fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute("SELECT * FROM daily_report_test ORDER BY date DESC, iid LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    conn.close()
    return {"total": total, "page": page, "per_page": per_page, "items": dicts_from_rows(rows)}


@app.get("/api/dashboard/dates")
def api_dashboard_dates():
    conn = get_db()
    rows = conn.execute("SELECT date FROM dev_dashboard ORDER BY date").fetchall()
    conn.close()
    return {"dates": [r["date"] for r in rows]}


@app.get("/api/systems")
def api_systems():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT system FROM issues WHERE system != '' ORDER BY system").fetchall()
    conn.close()
    return {"systems": [r["system"] for r in rows]}


@app.get("/api/refresh-meta")
def api_refresh_meta():
    """Return metadata about the current data"""
    conn = get_db()
    d = conn.execute("SELECT COUNT(*) as c FROM issues").fetchone()[0]
    b = conn.execute("SELECT COUNT(*) as c FROM bugs").fetchone()[0]
    sd = conn.execute("SELECT MIN(date) as mn, MAX(date) as mx FROM dev_dashboard").fetchone()
    last_update = datetime.datetime.fromtimestamp(os.path.getmtime(DB_PATH)).strftime("%Y-%m-%d %H:%M:%S")
    conn.close()
    return {
        "total_issues": d,
        "total_bugs": b,
        "date_range": f"{sd['mn']} ~ {sd['mx']}",
        "db_updated": last_update,
    }


# ===== Page routes =====

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/issues", response_class=HTMLResponse)
def issues_page(request: Request):
    return templates.TemplateResponse(request, "issues.html")


@app.get("/bugs", response_class=HTMLResponse)
def bugs_page(request: Request):
    return templates.TemplateResponse(request, "bugs.html")


@app.get("/sprint", response_class=HTMLResponse)
def sprint_page(request: Request):
    return templates.TemplateResponse(request, "sprint.html")


@app.get("/ex", response_class=HTMLResponse)
def ex_page(request: Request):
    return templates.TemplateResponse(request, "ex.html")


@app.get("/dashboard/dev", response_class=HTMLResponse)
def dev_dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard_dev.html")


@app.get("/dashboard/test", response_class=HTMLResponse)
def test_dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard_test.html")


@app.get("/dashboard/status", response_class=HTMLResponse)
def status_dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard_status.html")


@app.get("/daily-report/dev", response_class=HTMLResponse)
def daily_report_dev_page(request: Request):
    return templates.TemplateResponse(request, "daily_report_dev.html")


@app.get("/daily-report/test", response_class=HTMLResponse)
def daily_report_test_page(request: Request):
    return templates.TemplateResponse(request, "daily_report_test.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
