import axios from 'axios';
import https from 'https';
import { config } from '../config';

class GitLabService {
  private client;

  constructor() {
    this.client = axios.create({
      baseURL: `${config.gitlab.url}/api/v4`,
      headers: {
        'Private-Token': config.gitlab.token,
      },
      timeout: 30000,
      httpsAgent: new https.Agent({
        rejectUnauthorized: false,
      }),
    });
  }

  async getAllIssues(projectId: number, params: Record<string, unknown> = {}): Promise<Record<string, unknown>[]> {
    const allIssues: Record<string, unknown>[] = [];
    let page = 1;
    const perPage = 100;

    while (true) {
      const { data, headers } = await this.client.get(`/projects/${projectId}/issues`, {
        params: { ...params, per_page: perPage, page },
      });

      allIssues.push(...data);

      const totalPages = parseInt(headers['x-total-pages'] || '1', 10);
      if (page >= totalPages) break;
      page++;
    }

    return allIssues;
  }

  async getProject(projectId: number) {
    const { data } = await this.client.get(`/projects/${projectId}`);
    return data;
  }

  async testConnection() {
    try {
      const { data } = await this.client.get('/user');
      return { success: true, user: data };
    } catch {
      return { success: false, user: null };
    }
  }
}

export const gitlabService = new GitLabService();
