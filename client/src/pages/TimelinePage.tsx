import React, { useEffect, useState, useCallback } from 'react';
import { Table, Tag, Button, Modal, Form, DatePicker, Select, Space, Typography, message, Tooltip, Drawer } from 'antd';
import { EditOutlined, HistoryOutlined } from '@ant-design/icons';
import { featureApi, subsystemApi } from '../services/api';
import { STAGE_NAMES, STAGE_SHORT, STAGE_COLORS, SUBSYSTEM_COLORS } from '../types';
import type { Feature, Subsystem, StageStatus, StatusHistory } from '../types';
import dayjs from 'dayjs';

const TimelinePage: React.FC = () => {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [subsystems, setSubsystems] = useState<Subsystem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSub, setFilterSub] = useState<string | undefined>();
  const [filterSprint, setFilterSprint] = useState<string | undefined>();
  const [editFeature, setEditFeature] = useState<Feature | null>(null);
  const [historyFeature, setHistoryFeature] = useState<Feature | null>(null);
  const [history, setHistory] = useState<StatusHistory[]>([]);
  const [form] = Form.useForm();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [f, s] = await Promise.all([featureApi.getAll({ subsystem: filterSub, sprint: filterSprint }), subsystemApi.getAll()]);
      setFeatures(f);
      setSubsystems(s);
    } catch { /* */ }
    finally { setLoading(false); }
  }, [filterSub, filterSprint]);

  useEffect(() => { loadData(); }, [loadData]);

  const sprints = Array.from(new Set(features.map(f => f.sprint).filter(Boolean) as string[])).sort();

  const handleEdit = (feature: Feature) => {
    setEditFeature(feature);
    const vals: Record<string, dayjs.Dayjs | undefined> = {};
    for (const s of feature.stages || []) {
      if (s.plan_end) vals[`s${s.stage}_plan`] = dayjs(s.plan_end);
      if (s.actual_end) vals[`s${s.stage}_actual`] = dayjs(s.actual_end);
    }
    form.setFieldsValue(vals);
  };

  const handleSave = async () => {
    if (!editFeature) return;
    try {
      const values = form.getFieldsValue();
      for (let s = 1; s <= 5; s++) {
        const planEnd = values[`s${s}_plan`]?.format('YYYY-MM-DD');
        const actualEnd = values[`s${s}_actual`]?.format('YYYY-MM-DD');
        const existing = editFeature.stages?.find(st => st.stage === s);
        if (planEnd || actualEnd || existing) {
          await featureApi.updateStage(editFeature.id, s, { plan_end: planEnd, actual_end: actualEnd }, 'web');
        }
      }
      message.success('更新成功');
      setEditFeature(null);
      form.resetFields();
      loadData();
    } catch { message.error('更新失败'); }
  };

  const handleHistory = async (feature: Feature) => {
    setHistoryFeature(feature);
    try {
      const h = await featureApi.getHistory(feature.id);
      setHistory(h);
    } catch { setHistory([]); }
  };

  const getStageStatus = (feature: Feature, stage: number): StageStatus | undefined => {
    return feature.stages?.find(s => s.stage === stage)?.status;
  };

  const getStageDate = (feature: Feature, stage: number, field: 'plan_end' | 'actual_end'): string | undefined => {
    return feature.stages?.find(s => s.stage === stage)?.[field];
  };

  const renderDateCell = (feature: Feature, stage: number, field: 'plan_end' | 'actual_end') => {
    const date = getStageDate(feature, stage, field);
    const status = getStageStatus(feature, stage);
    const isDelayed = status === 'delayed' && field === 'actual_end';
    const isPlan = field === 'plan_end';

    if (!date) return <span style={{ color: '#d9d9d9' }}>-</span>;

    return (
      <Tooltip title={`${isPlan ? '计划' : '实际'}: ${date}`}>
        <span style={{
          fontSize: 12,
          color: isDelayed ? '#ff4d4f' : (isPlan ? STAGE_COLORS[stage] : '#333'),
          fontWeight: isDelayed ? 700 : (isPlan ? 400 : 500),
        }}>
          {date.slice(5)}
          {isDelayed && ' ⚠'}
        </span>
      </Tooltip>
    );
  };

  const stageColumns = [1, 2, 3, 4, 5].flatMap(s => [
    {
      title: <span style={{ color: STAGE_COLORS[s], fontSize: 12 }}>{STAGE_SHORT[s]} 计划</span>,
      key: `s${s}_plan`,
      width: 76,
      render: (_: unknown, r: Feature) => renderDateCell(r, s, 'plan_end'),
    },
    {
      title: <span style={{ fontSize: 12 }}>实际</span>,
      key: `s${s}_actual`,
      width: 76,
      render: (_: unknown, r: Feature) => renderDateCell(r, s, 'actual_end'),
    },
  ]);

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>关键时间节点</Typography.Title>
        <Space wrap>
          <Select placeholder="子系统" allowClear style={{ width: 140 }} value={filterSub} onChange={setFilterSub}
            options={subsystems.map(s => ({ label: s.key, value: s.key }))} />
          <Select placeholder="Sprint" allowClear style={{ width: 120 }} value={filterSprint} onChange={setFilterSprint}
            options={sprints.map(s => ({ label: s, value: s }))} />
        </Space>
      </div>

      <Table
        dataSource={features}
        rowKey="id"
        loading={loading}
        size="small"
        scroll={{ x: 1400 }}
        pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ['20', '50', '100', '200'] }}
        columns={[
          {
            title: '子系统', dataIndex: 'subsystem', width: 80, fixed: 'left',
            render: (v: string) => <Tag color={SUBSYSTEM_COLORS[v] || 'default'}>{v}</Tag>,
          },
          { title: '编号', dataIndex: 'feature_id', width: 90, fixed: 'left', render: (v: string) => <Typography.Text strong style={{ fontSize: 12 }}>{v}</Typography.Text> },
          { title: '功能点', dataIndex: 'feature_name', width: 140, ellipsis: true, fixed: 'left' },
          { title: 'Sprint', dataIndex: 'sprint', width: 70 },
          ...stageColumns,
          {
            title: '操作', key: 'actions', width: 80, fixed: 'right',
            render: (_: unknown, r: Feature) => (
              <Space size={4}>
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(r)} />
                <Button type="link" size="small" icon={<HistoryOutlined />} onClick={() => handleHistory(r)} />
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editFeature ? `编辑 ${editFeature.feature_id}` : ''}
        open={!!editFeature}
        onOk={handleSave}
        onCancel={() => { setEditFeature(null); form.resetFields(); }}
        width={560}
        destroyOnClose
      >
        {editFeature && (
          <Form form={form} layout="vertical" size="small">
            <Typography.Text type="secondary">{editFeature.feature_name}</Typography.Text>
            {[1, 2, 3, 4, 5].map(s => (
              <div key={s} style={{ marginTop: 12, padding: '8px 12px', background: '#fafafa', borderRadius: 6, borderLeft: `3px solid ${STAGE_COLORS[s]}` }}>
                <Typography.Text strong style={{ color: STAGE_COLORS[s] }}>{STAGE_NAMES[s]}</Typography.Text>
                <Space style={{ marginTop: 4 }}>
                  <Form.Item name={`s${s}_plan`} label="计划" style={{ marginBottom: 0 }}><DatePicker format="YYYY-MM-DD" /></Form.Item>
                  <Form.Item name={`s${s}_actual`} label="实际" style={{ marginBottom: 0 }}><DatePicker format="YYYY-MM-DD" /></Form.Item>
                </Space>
              </div>
            ))}
          </Form>
        )}
      </Modal>

      <Drawer
        title={historyFeature ? `${historyFeature.feature_id} 变更历史` : ''}
        open={!!historyFeature}
        onClose={() => setHistoryFeature(null)}
        width={500}
      >
        {history.length === 0 ? <Typography.Text type="secondary">暂无变更记录</Typography.Text> : (
          <Table
            dataSource={history}
            rowKey="id"
            size="small"
            pagination={false}
            columns={[
              { title: '时间', dataIndex: 'changed_at', width: 140, render: (v: string) => v?.slice(0, 16) },
              { title: '步骤', dataIndex: 'stage', width: 60, render: (v: number) => v ? STAGE_SHORT[v] : '-' },
              { title: '字段', dataIndex: 'field_name', width: 80 },
              { title: '旧值', dataIndex: 'old_value', width: 90, ellipsis: true },
              { title: '新值', dataIndex: 'new_value', width: 90, ellipsis: true },
              { title: '操作人', dataIndex: 'changed_by', width: 60 },
            ]}
          />
        )}
      </Drawer>
    </div>
  );
};

export default TimelinePage;
