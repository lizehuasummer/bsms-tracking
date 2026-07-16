# BSMS GitLab → Excel 同步说明

## 一、执行要求

每周更新一次，从 GitLab 抓取 Issue 的 activity 记录，回填到 Excel 表格 `【交付HK】BSMS项目整体进度计划 (更新中)20260702备份.xlsx`。

### 1. GitLab 配置
- **实例**: `https://gitlab.stpass.com`（内网，自签名 SSL，需 `verify=False`）
- **项目**: `aladdinx/document/dev-design`（project ID = 4）
- **Token**: 存放在 `server/.env` 文件中，有效至 2026-12-31
- **API 速率**: 每个 issue 需请求 2 个 API（notes + label_events），建议 10 并发，0.1s 间隔

### 2. 数据来源
| Label | 用途 | 当前总数 | 校验数 |
|---|---|---|---|
| `Function::dev` | 功能点开发进度 | 1515 | Excel 已知含已完成总数 1115 |
| `Bug::dev` | Bug 修复进度 | 2258 | Excel 已知含已完成总数 2257 |

### 3. Excel 三个 Sheet 的填写规则

#### Sheet 1: `Sprint详细安排`（1166行，数据从第5行开始）
匹配方式：E列功能点编号 → GitLab issue title 中的 `XXX-FNNN`，如有多个再按 F列名称匹配。

| 列 | 内容 | 数据来源 |
|---|---|---|
| I | 最新状态（待开发/开发中/测试中/processpass/已完成） | system note `set status to **XXX**` 的最后一条；若状态=测试中 且当前 labels 含 `Process::pass`，则改为 processpass |
| L | 测试中操作人 | system note `set status to **测试中**` 最后一条的 author |
| M | 测试中时间 | 同上的 created_at（格式 YYYY-MM-DD HH:MM） |
| N | Process::pass 操作人 | label_event `Process::pass` + action=add 最后一条的 user |
| O | Process::pass 时间 | 同上的 created_at |
| R | 已完成操作人 | system note `set status to **已完成**` 最后一条的 author |
| S | 已完成时间 | 同上的 created_at |

#### Sheet 2: `EX开发功能点`（389行，数据从第5行开始）
匹配方式同上。

| 列 | 内容 |
|---|---|
| L/M | 测试中操作人/时间 |
| N/O | Process::pass 操作人/时间 |
| R/S | 已完成操作人/时间 |

（不填 I 列状态）

#### Sheet 3: `bug`（动态行数，数据从第2行开始，先清空再填入）
无需匹配，将 GitLab 中所有 `Bug::dev` 的 issue 全部写入。

| 列 | 内容 | 数据来源 |
|---|---|---|
| A | 子系统名 | label `BSMS::XXX` → XXX（如 DMM, DOP 等） |
| B | issue 编号 | `#iid`（如 #3070） |
| C | issue 标题 | issue.title |
| D | 优先级 | label `Priority::P0/P1/P2/P3` → P0/P1/P2/P3 |
| E | 最新状态 | system note 最后一条 `set status to **XXX**`；无则用 issue.state |
| F | 创建人 | issue.author.username |
| G | 创建时间 | issue.created_at（YYYY-MM-DD HH:MM） |
| H | 待修复操作人 | system note `set status to **待修复**` 最后一条的 author |
| I | 待修复时间 | 同上的 created_at |
| J | 测试中操作人 | system note `set status to **测试中**` 最后一条的 author |
| K | 测试中时间 | 同上的 created_at |
| L | 已完成操作人 | system note `set status to **已完成**` 最后一条的 author |
| M | 已完成时间 | 同上的 created_at |

---

## 二、GitLab 数据结构

### 1. Issue 对象（`/api/v4/projects/4/issues?labels=Function::dev&state=all`）
```json
{
  "iid": 4265,
  "title": "DOP-F029-1-取消預約變更為查詢預約記錄",
  "state": "closed",          // opened / closed
  "labels": [
    "BSMS::DOP",
    "Function::dev",
    "sprint::7"
  ],
  "author": { "username": "chenny", "name": "陈..." },
  "created_at": "2026-06-23T10:32:46.097Z",
  "closed_at": "2026-07-01T09:05:20.276Z"
}
```

### 2. System Notes（`/api/v4/projects/4/issues/{iid}/notes?per_page=100&sort=asc&order_by=created_at`）
状态变更记录在 system notes 中，`body` 格式为 `set status to **XXX**`。

