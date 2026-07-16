import { getDatabase, saveDatabase } from '../database';
import type { Feature, FeatureStage, StatusHistory, GitlabIssue, SubsystemSummary, GanttRow } from '../types';

type Params = (string | number | null)[];

function queryAll<T>(sql: string, params: Params = []): T[] {
  const db = getDatabase();
  const stmt = db.prepare(sql);
  stmt.bind(params);
  const results: T[] = [];
  while (stmt.step()) results.push(stmt.getAsObject() as T);
  stmt.free();
  return results;
}

function queryOne<T>(sql: string, params: Params = []): T | undefined {
  const db = getDatabase();
  const stmt = db.prepare(sql);
  stmt.bind(params);
  let result: T | undefined;
  if (stmt.step()) result = stmt.getAsObject() as T;
  stmt.free();
  return result;
}

function run(sql: string, params: Params = []): void {
  const db = getDatabase();
  db.run(sql, params);
  saveDatabase();
}

function n(v: string | null | undefined): string | null {
  return v ?? null;
}

export const featureService = {
  getAll(params?: { subsystem?: string; sprint?: string; stage_status?: string }): Feature[] {
    let sql = 'SELECT f.* FROM features f';
    const conditions: string[] = [];
    const p: Params = [];
    if (params?.subsystem) { conditions.push('f.subsystem = ?'); p.push(params.subsystem); }
    if (params?.sprint) { conditions.push('f.sprint = ?'); p.push(params.sprint); }
    if (conditions.length) sql += ' WHERE ' + conditions.join(' AND ');
    sql += ' ORDER BY f.subsystem, f.sprint, f.feature_id';

    const features = queryAll<Feature>(sql, p);
    for (const f of features) {
      f.stages = queryAll<FeatureStage>('SELECT * FROM feature_stages WHERE feature_pk = ? ORDER BY stage', [f.id]);
    }
    return features;
  },

  getById(id: number): Feature | undefined {
    const f = queryOne<Feature>('SELECT * FROM features WHERE id = ?', [id]);
    if (f) f.stages = queryAll<FeatureStage>('SELECT * FROM feature_stages WHERE feature_pk = ? ORDER BY stage', [id]);
    return f;
  },

  getByFeatureId(featureId: string): Feature | undefined {
    const f = queryOne<Feature>('SELECT * FROM features WHERE feature_id = ?', [featureId]);
    if (f) f.stages = queryAll<FeatureStage>('SELECT * FROM feature_stages WHERE feature_pk = ? ORDER BY stage', [f.id]);
    return f;
  },

  upsertFromExcel(row: {
    subsystem?: string; workbench?: string; story_code?: string; menu?: string;
    feature_id: string; feature_name: string; milestone?: string; sprint?: string;
    stages: { stage: number; plan_end?: string; actual_end?: string }[];
  }): Feature {
    const existing = queryOne<Feature>('SELECT * FROM features WHERE feature_id = ?', [row.feature_id]);

    if (existing) {
      run(`UPDATE features SET subsystem=?, workbench=?, story_code=?, menu=?, feature_name=?,
        milestone=?, sprint=?, updated_at=datetime('now') WHERE id=?`,
        [n(row.subsystem) ?? existing.subsystem ?? null, n(row.workbench), n(row.story_code), n(row.menu),
         n(row.feature_name), n(row.milestone), n(row.sprint), existing.id]);

      for (const s of row.stages) {
        if (s.plan_end || s.actual_end) {
          const existingStage = queryOne<FeatureStage>(
            'SELECT * FROM feature_stages WHERE feature_pk=? AND stage=?', [existing.id, s.stage]);
          if (existingStage) {
            run('UPDATE feature_stages SET plan_end=?, actual_end=?, status=? WHERE id=?',
              [n(s.plan_end), n(s.actual_end) ?? existingStage.actual_end ?? null,
               computeStatus(s.plan_end, s.actual_end), existingStage.id]);
          } else {
            run('INSERT INTO feature_stages (feature_pk, stage, plan_end, actual_end, status) VALUES (?,?,?,?,?)',
              [existing.id, s.stage, n(s.plan_end), n(s.actual_end), computeStatus(s.plan_end, s.actual_end)]);
          }
        }
      }
      return this.getById(existing.id)!;
    }

    run(`INSERT INTO features (feature_id, subsystem, workbench, story_code, menu, feature_name, milestone, sprint)
      VALUES (?,?,?,?,?,?,?,?)`,
      [row.feature_id, n(row.subsystem), n(row.workbench), n(row.story_code), n(row.menu),
       n(row.feature_name), n(row.milestone), n(row.sprint)]);

    const newId = queryOne<{ id: number }>('SELECT last_insert_rowid() as id')!.id;
    for (const s of row.stages) {
      run('INSERT INTO feature_stages (feature_pk, stage, plan_end, actual_end, status) VALUES (?,?,?,?,?)',
        [newId, s.stage, n(s.plan_end), n(s.actual_end), computeStatus(s.plan_end, s.actual_end)]);
    }
    return this.getById(newId)!;
  },

  updateStage(featurePk: number, stage: number, data: { plan_end?: string; actual_end?: string }, changedBy?: string, note?: string): FeatureStage | undefined {
    const existing = queryOne<FeatureStage>('SELECT * FROM feature_stages WHERE feature_pk=? AND stage=?', [featurePk, stage]);
    const status = computeStatus(data.plan_end ?? existing?.plan_end, data.actual_end ?? existing?.actual_end);

    if (existing) {
      if (data.plan_end !== undefined && data.plan_end !== existing.plan_end) {
        addHistory(featurePk, stage, 'plan_end', existing.plan_end, data.plan_end, changedBy, note);
      }
      if (data.actual_end !== undefined && data.actual_end !== existing.actual_end) {
        addHistory(featurePk, stage, 'actual_end', existing.actual_end, data.actual_end, changedBy, note);
      }
      run('UPDATE feature_stages SET plan_end=?, actual_end=?, status=? WHERE id=?',
        [n(data.plan_end) ?? existing.plan_end ?? null, n(data.actual_end) ?? existing.actual_end ?? null, status, existing.id]);
    } else {
      run('INSERT INTO feature_stages (feature_pk, stage, plan_end, actual_end, status) VALUES (?,?,?,?,?)',
        [featurePk, stage, n(data.plan_end), n(data.actual_end), status]);
      addHistory(featurePk, stage, 'created', null, JSON.stringify(data), changedBy, note);
    }
    run("UPDATE features SET updated_at=datetime('now') WHERE id=?", [featurePk]);
    return queryOne<FeatureStage>('SELECT * FROM feature_stages WHERE feature_pk=? AND stage=?', [featurePk, stage]);
  },

  delete(id: number): void {
    run('DELETE FROM features WHERE id = ?', [id]);
  },

  getHistory(featurePk: number): StatusHistory[] {
    return queryAll<StatusHistory>('SELECT * FROM status_history WHERE feature_pk=? ORDER BY changed_at DESC', [featurePk]);
  },

  getGanttData(params?: { subsystem?: string; sprint?: string }): GanttRow[] {
    const features = this.getAll(params);
    return features.map(f => ({
      feature_pk: f.id,
      feature_id: f.feature_id,
      feature_name: f.feature_name,
      subsystem: f.subsystem,
      sprint: f.sprint,
      stages: (f.stages || []).map(s => ({
        stage: s.stage,
        plan_end: s.plan_end,
        actual_end: s.actual_end,
        status: s.status,
      })),
    }));
  },

  getSubsystemSummary(): SubsystemSummary[] {
    const rows = queryAll<{
      subsystem: string; total: number;
      s1c: number; s2c: number; s3c: number; s4c: number; s5c: number;
      s1t: number; s2t: number; s3t: number; s4t: number; s5t: number;
      delayed: number; not_started: number;
    }>(`
      SELECT
        COALESCE(f.subsystem,'uncategorized') as subsystem,
        COUNT(*) as total,
        SUM(CASE WHEN fs1.status='completed' THEN 1 ELSE 0 END) as s1c,
        SUM(CASE WHEN fs2.status='completed' THEN 1 ELSE 0 END) as s2c,
        SUM(CASE WHEN fs3.status='completed' THEN 1 ELSE 0 END) as s3c,
        SUM(CASE WHEN fs4.status='completed' THEN 1 ELSE 0 END) as s4c,
        SUM(CASE WHEN fs5.status='completed' THEN 1 ELSE 0 END) as s5c,
        SUM(CASE WHEN fs1.status IS NOT NULL THEN 1 ELSE 0 END) as s1t,
        SUM(CASE WHEN fs2.status IS NOT NULL THEN 1 ELSE 0 END) as s2t,
        SUM(CASE WHEN fs3.status IS NOT NULL THEN 1 ELSE 0 END) as s3t,
        SUM(CASE WHEN fs4.status IS NOT NULL THEN 1 ELSE 0 END) as s4t,
        SUM(CASE WHEN fs5.status IS NOT NULL THEN 1 ELSE 0 END) as s5t,
        SUM(CASE WHEN fs1.status='delayed' OR fs2.status='delayed' OR fs3.status='delayed' OR fs4.status='delayed' OR fs5.status='delayed' THEN 1 ELSE 0 END) as delayed,
        SUM(CASE WHEN fs1.status='not_started' OR fs1.status IS NULL THEN 1 ELSE 0 END) as not_started
      FROM features f
      LEFT JOIN feature_stages fs1 ON f.id=fs1.feature_pk AND fs1.stage=1
      LEFT JOIN feature_stages fs2 ON f.id=fs2.feature_pk AND fs2.stage=2
      LEFT JOIN feature_stages fs3 ON f.id=fs3.feature_pk AND fs3.stage=3
      LEFT JOIN feature_stages fs4 ON f.id=fs4.feature_pk AND fs4.stage=4
      LEFT JOIN feature_stages fs5 ON f.id=fs5.feature_pk AND fs5.stage=5
      GROUP BY f.subsystem ORDER BY total DESC
    `);

    return rows.map(r => ({
      subsystem: r.subsystem,
      total: r.total,
      stage_completed: [r.s1c, r.s2c, r.s3c, r.s4c, r.s5c],
      stage_total: [r.s1t, r.s2t, r.s3t, r.s4t, r.s5t],
      delayed: r.delayed,
      not_started: r.not_started,
    }));
  },

  getSprintSummary() {
    return queryAll<{ sprint: string; total: number; completed: number; delayed: number }>(`
      SELECT f.sprint, COUNT(*) as total,
        SUM(CASE WHEN fs5.status='completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN fs1.status='delayed' OR fs2.status='delayed' OR fs3.status='delayed' OR fs4.status='delayed' OR fs5.status='delayed' THEN 1 ELSE 0 END) as delayed
      FROM features f
      LEFT JOIN feature_stages fs1 ON f.id=fs1.feature_pk AND fs1.stage=1
      LEFT JOIN feature_stages fs2 ON f.id=fs2.feature_pk AND fs2.stage=2
      LEFT JOIN feature_stages fs3 ON f.id=fs3.feature_pk AND fs3.stage=3
      LEFT JOIN feature_stages fs4 ON f.id=fs4.feature_pk AND fs4.stage=4
      LEFT JOIN feature_stages fs5 ON f.id=fs5.feature_pk AND fs5.stage=5
      WHERE f.sprint IS NOT NULL
      GROUP BY f.sprint ORDER BY f.sprint
    `);
  },
};

