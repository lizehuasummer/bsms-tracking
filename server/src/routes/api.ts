import { Router, Request, Response } from 'express';
import { featureService, gitlabIssueService, subsystemService } from '../services/store';
import { gitlabService } from '../services/gitlab';
import { config } from '../config';
import { getDatabase, saveDatabase } from '../database';

const router = Router();

interface ExcelRow {
  subsystem?: string; workbench?: string; story_code?: string; menu?: string;
  feature_id: string; feature_name: string; milestone?: string; sprint?: string;
  [key: string]: unknown;
}

router.post('/import/excel', async (req: Request, res: Response) => {
  const start = Date.now();
  try {
    const { rows } = req.body as { rows: ExcelRow[] };
    if (!Array.isArray(rows)) return res.status(400).json({ error: 'rows array required' });

    let upserted = 0;
    for (const row of rows) {
      if (!row.feature_id || !row.feature_name) continue;
      const stages: { stage: number; plan_end?: string; actual_end?: string }[] = [];
      for (let s = 1; s <= 5; s++) {
        const pe = row[`s${s}_plan`] as string | undefined;
        const ae = row[`s${s}_actual`] as string | undefined;
        if (pe || ae) stages.push({ stage: s, plan_end: pe || undefined, actual_end: ae || undefined });
      }
      featureService.upsertFromExcel({
        subsystem: row.subsystem,
        workbench: row.workbench,
        story_code: row.story_code,
        menu: row.menu,
        feature_id: row.feature_id,
        feature_name: row.feature_name,
        milestone: row.milestone,
        sprint: row.sprint,
        stages,
      });
      upserted++;
    }

    const duration = Date.now() - start;
    const db = getDatabase();
    db.run('INSERT INTO sync_log (type, total_synced, duration_ms, detail) VALUES (?,?,?,?)',
      ['excel_import', upserted, duration, `${rows.length} rows received`]);
    saveDatabase();

    res.json({ success: true, imported: upserted, duration_ms: duration });
  } catch (error) {
    res.status(500).json({ error: String(error) });
  }
});

router.post('/sync/gitlab', async (_req: Request, res: Response) => {
  const start = Date.now();
  try {
    const projectId = config.gitlab.projectId;
    const [openedIssues, closedIssues] = await Promise.all([
      gitlabService.getAllIssues(projectId, { state: 'opened' }),
      gitlabService.getAllIssues(projectId, { state: 'closed' }),
    ]);

    const allIssues = [...openedIssues, ...closedIssues];
    let synced = 0;
    const featPattern = /([A-Z]{2,5}-F\d{1,4})/;

    for (const issue of allIssues) {
      const i = issue as Record<string, any>;
      const titleMatch = featPattern.exec(i.title || '');
      let featurePk: number | undefined;
      if (titleMatch) {
        const f = featureService.getByFeatureId(titleMatch[1]);
        if (f) featurePk = f.id;
      }
      gitlabIssueService.syncFromGitlab({
        iid: i.iid,
        title: i.title,
        state: i.state,
        labels: i.labels || [],
        assignees: i.assignees || [],
        created_at: i.created_at,
        updated_at: i.updated_at,
        closed_at: i.closed_at,
        web_url: i.web_url,
      }, featurePk);
      synced++;
    }

    const duration = Date.now() - start;
    const db = getDatabase();
    db.run('INSERT INTO sync_log (type, total_synced, duration_ms, detail) VALUES (?,?,?,?)',
      ['gitlab_sync', synced, duration, `opened:${openedIssues.length} closed:${closedIssues.length}`]);
    saveDatabase();

    res.json({ success: true, total: synced, opened: openedIssues.length, closed: closedIssues.length, duration_ms: duration });
  } catch (error) {
    res.status(500).json({ error: String(error) });
  }
});

router.get('/features', (req: Request, res: Response) => {
  const subsystem = typeof req.query.subsystem === 'string' ? req.query.subsystem : undefined;
  const sprint = typeof req.query.sprint === 'string' ? req.query.sprint : undefined;
  const stage_status = typeof req.query.stage_status === 'string' ? req.query.stage_status : undefined;
  const features = featureService.getAll({ subsystem, sprint, stage_status });
  res.json(features);
});

router.get('/features/:id', (req: Request, res: Response) => {
  const feature = featureService.getById(parseInt(req.params.id as string));
  if (!feature) return res.status(404).json({ error: 'Not found' });
  res.json(feature);
});

router.patch('/features/:id/stages', (req: Request, res: Response) => {
  const { stage, plan_end, actual_end, changed_by, note } = req.body as { stage: number; plan_end?: string; actual_end?: string; changed_by?: string; note?: string };
  if (!stage || stage < 1 || stage > 5) return res.status(400).json({ error: 'stage 1-5 required' });
  const result = featureService.updateStage(parseInt(req.params.id as string), stage, { plan_end, actual_end }, changed_by, note);
  res.json(result);
});

router.get('/features/:id/history', (req: Request, res: Response) => {
  const history = featureService.getHistory(parseInt(req.params.id as string));
  res.json(history);
});

router.delete('/features/:id', (req: Request, res: Response) => {
  featureService.delete(parseInt(req.params.id as string));
  res.json({ success: true });
});

router.get('/gantt', (req: Request, res: Response) => {
  const subsystem = typeof req.query.subsystem === 'string' ? req.query.subsystem : undefined;
  const sprint = typeof req.query.sprint === 'string' ? req.query.sprint : undefined;
  const data = featureService.getGanttData({ subsystem, sprint });
  res.json(data);
});

router.get('/stats/subsystems', (_req: Request, res: Response) => {
  res.json(featureService.getSubsystemSummary());
});

router.get('/stats/sprints', (_req: Request, res: Response) => {
  res.json(featureService.getSprintSummary());
});

router.get('/subsystems', (_req: Request, res: Response) => {
  res.json(subsystemService.getAll());
});

router.get('/gitlab/unlinked', (_req: Request, res: Response) => {
  res.json(gitlabIssueService.getUnlinked());
});

router.get('/sync-log', (_req: Request, res: Response) => {
  const db = getDatabase();
  const stmt = db.prepare('SELECT * FROM sync_log ORDER BY created_at DESC LIMIT 10');
  const logs: unknown[] = [];
  while (stmt.step()) logs.push(stmt.getAsObject());
  stmt.free();
  res.json(logs);
});

router.get('/gitlab/test', async (_req: Request, res: Response) => {
  const result = await gitlabService.testConnection();
  res.json(result);
});

export default router;
