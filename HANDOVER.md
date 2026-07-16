# BSMS 项目跟踪系统 — 项目交接文档

## 1. 项目概述

从 GitLab 拉取 BSMS 项目数据，自动填充 Excel 跟踪表，并提供网页看板供团队查看。

**核心数据流**：
```
GitLab API → JSON 缓存 (Temp) → Excel (_.xlsx)
                               → SQLite (bsms.db) → FastAPI Web 看板
```

## 2. 目录结构

```
bsms_tracking/
├── 【交付HK】BSMS项目整体进度计划 (更新中)20260702备份_new.xlsx  ← Excel 输出
├── start_web.bat                    ← 一键启动 Web 服务
│
├── scripts/
│   ├── update_4sheets.py            ← ★ 主脚本：抓取 + 填 Excel
│   ├── export_to_sqlite.py          ← JSON 缓存 → SQLite（Web 用）
│   ├── generate_dashboards_v2.py    ← 开发/测试汇总看板（3 个 Dashboard）
│   ├── generate_status_dashboard.py ← 每日状态变化看板
│   ├── generate_daily_reports.py    ← 技术/测试工作日报
│   ├── gitlab_users.py              ← 用户映射（用户名→中文名）
│   ├── add_dashboard_doc.py         ← 看板说明文档
│   └── add_issue_update_doc.py      ← Issue 更新说明文档
│
├── web/
│   ├── main.py                      ← FastAPI 应用（11 页面 + 10 API）
│   ├── bsms.db                      ← SQLite 数据库
│   ├── requirements.txt             ← Python 依赖
│   └── templates/
│       ├── base.html                ← 侧边栏导航 + Bootstrap 5
│       ├── index.html               ← 首页概览
│       ├── issues.html              ← Issue 列表
│       ├── bugs.html                ← Bug 列表
│       ├── sprint.html              ← Sprint 安排
│       ├── ex.html                  ← EX 功能点
│       ├── dashboard_dev.html       ← 开发汇总看板（Chart.js）
│       ├── dashboard_test.html      ← 测试汇总看板
│       ├── dashboard_status.html    ← 状态变化看板
│       ├── daily_report_dev.html    ← 技术工作日报
│       └── daily_report_test.html   ← 测试工作日报
```

## 3. 环境准备

### 3.1 Python 3.12+

```bash
pip install fastapi uvicorn jinja2 requests openpyxl
# 或: pip install -r web/requirements.txt
```

### 3.2 依赖清单

| 包 | 用途 |
|---|---|
| `requests` | 调用 GitLab API |
| `openpyxl` | 读写 Excel |
| `fastapi` + `uvicorn` | Web 服务 |
| `jinja2` | HTML 模板引擎 |

### 3.3 VPN 要求

访问 `gitlab.stpass.com` 需要公司 VPN（深信 EasyConnect）。

## 4. 配置

所有配置集中在 `scripts/update_4sheets.py` 顶部：

```python
GITLAB_URL = "https://gitlab.stpass.com"
GITLAB_TOKEN = "glpat-rO7mGLMblvELQu1iJbGMY286MQp1OnEH.01.0w0x3iets"
PROJECT_ID = 4
EXCEL_PATH = r"D:\...\【交付HK】BSMS项目整体进度计划 (更新中)20260702备份_new.xlsx"
CACHE_DIR = r"C:\Users\EDY\AppData\Local\Temp\opencode"
```

**跨电脑迁移须知**：
- `EXCEL_PATH` 需要改为新电脑的绝对路径
- `CACHE_DIR` 建议保持 `Temp/opencode`
- GitLab Token 有效期至 2027-01-01，过期需重新生成

## 5. 核心脚本说明

### 5.1 update_4sheets.py（最重要）

负责抓取数据 + 填充 Excel。三种运行模式：

```bash
python scripts/update_4sheets.py              # 用缓存填表（跳过抓取）
python scripts/update_4sheets.py --fresh      # 删除缓存，重新抓取全部（耗时 10min+）
python scripts/update_4sheets.py --excel-only # 仅用已有缓存填表
```

内部流程：
1. `step1_fetch_all_issues()` — 抓取 3 组数据：all / Function::dev / Bug::dev
2. `step2_fetch_notes()` — 并行抓取每个 issue 的 notes + label_events
3. `step3_fill_excel()` — 填充 6 个 Sheet：
   - issue（4522→4538 行）
   - Sprint详细安排（1126 行）
   - EX开发功能点（335 行）
   - bug（2380→2396 行）
   - 技术工作日报（4098→4100 行）
   - 测试工作日报（2940→2957 行）

### 5.2 export_to_sqlite.py

将 JSON 缓存写入 SQLite，供 Web 看板使用：

```bash
python scripts/export_to_sqlite.py   # 约 60 秒
```

生成 8 张表：`issues`, `bugs`, `sprint_data`, `ex_data`, `dev_dashboard`, `test_dashboard`, `status_dashboard`, `daily_report_dev`, `daily_report_test`

### 5.3 生成 Dashboard

```bash
python scripts/generate_dashboards_v2.py      # 开发/测试汇总看板
python scripts/generate_status_dashboard.py   # 每日状态变化
```

这些脚本读取 JSON 缓存 → 计算每日统计 → 写入 Excel 的对应 Sheet。

## 6. 当前数据状态