export const gitlabIssueService = {
  syncFromGitlab(issue: { iid: number; title: string; state: string; labels: string[]; assignees?: { name: string }[]; created_at: string; updated_at: string; closed_at?: string; web_url: string }, featurePk?: number): GitlabIssue {
    const existing = queryOne<GitlabIssue>('SELECT * FROM gitlab_issues WHERE gitlab_iid=?', [issue.iid]);
    const assignees = (issue.assignees || []).map(a => a.name).join('; ');
    const labels = (issue.labels || []).join(',');

    if (existing) {
      run(`UPDATE gitlab_issues SET title=?, state=?, labels=?, feature_pk=?, assignees=?,
        updated_at_gitlab=?, closed_at=?, synced_at=datetime('now') WHERE id=?`,
        [issue.title, issue.state, labels, featurePk ?? existing.feature_pk ?? null, assignees,
         issue.updated_at, n(issue.closed_at), existing.id]);
      return queryOne<GitlabIssue>('SELECT * FROM gitlab_issues WHERE id=?', [existing.id])!;
    }

    run(`INSERT INTO gitlab_issues (gitlab_iid, title, state, labels, feature_pk, assignees,
      created_at_gitlab, updated_at_gitlab, closed_at, web_url) VALUES (?,?,?,?,?,?,?,?,?,?)`,
      [issue.iid, issue.title, issue.state, labels, featurePk ?? null, assignees,
       issue.created_at, issue.updated_at, n(issue.closed_at), issue.web_url]);
    return queryOne<GitlabIssue>('SELECT * FROM gitlab_issues WHERE gitlab_iid=?', [issue.iid])!;
  },

  getUnlinked(): GitlabIssue[] {
    return queryAll<GitlabIssue>('SELECT * FROM gitlab_issues WHERE feature_pk IS NULL ORDER BY gitlab_iid');
  },
};

export const subsystemService = {
  getAll() {
    return queryAll<import('../types').Subsystem>('SELECT * FROM subsystems ORDER BY sort_order');
  },
};

function computeStatus(planEnd?: string | null, actualEnd?: string | null): string {
  if (actualEnd) return 'completed';
  if (!planEnd) return 'not_started';
  const today = new Date().toISOString().slice(0, 10);
  if (planEnd < today) return 'delayed';
  return 'in_progress';
}

function addHistory(featurePk: number, stage: number | undefined, fieldName: string, oldValue: string | null | undefined, newValue: string | null | undefined, changedBy?: string, note?: string) {
  run('INSERT INTO status_history (feature_pk, stage, field_name, old_value, new_value, changed_by, note) VALUES (?,?,?,?,?,?,?)',
    [featurePk, stage ?? null, fieldName, n(oldValue), n(newValue), n(changedBy), n(note)]);
}
