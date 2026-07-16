import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Statistic, Tag, Table, Button, message, Spin, Typography, Progress, Space, Upload } from 'antd';
import { SyncOutlined, UploadOutlined, CheckCircleOutlined, ClockCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { statsApi, importApi } from '../services/api';
import { STAGE_SHORT, STAGE_COLORS, SUBSYSTEM_COLORS } from '../types';
import type { SubsystemSummary, SprintSummary } from '../types';

const Dashboard: React.FC = () => {
  const [summary, setSummary] = useState<SubsystemSummary[]>([]);
  const [sprints, setSprints] = useState<SprintSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [importing, setImporting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, sp] = await Promise.all([statsApi.getSubsystems(), statsApi.getSprints()]);
      setSummary(s);
      setSprints(sp);
    } catch { message.error('加载失败'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSyncGitlab = async () => {
    setSyncing(true);
    try {
      const r = await importApi.syncGitlab();
      message.success(`同步完成: ${r.total} 条, 耗时 ${(r.duration_ms / 1000).toFixed(1)}s`);
      loadData();
    } catch { message.error('同步失败'); }
    finally { setSyncing(false); }
  };

  const handleImportExcel = async (file: File) => {
    setImporting(true);
    try {
      const XLSX = await import('xlsx');
      const wb = XLSX.read(await file.arrayBuffer(), { type: 'array' });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rawRows: Record<string, unknown>[] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });

      const COL_MAP: Record<string, number> = { A: 0, B: 1, C: 2, D: 3, E: 4, F: 5, G: 6, H: 7, J: 9, K: 10, L: 11, M: 12, N: 13, O: 14, P: 15, Q: 16, R: 17, S: 18 };
      const rows: Record<string, unknown>[] = [];
      for (let i = 4; i < rawRows.length; i++) {
        const r = rawRows[i];
        const fid = r[COL_MAP.E];
        if (!fid || String(fid).trim() === '') continue;
        const fmtDate = (v: unknown) => {
          if (!v || v === '' || v === '0') return undefined;
          if (typeof v === 'number') {
            const d = new Date(Date.UTC(1899, 11, 30 + Math.floor(v)));
            return isNaN(d.getTime()) ? undefined : d.toISOString().slice(0, 10);
          }
          const s = String(v);
          if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
          return undefined;
        };
        rows.push({
          subsystem: r[COL_MAP.A] || undefined,
          workbench: r[COL_MAP.B] || undefined,
          story_code: r[COL_MAP.C] || undefined,
          menu: r[COL_MAP.D] || undefined,
          feature_id: String(fid).trim(),
          feature_name: r[COL_MAP.F] || '',
          milestone: r[COL_MAP.G] || undefined,
          sprint: r[COL_MAP.H] || undefined,
          s1_plan: fmtDate(r[COL_MAP.J]),
          s1_actual: fmtDate(r[COL_MAP.K]),
          s2_plan: fmtDate(r[COL_MAP.L]),
          s2_actual: fmtDate(r[COL_MAP.M]),
          s3_plan: fmtDate(r[COL_MAP.N]),
          s3_actual: fmtDate(r[COL_MAP.O]),
          s4_plan: fmtDate(r[COL_MAP.P]),
          s4_actual: fmtDate(r[COL_MAP.Q]),
          s5_plan: fmtDate(r[COL_MAP.R]),
          s5_actual: fmtDate(r[COL_MAP.S]),
        });
      }

      const result = await importApi.importExcel(rows);
      message.success(`导入成功: ${result.imported} 条, 耗时 ${(result.duration_ms / 1000).toFixed(1)}s`);
      loadData();
    } catch (e) {
      message.error('导入失败: ' + String(e));
    } finally { setImporting(false); }
    return false;
  };

  const totalFeatures = summary.reduce((s, x) => s + x.total, 0);
  const totalDelayed = summary.reduce((s, x) => s + x.delayed, 0);
  const totalNotStarted = summary.reduce((s, x) => s + x.not_started, 0);
  const totalCompleted = summary.reduce((s, x) => s + x.stage_completed[4], 0);

  if (loading && !summary.length) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;

  return (
    <div>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>BSMS 功能点进度追踪</Typography.Title>
          <Typography.Text type="secondary">Excel 为主 · GitLab Issue 补充 · 5 步骤进度管理</Typography.Text>
        </div>
        <Space wrap>
          <Upload accept=".xlsx,.xls" showUploadList={false} beforeUpload={handleImportExcel} disabled={importing}>
            <Button icon={<UploadOutlined />} loading={importing}>导入 Excel</Button>
          </Upload>
          <Button type="primary" icon={<SyncOutlined />} onClick={handleSyncGitlab} loading={syncing}>同步 GitLab</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="功能点总数" value={totalFeatures} valueStyle={{ fontWeight: 700 }} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="已验收" value={totalCompleted} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a', fontWeight: 700 }} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="已延期" value={totalDelayed} prefix={<WarningOutlined />} valueStyle={{ color: '#ff4d4f', fontWeight: 700 }} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="未开始" value={totalNotStarted} prefix={<ClockCircleOutlined />} valueStyle={{ color: '#999', fontWeight: 700 }} /></Card></Col>
      </Row>

      <Typography.Title level={5}>5 步骤完成率</Typography.Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {[1, 2, 3, 4, 5].map(s => {
          const total = summary.reduce((sum, x) => sum + (x.stage_total[s - 1] || 0), 0);
          const done = summary.reduce((sum, x) => sum + (x.stage_completed[s - 1] || 0), 0);
          const pct = total > 0 ? Math.round((done / total) * 100) : 0;
          return (
            <Col xs={24} sm={12} md={8} lg={4} key={s}>
              <Card size="small" style={{ borderLeft: `3px solid ${STAGE_COLORS[s]}` }}>
                <Statistic title={<span style={{ color: STAGE_COLORS[s] }}>{STAGE_SHORT[s]}</span>}
                  value={pct} suffix="%" valueStyle={{ color: STAGE_COLORS[s] }} />
                <Progress percent={pct} showInfo={false} strokeColor={STAGE_COLORS[s]} size="small" />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>{done} / {total}</Typography.Text>
              </Card>
            </Col>
          );
        })}
      </Row>

      <Typography.Title level={5}>子系统概览</Typography.Title>
      <Table
        dataSource={summary}
        rowKey="subsystem"
        size="small"
        pagination={false}
        style={{ marginBottom: 24 }}
        columns={[
          { title: '子系统', dataIndex: 'subsystem', render: (v: string) => <Space><span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 2, background: SUBSYSTEM_COLORS[v] || '#8c8c8c' }} />{v}</Space> },
          { title: '功能点', dataIndex: 'total', width: 70 },
          { title: '未开始', dataIndex: 'not_started', width: 70 },
          { title: '延期', dataIndex: 'delayed', width: 60, render: (v: number) => v > 0 ? <Tag color="red">{v}</Tag> : v },
          ...[1, 2, 3, 4, 5].map(s => ({
            title: STAGE_SHORT[s], key: `s${s}`, width: 80,
            render: (_: unknown, r: SubsystemSummary) => {
              const t = r.stage_total[s - 1] || 0;
              const c = r.stage_completed[s - 1] || 0;
              return t > 0 ? <span>{c}/{t}</span> : '-';
            },
          })),
          {
            title: '验收率', key: 'rate', width: 100,
            render: (_: unknown, r: SubsystemSummary) => {
              const t = r.stage_total[4] || 0;
              const c = r.stage_completed[4] || 0;
              return t > 0 ? <Progress percent={Math.round((c / t) * 100)} size="small" /> : <Progress percent={0} size="small" />;
            },
          },
        ]}
      />

      {sprints.length > 0 && (
        <>
          <Typography.Title level={5}>Sprint 进度</Typography.Title>
          <Row gutter={[12, 12]} style={{ marginBottom: 24 }}>
            {sprints.map(sp => (
              <Col xs={12} sm={8} md={6} lg={4} key={sp.sprint}>
                <Card size="small">
                  <Statistic title={sp.sprint} value={sp.total} suffix={<span style={{ fontSize: 12, color: '#52c41a' }}>完成 {sp.completed}</span>} />
                  {sp.delayed > 0 && <Tag color="red" style={{ marginTop: 4 }}>延期 {sp.delayed}</Tag>}
                </Card>
              </Col>
            ))}
          </Row>
        </>
      )}
    </div>
  );
};

export default Dashboard;