```json
[
  {
    "system": true,
    "body": "set status to **待开发**",
    "created_at": "2026-06-23T10:32:45.474Z",
    "author": { "username": "chenny" }
  },
  {
    "system": true,
    "body": "set status to **开发中**",
    "created_at": "2026-06-25T07:46:29.212Z",
    "author": { "username": "liuhaolong" }
  },
  {
    "system": true,
    "body": "set status to **测试中**",
    "created_at": "2026-06-26T08:48:02.742Z",
    "author": { "username": "liuhaolong" }
  },
  {
    "system": true,
    "body": "set status to **已完成**",
    "created_at": "2026-07-01T09:05:20.247Z",
    "author": { "username": "liangyaoxian" }
  }
]
```

**已知状态值**: 待开发、开发中、测试中、已完成、待修复、不需要修复、已关闭、Duplicate、已处理

### 3. Label Events（`/api/v4/projects/4/issues/{iid}/resource_label_events`）
Process::pass 标签的添加记录。

```json
[
  {
    "action": "add",
    "label": { "name": "BSMS::DOP" },
    "created_at": "2026-06-18T09:44:45.247Z",
    "user": { "username": "chenny" }
  },
  {
    "action": "add",
    "label": { "name": "Process::pass" },
    "created_at": "2026-07-02T07:01:43.850Z",
    "user": { "username": "liangyaoxian" }
  }
]
```

### 4. 已知 Label 分类
| Label 前缀 | 含义 | 示例 |
|---|---|---|
| `BSMS::` | 子系统 | `BSMS::DMM`, `BSMS::DOP`, `BSMS::STM` 等 |
| `Function::dev` | 功能点开发 | 固定 label |
| `Bug::dev` | Bug 修复 | 固定 label |
| `Change::dev` | 变更开发 | 固定 label |
| `Story::dev` | Story 开发 | 固定 label |
| `Priority::` | 优先级 | `Priority::P0`, `Priority::P1`, `Priority::P2` |
| `Process::pass` | 测试通过 | 固定 label |
| `Sprint::` / `sprint::` | Sprint 分配 | `Sprint::01`, `sprint::7`, `sprint::8` |
| `Port::` | 端口 | `Port::frontend`, `Port::backend` |
| `backend::finished` | 后端完成 | 固定 label |
| `front::finished` | 前端完成 | 固定 label |
| `start::dev` | 开发已启动 | 固定 label |

### 5. 功能点编号匹配
Issue title 中包含功能点编号，格式如：
- `DMM-F001:用户管理搜索 Search Donor`
- `DOP-F029-1-取消預約變更為查詢預約記錄`
- `D3M-F324【新增】新稀有血型通知记录`

正则匹配：`([A-Z]{2,5}-F\d{1,4})`

---

## 三、执行流程

### 快速执行（每周更新）
```powershell
# 1. 确保 server 已启动（用于 GitLab SSL bypass）
# 2. 运行同步脚本
cd D:\Users\LZH\Documents\opencode\bsms_tracking\scripts
python sync_gitlab_to_excel.py
```

脚本执行步骤：
1. 检查缓存（issues 缓存 1 小时内有效，notes 缓存永久）
2. 抓取 `Function::dev` 和 `Bug::dev` 的所有 issue（约 3773 条）
3. 对每个 issue 抓取 system notes 和 label events（约 7546 个 API 请求，10 并发约 8 分钟）
4. 匹配 Excel 并填写三个 Sheet
5. 保存 Excel

### 缓存文件
| 文件 | 内容 | 位置 |
|---|---|---|
| `gitlab_issues_cache.json` | 所有 issue 数据 | `C:\Users\EDY\AppData\Local\Temp\opencode\` |
| `gitlab_notes_cache.json` | 所有 issue 的 notes + label_events | 同上 |

更新数据时删除缓存文件即可强制重新抓取。

### Token 更新
Token 存放在 `server/.env` 文件中：
```
GITLAB_TOKEN=glpat-XXXXXXXX
```
当前 Token 有效至 2026-12-31。过期后需在 GitLab → User Settings → Personal Access Tokens 重新生成，需勾选 `api` scope。

---

## 四、上次执行结果（2026-07-02）

- Function::dev: 1515 条 issue，997 个唯一功能点编号
- Sprint详细安排: 782 行匹配
- EX开发功能点: 186 行匹配
- Bug::dev: 2258 条全部填入 bug sheet
- Bug 状态分布: 已完成 1827, 待修复 154, 测试中 84, 不需要修复 112
