export interface Subsystem {
  id: number;
  key: string;
  name: string;
  color: string;
  sort_order: number;
  created_at: string;
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

export type StageStatus = 'not_started' | 'in_progress' | 'completed' | 'delayed';

export interface FeatureStage {
  id: number;
  feature_pk: number;
  stage: number;
  plan_end?: string;
  actual_end?: string;
  status: StageStatus;
}

export const STAGE_NAMES: Record<number, string> = {
  1: 'Development',
  2: 'Testing',
  3: 'Debugging',
  4: 'Deployment',
  5: 'KCCIT Verification',
};

export const STAGE_COLORS: Record<number, string> = {
  1: '#1677ff',
  2: '#52c41a',
  3: '#fa8c16',
  4: '#722ed1',
  5: '#eb2f96',
};

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

export interface GitlabIssue {
  id: number;
  gitlab_iid: number;
  title?: string;
  state?: string;
  labels?: string;
  feature_pk?: number;
  assignees?: string;
  created_at_gitlab?: string;
  updated_at_gitlab?: string;
  closed_at?: string;
  web_url?: string;
  synced_at: string;
}

export interface SyncLog {
  id: number;
  type: string;
  total_synced: number;
  duration_ms: number;
  detail?: string;
  created_at: string;
}

export interface GanttRow {
  feature_pk: number;
  feature_id: string;
  feature_name: string;
  subsystem?: string;
  sprint?: string;
  stages: {
    stage: number;
    plan_end?: string;
    actual_end?: string;
    status: StageStatus;
  }[];
}

export interface SubsystemSummary {
  subsystem: string;
  total: number;
  stage_completed: number[];
  stage_total: number[];
  delayed: number;
  not_started: number;
}

export const SUBSYSTEM_COLORS: Record<string, string> = {
  BCM: '#1677ff',
  DMM: '#52c41a',
  DOP: '#722ed1',
  D3M: '#fa8c16',
  QSM: '#eb2f96',
  STM: '#13c2c2',
  IDM: '#faad14',
  QMS: '#f5222d',
  BSC: '#2f54eb',
  CYLIMS: '#595959',
};
