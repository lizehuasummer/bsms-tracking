# BSMS Tracking - 项目管理工具

管理 GitLab 上的功能点开发进度

## 技术栈

- **前端**: React 18 + TypeScript + Ant Design + Vite
- **后端**: Node.js + Express + TypeScript
- **数据库**: SQLite (better-sqlite3)
- **GitLab API**: 集成 GitLab REST API

## 核心功能

- GitLab 项目同步
- 功能点管理（关联 GitLab Issue/MR）
- 进度看板（Kanban）
- 甘特图
- 团队成员管理
- 通知提醒

## 快速开始

```bash
# 安装所有依赖
npm run install:all

# 启动开发环境（前后端同时启动）
npm run dev

# 仅启动后端 (http://localhost:3001)
npm run dev:server

# 仅启动前端 (http://localhost:5173)
npm run dev:client
```

## 项目结构

```
bsms_tracking/
├── server/          # 后端服务
│   ├── src/
│   │   ├── config/      # 配置
│   │   ├── database/    # 数据库
│   │   ├── routes/      # API 路由
│   │   ├── services/    # 业务逻辑
│   │   └── index.ts     # 入口
│   └── package.json
├── client/          # 前端应用
│   ├── src/
│   │   ├── components/  # 通用组件
│   │   ├── pages/       # 页面
│   │   ├── services/    # API 调用
│   │   ├── stores/      # 状态管理
│   │   ├── types/       # 类型定义
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
└── package.json     # 根配置
```
