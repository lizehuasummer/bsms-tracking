import axios from 'axios';
import type { Feature, FeatureStage, GanttRow, SubsystemSummary, SprintSummary, SyncResult, Subsystem, StatusHistory } from '../types';

const api = axios.create({ baseURL: '/api', timeout: 120000 });

export const importApi = {
  importExcel: (rows: Record<string, unknown>[]) => api.post<SyncResult>('/import/excel', { rows }).then(r => r.data),
  syncGitlab: () => api.post<SyncResult>('/sync/gitlab').then(r => r.data),
  testGitlab: () => api.get('/gitlab/test').then(r => r.data),
};

export const featureApi = {
  getAll: (params?: { subsystem?: string; sprint?: string }) =>
    api.get<Feature[]>('/features', { params }).then(r => r.data),
  getById: (id: number) => api.get<Feature>(`/features/${id}`).then(r => r.data),
  updateStage: (id: number, stage: number, data: { plan_end?: string; actual_end?: string }, changedBy?: string, note?: string) =>
    api.patch<FeatureStage>(`/features/${id}/stages`, { stage, ...data, changed_by: changedBy, note }).then(r => r.data),
  getHistory: (id: number) => api.get<StatusHistory[]>(`/features/${id}/history`).then(r => r.data),
  delete: (id: number) => api.delete(`/features/${id}`),
};

export const ganttApi = {
  getData: (params?: { subsystem?: string; sprint?: string }) =>
    api.get<GanttRow[]>('/gantt', { params }).then(r => r.data),
};

export const statsApi = {
  getSubsystems: () => api.get<SubsystemSummary[]>('/stats/subsystems').then(r => r.data),
  getSprints: () => api.get<SprintSummary[]>('/stats/sprints').then(r => r.data),
};

export const subsystemApi = {
  getAll: () => api.get<Subsystem[]>('/subsystems').then(r => r.data),
};

export const syncLogApi = {
  getRecent: () => api.get('/sync-log').then(r => r.data),
};