| 指标 | 数值 |
|---|---|
| 最后更新 | 2026-07-13 18:11 |
| 总 issues | 4538 |
| Function::dev | 1526 |
| Bug::dev | 2396（closed=2314, opened=82）|
| Notes 条目 | 4538 |
| 看板天数 | 181 天（2026-01-14 ~ 2026-07-13）|
| Excel Sheet 数 | 16 个 |

## 7. Web 看板

### 7.1 启动

```bash
# 方式 1：直接启动
python web/main.py

# 方式 2：一键脚本
start_web.bat
```

### 7.2 访问地址

| 地址 | 说明 |
|---|---|
| http://localhost:8000 | 本机 |
| http://192.168.210.101:8000 | 内网其他设备 |

### 7.3 页面清单

| 路由 | 内容 |
|---|---|
| `/` | 首页概览（统计 + 趋势图） |
| `/issues` | Issue 列表（搜索/筛选/分页） |
| `/bugs` | Bug 列表 |
| `/sprint` | Sprint 详细安排 |
| `/ex` | EX 开发功能点 |
| `/dashboard/dev` | 开发每日汇总看板（4 个图） |
| `/dashboard/test` | 测试每日汇总看板 |
| `/dashboard/status` | 每日状态变化 |
| `/daily-report/dev` | 技术工作日报（按日期查询） |
| `/daily-report/test` | 测试工作日报（按日期查询） |

### 7.4 JSON API

| API | 说明 |
|---|---|
| `/api/stats` | 首页统计 |
| `/api/issues` | Issue 列表（支持 `?state=&system=&search=&page=`） |
| `/api/bugs` | Bug 列表（支持 `?state=`） |
| `/api/sprint` | Sprint 数据 |
| `/api/ex` | EX 数据 |
| `/api/dashboard/dev?days=30` | 开发看板 |
| `/api/dashboard/test?days=30` | 测试看板 |
| `/api/dashboard/status?days=30` | 状态变化 |
| `/api/dashboard/dates` | 所有日期列表 |
| `/api/systems` | 系统列表 |
| `/api/refresh-meta` | 数据元信息 |

### 7.5 注册 Windows 服务（开机自启）

```bash
nssm install BSMSWeb "C:\Python312\python.exe" "D:\...\bsms_tracking\web\main.py"
nssm start BSMSWeb
```

## 8. 日常操作流程

### 8.1 每日更新数据

```bash
# 标准流程（推荐）— 只拉变化数据：
python scripts/update_4sheets.py --fresh   # 12-15 分钟
python scripts/export_to_sqlite.py         # 1 分钟
# 重启 Web 服务即可
```

### 8.2 全量刷新（新电脑首次）

```bash
# Step 1: 清除旧缓存
Remove-Item "$env:TEMP\opencode\gitlab_*.json" -Force

# Step 2: 修改 update_4sheets.py 中的 EXCEL_PATH 为新路径

# Step 3: 抓取数据（耗时较长）
python scripts/update_4sheets.py --fresh

# Step 4: 导出 SQLite
python scripts/export_to_sqlite.py

# Step 5: 启动 Web
python web/main.py
```

### 8.3 只更新 Web 看板（不改 Excel）

```bash
python scripts/export_to_sqlite.py
# 重启 Web 服务
```

## 9. GitLab 用户映射

`scripts/gitlab_users.py` 定义了用户分组：

```python
GITLAB_USERS = [
    # (组名, 系统名, 中文名, GitLab 用户名, label)
    ("系统开发组（前端）", "BCM", "张三", "zhangsan", "BSMS::BCM"),
    ("系统开发组（后端）", "BCM", "李四", "lisi", "BSMS::BCM"),
    ...
]
```

新增用户时需同步更新此文件和 `label` Sheet。

## 10. 已知问题

### 10.1 GitLab Token 过期
- Token 格式：`glpat-...`（Personal Access Token）
- 过期后需在 GitLab → Settings → Access Tokens 重新生成
- 权限需求：`read_api`

### 10.2 VPN 断开
- 脚本会因连接超时报错
- 重新连接 VPN 后重试即可

### 10.3 Notes 抓取慢
- 4500+ issue 并行抓取约需 8-10 分钟
- 脚本有 checkpoint 机制，中断后重跑会续传

### 10.4 文件路径含中文
- Excel 文件名含中文，PowerShell 中可能需要 `-Encoding UTF8`
- Python 3.12 下无问题

## 11. 常见修复

### Bug 关闭数不匹配 GitLab

```bash
# 只同步 Bug::dev 状态，比全量刷新快 10 倍
python C:\Users\EDY\AppData\Local\Temp\opencode\sync_bugs.py
python scripts/export_to_sqlite.py
python scripts/update_4sheets.py --excel-only
```

### Notes 缓存不完整

```bash
python C:\Users\EDY\AppData\Local\Temp\opencode\refetch_notes.py
python scripts/export_to_sqlite.py
```

## 12. 迁移到新电脑清单

- [ ] 安装 Python 3.12+
- [ ] 安装依赖：`pip install fastapi uvicorn jinja2 requests openpyxl`
- [ ] 连接公司 VPN
- [ ] 验证 GitLab 访问：`curl https://gitlab.stpass.com`
- [ ] 复制整个 `bsms_tracking/` 目录
- [ ] 修改 `scripts/update_4sheets.py` 中的 `EXCEL_PATH`
- [ ] 运行 `python scripts/update_4sheets.py --fresh`
- [ ] 运行 `python scripts/export_to_sqlite.py`
- [ ] 启动 Web：`python web/main.py`
- [ ] 验证：`http://localhost:8000`
