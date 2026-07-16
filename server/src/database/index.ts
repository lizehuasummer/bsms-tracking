import initSqlJs, { Database as SqlJsDatabase } from 'sql.js';
import path from 'path';
import fs from 'fs';
import { config } from '../config';

let db: SqlJsDatabase;
let dbPath: string;
let saveTimer: ReturnType<typeof setTimeout> | null = null;

export async function initDatabase(): Promise<SqlJsDatabase> {
  if (db) return db;

  dbPath = path.resolve(config.db.path);
  const dir = path.dirname(dbPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const SQL = await initSqlJs();

  if (fs.existsSync(dbPath)) {
    const buffer = fs.readFileSync(dbPath);
    db = new SQL.Database(buffer);
  } else {
    db = new SQL.Database();
  }

  db.run('PRAGMA foreign_keys = ON');
  migrate(db);
  return db;
}

export function getDatabase(): SqlJsDatabase {
  if (!db) throw new Error('Database not initialized. Call initDatabase() first.');
  return db;
}

function migrate(db: SqlJsDatabase): void {
  db.run(`
    CREATE TABLE IF NOT EXISTS subsystems (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      color TEXT DEFAULT '#1677ff',
      sort_order INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS features (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      feature_id TEXT UNIQUE NOT NULL,
      subsystem TEXT,
      workbench TEXT,
      story_code TEXT,
      menu TEXT,
      feature_name TEXT NOT NULL,
      milestone TEXT,
      sprint TEXT,
      gitlab_iid INTEGER,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS feature_stages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      feature_pk INTEGER NOT NULL,
      stage INTEGER NOT NULL CHECK(stage BETWEEN 1 AND 5),
      plan_end TEXT,
      actual_end TEXT,
      status TEXT DEFAULT 'not_started' CHECK(status IN ('not_started','in_progress','completed','delayed')),
      FOREIGN KEY (feature_pk) REFERENCES features(id) ON DELETE CASCADE,
      UNIQUE(feature_pk, stage)
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS status_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      feature_pk INTEGER NOT NULL,
      stage INTEGER,
      field_name TEXT NOT NULL,
      old_value TEXT,
      new_value TEXT,
      changed_at TEXT DEFAULT (datetime('now')),
      changed_by TEXT,
      note TEXT,
      FOREIGN KEY (feature_pk) REFERENCES features(id) ON DELETE CASCADE
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS gitlab_issues (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      gitlab_iid INTEGER UNIQUE NOT NULL,
      title TEXT,
      state TEXT,
      labels TEXT,
      feature_pk INTEGER,
      assignees TEXT,
      created_at_gitlab TEXT,
      updated_at_gitlab TEXT,
      closed_at TEXT,
      web_url TEXT,
      synced_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (feature_pk) REFERENCES features(id) ON DELETE SET NULL
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS sync_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      type TEXT NOT NULL,
      total_synced INTEGER DEFAULT 0,
      duration_ms INTEGER DEFAULT 0,
      detail TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
  `);

  db.run('CREATE INDEX IF NOT EXISTS idx_features_subsystem ON features(subsystem)');
  db.run('CREATE INDEX IF NOT EXISTS idx_features_sprint ON features(sprint)');
  db.run('CREATE INDEX IF NOT EXISTS idx_features_feature_id ON features(feature_id)');
  db.run('CREATE INDEX IF NOT EXISTS idx_stages_feature ON feature_stages(feature_pk)');
  db.run('CREATE INDEX IF NOT EXISTS idx_stages_status ON feature_stages(status)');
  db.run('CREATE INDEX IF NOT EXISTS idx_history_feature ON status_history(feature_pk)');
  db.run('CREATE INDEX IF NOT EXISTS idx_gitlab_iid ON gitlab_issues(gitlab_iid)');
  db.run('CREATE INDEX IF NOT EXISTS idx_gitlab_feature ON gitlab_issues(feature_pk)');

  seedSubsystems(db);
  saveDatabase();
}

function seedSubsystems(db: SqlJsDatabase): void {
  const subsystems = [
    { key: 'BCM', name: 'BCM 血站管理', color: '#1677ff', sort: 1 },
    { key: 'DMM', name: 'DMM 献血者管理', color: '#52c41a', sort: 2 },
    { key: 'DOP', name: 'DOP 献血者在线门户', color: '#722ed1', sort: 3 },
    { key: 'D3M', name: 'D3M 数据管理', color: '#fa8c16', sort: 4 },
    { key: 'QSM', name: 'QSM 质量安全', color: '#eb2f96', sort: 5 },
    { key: 'STM', name: 'STM 样本检测', color: '#13c2c2', sort: 6 },
    { key: 'IDM', name: 'IDM 库存分发', color: '#faad14', sort: 7 },
    { key: 'QMS', name: 'QMS 质量管理', color: '#f5222d', sort: 8 },
    { key: 'BSC', name: 'BSC 血站采集', color: '#2f54eb', sort: 9 },
    { key: 'CYLIMS', name: 'CYLIMS 实验室信息', color: '#595959', sort: 10 },
  ];
  for (const s of subsystems) {
    db.run(
      'INSERT OR IGNORE INTO subsystems (key, name, color, sort_order) VALUES (?, ?, ?, ?)',
      [s.key, s.name, s.color, s.sort]
    );
  }
}

export function saveDatabase(): void {
  if (!db) return;
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      const data = db.export();
      const buffer = Buffer.from(data);
      fs.writeFileSync(dbPath, buffer);
    } catch (err) {
      console.error('Failed to save database:', err);
    }
  }, 300);
}

export function closeDatabase(): void {
  if (db) {
    if (saveTimer) clearTimeout(saveTimer);
    try {
      const data = db.export();
      const buffer = Buffer.from(data);
      fs.writeFileSync(dbPath, buffer);
    } catch (err) {
      console.error('Failed to save database on close:', err);
    }
    db.close();
  }
}
