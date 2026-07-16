export type StageStatus = 'not_started' | 'in_progress' | 'completed' | 'delayed';

export interface Subsystem {
  id: number;
  key: string;
  name: string;
  color: string;
  sort_order: number;
}

export interface FeatureStage {
  id: number;
  feature_pk: number;
  stage: number;
  plan_end?: string;
  actual_end?: string;
  status: StageStatus;
}

export interface Feature {
  id: number;
  feature_id: string;
  subsystem?: string;
  workbench?: string;
  story_code?: string;
  menu?: string;
  feature_name: string;
  milestone?: string;
  sprint?: string;
  gitlab_iid?: number;
  created_at: string;
  updated_at: string;
  stages?: FeatureStage[];
}

export interface StatusHistory {
  id: number;
  feature_pk: number;
  stage?: number;
  field_name: string;
  old_value?: string;
  new_value?: string;
  changed_at: string;
  changed_by?: string;
  note?: string;
}

export interface GanttRow {
  feature_pk: number;
  feature_id: string;
  feature_name: string;
  subsystem?: string;
  sprint?: string;
  stages: { stage: number; plan_end?: string; actual_end?: string; status: StageStatus }[];
}

export interface SubsystemSummary {
  subsystem: string;
  total: number;
  stage_completed: number[];
  stage_total: number[];
  delayed: number;
  not_started: number;
}

export interface SprintSummary {
  sprint: string;
  total: number;
  completed: number;
  delayed: number;
}

export interface SyncResult {
  success: boolean;
  total?: number;
  imported?: number;
  opened?: number;
  closed?: number;
  duration_ms: number;
}

export const STAGE_NAMES: Record<number, string> = {
  1: '开发 Development',
  2: '测试 Testing',
  3: '调试 Debugging',
  4: '部署 Deployment',
  5: '验收 KCCIT',
};

export const STAGE_SHORT: Record<number, string> = {
  1: 'Dev',
  2: 'Test',
  3: 'Debug',
  4: 'Deploy',
  5: 'KCCIT',
};

export const STAGE_COLORS: Record<number, string> = {
  1: '#1677ff',
  2: '#52c41a',
  3: '#fa8c16',
  4: '#722ed1',
  5: '#eb2f96',
};

export const STATUS_CONFIG: Record<StageStatus, { label: string; color: string }> = {
  not_started: { label: '未开始', color: 'default' },
  in_progress: { label: '进行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  delayed: { label: '已延期', color: 'error' },
};

export const SUBSYSTEM_COLORS: Record<string, string> = {
  BCM: '#1677ff', DMM: '#52c41a', DOP: '#722ed1', D3M: '#fa8c16',
  QSM: '#eb2f96', STM: '#13c2c2', IDM: '#faad14', QMS: '#f5222d',
  BSC: '#2f54eb', CYLIMS: '#595959',
};
