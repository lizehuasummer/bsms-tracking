import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { Card, Select, Spin, Typography, Space, Tooltip } from 'antd';
import { ganttApi } from '../services/api';
import { STAGE_COLORS, STAGE_SHORT, SUBSYSTEM_COLORS } from '../types';
import type { GanttRow } from '../types';

const STAGE_KEYS = [1, 2, 3, 4, 5] as const;
const DAY_WIDTH = 24;
const ROW_HEIGHT = 36;
const BAR_HEIGHT = 14;
const LEFT_WIDTH = 240;

function parseDate(s?: string): number | null {
  if (!s) return null;
  const d = new Date(s + 'T00:00:00');
  return isNaN(d.getTime()) ? null : d.getTime();
}

function addDays(ts: number, n: number): number {
  return ts + n * 86400000;
}

function daysBetween(a: number, b: number): number {
  return Math.round((b - a) / 86400000);
}

function dateStr(ts: number): string {
  return new Date(ts).toISOString().slice(0, 10);
}

const GanttPage: React.FC = () => {
  const [data, setData] = useState<GanttRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSub, setFilterSub] = useState<string | undefined>();
  const [filterSprint, setFilterSprint] = useState<string | undefined>();
  const [expandedSubs, setExpandedSubs] = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const g = await ganttApi.getData({ subsystem: filterSub, sprint: filterSprint });
      setData(g);
      const subs = new Set(g.map(r => r.subsystem).filter(Boolean) as string[]);
      setExpandedSubs(subs);
    } catch { /* */ }
    finally { setLoading(false); }
  }, [filterSub, filterSprint]);

  useEffect(() => { loadData(); }, [loadData]);

  const { minDate, maxDate, totalDays } = useMemo(() => {
    const dates: number[] = [];
    for (const row of data) {
      for (const s of row.stages) {
        const p = parseDate(s.plan_end);
        const a = parseDate(s.actual_end);
        if (p) { dates.push(p); dates.push(addDays(p, -14)); }
        if (a) { dates.push(a); dates.push(addDays(a, -14)); }
      }
    }
    if (!dates.length) {
      const now = Date.now();
      dates.push(addDays(now, -90), addDays(now, 90));
    }
    const min = Math.min(...dates);
    const max = Math.max(...dates);
    const total = daysBetween(min, max) + 30;
    return { minDate: min, maxDate: max, totalDays: Math.max(total, 60) };
  }, [data]);

  const grouped = useMemo(() => {
    const map = new Map<string, GanttRow[]>();
    for (const row of data) {
      const key = row.subsystem || 'uncategorized';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(row);
    }
    return map;
  }, [data]);

  const sprints = useMemo(() => {
    const set = new Set(data.map(r => r.sprint).filter(Boolean) as string[]);
    return Array.from(set).sort();
  }, [data]);

  const weekCols = useMemo(() => {
    const cols: { ts: number; label: string }[] = [];
    let t = minDate;
    const dayOfWeek = new Date(t).getDay();
    t = addDays(t, dayOfWeek === 0 ? -6 : 1 - dayOfWeek);
    while (t < addDays(maxDate, 14)) {
      cols.push({ ts: t, label: new Date(t).toISOString().slice(5, 10) });
      t = addDays(t, 7);
    }
    return cols;
  }, [minDate, maxDate]);

  const todayX = useMemo(() => daysBetween(minDate, Date.now()) * DAY_WIDTH, [minDate]);

  const toggleSub = (sub: string) => {
    setExpandedSubs(prev => {
      const next = new Set(prev);
      if (next.has(sub)) next.delete(sub); else next.add(sub);
      return next;
    });
  };

  const renderBar = (stage: GanttRow['stages'][0], prevEnd: number | null) => {
    const planEnd = parseDate(stage.plan_end);
    const actualEnd = parseDate(stage.actual_end);
    const planStart = prevEnd || (planEnd ? addDays(planEnd, -14) : null);
    const color = STAGE_COLORS[stage.stage];
    const bars: React.ReactNode[] = [];

    if (planEnd && planStart) {
      const x1 = daysBetween(minDate, planStart) * DAY_WIDTH;
      const x2 = daysBetween(minDate, planEnd) * DAY_WIDTH;
      const w = Math.max(x2 - x1, DAY_WIDTH);
      bars.push(
        <Tooltip key={`p${stage.stage}`} title={`计划: ${dateStr(planStart)} → ${dateStr(planEnd)}`}>
          <rect x={x1} y={2} width={w} height={BAR_HEIGHT} fill={color} fillOpacity={0.25} stroke={color} strokeWidth={1} strokeDasharray="4 2" rx={2} />
        </Tooltip>
      );
    } else if (planEnd) {
      const x2 = daysBetween(minDate, planEnd) * DAY_WIDTH;
      const x1 = Math.max(x2 - 14 * DAY_WIDTH, 0);
      const w = Math.max(x2 - x1, DAY_WIDTH);
      bars.push(
        <Tooltip key={`p${stage.stage}`} title={`计划结束: ${dateStr(planEnd)}`}>
          <rect x={x1} y={2} width={w} height={BAR_HEIGHT} fill={color} fillOpacity={0.25} stroke={color} strokeWidth={1} strokeDasharray="4 2" rx={2} />
        </Tooltip>
      );
    }

    if (actualEnd) {
      const actualStart = prevEnd || addDays(actualEnd, -14);
      const x1 = daysBetween(minDate, actualStart) * DAY_WIDTH;
      const x2 = daysBetween(minDate, actualEnd) * DAY_WIDTH;
      const w = Math.max(x2 - x1, DAY_WIDTH);
      const delayed = planEnd && actualEnd > planEnd;
      const fillColor = delayed ? '#ff4d4f' : color;
      bars.push(
        <Tooltip key={`a${stage.stage}`} title={`实际: ${dateStr(actualStart)} → ${dateStr(actualEnd)}${delayed ? ' (延期)' : ''}`}>
          <rect x={x1} y={18} width={w} height={BAR_HEIGHT} fill={fillColor} fillOpacity={0.7} stroke={fillColor} strokeWidth={1} rx={2} />
        </Tooltip>
      );
    }

    if (!planEnd && !actualEnd) {
      bars.push(
        <text key={`n${stage.stage}`} x={0} y={14} fill="#ccc" fontSize={10}>{STAGE_SHORT[stage.stage]}: -</text>
      );
    }

    return <g>{bars}</g>;
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;

  const svgWidth = LEFT_WIDTH + totalDays * DAY_WIDTH;
  const headerHeight = 28;

  let currentY = headerHeight;
  const rowPositions: { sub: string; y: number; rows: GanttRow[]; isHeader: boolean }[] = [];
  for (const [sub, rows] of grouped) {
    rowPositions.push({ sub, y: currentY, rows: [], isHeader: true });
    currentY += ROW_HEIGHT;
    if (expandedSubs.has(sub)) {
      for (const row of rows) {
        rowPositions.push({ sub, y: currentY, rows: [row], isHeader: false });
        currentY += ROW_HEIGHT;
      }
    }
  }
  const svgHeight = currentY;

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>甘特图 — 5 步骤进度</Typography.Title>
        <Space wrap>
          <Select placeholder="子系统" allowClear style={{ width: 140 }} value={filterSub} onChange={setFilterSub}
            options={[...grouped.keys()].map(k => ({ label: k, value: k }))} />
          <Select placeholder="Sprint" allowClear style={{ width: 120 }} value={filterSprint} onChange={setFilterSprint}
            options={sprints.map(s => ({ label: s, value: s }))} />
        </Space>
      </div>

      <Card bodyStyle={{ padding: 0 }} style={{ overflow: 'hidden' }}>
        <div ref={containerRef} style={{ overflow: 'auto', maxHeight: 'calc(100vh - 180px)' }}>
          <svg width={svgWidth} height={svgHeight} style={{ display: 'block' }}>
            <defs>
              <pattern id="weekGrid" width={7 * DAY_WIDTH} height={ROW_HEIGHT} patternUnits="userSpaceOnUse">
                <rect width={7 * DAY_WIDTH} height={ROW_HEIGHT} fill="none" stroke="#f0f0f0" strokeWidth={0.5} />
              </pattern>
            </defs>

            <rect x={LEFT_WIDTH} y={0} width={totalDays * DAY_WIDTH} height={svgHeight} fill="url(#weekGrid)" />

            {weekCols.map((w, i) => (
              <g key={i}>
                <line x1={LEFT_WIDTH + daysBetween(minDate, w.ts) * DAY_WIDTH} y1={0}
                  x2={LEFT_WIDTH + daysBetween(minDate, w.ts) * DAY_WIDTH} y2={svgHeight} stroke="#e8e8e8" strokeWidth={0.5} />
                <text x={LEFT_WIDTH + daysBetween(minDate, w.ts) * DAY_WIDTH + 4} y={14} fill="#999" fontSize={10}>{w.label}</text>
              </g>
            ))}

            {todayX >= 0 && todayX <= totalDays * DAY_WIDTH && (
              <line x1={LEFT_WIDTH + todayX} y1={0} x2={LEFT_WIDTH + todayX} y2={svgHeight} stroke="#1677ff" strokeWidth={1.5} strokeDasharray="6 3" />
            )}

            <rect x={0} y={0} width={LEFT_WIDTH} height={svgHeight} fill="white" />

            {rowPositions.map((rp) => {
              if (rp.isHeader) {
                const color = SUBSYSTEM_COLORS[rp.sub] || '#8c8c8c';
                const count = rp.rows.length || grouped.get(rp.sub)?.length || 0;
                return (
                  <g key={`h${rp.sub}`} onClick={() => toggleSub(rp.sub)} style={{ cursor: 'pointer' }}>
                    <rect x={0} y={rp.y} width={LEFT_WIDTH} height={ROW_HEIGHT} fill={color} fillOpacity={0.1} />
                    <rect x={0} y={rp.y} width={4} height={ROW_HEIGHT} fill={color} />
                    <text x={12} y={rp.y + ROW_HEIGHT / 2 + 4} fill={color} fontSize={13} fontWeight={700}>{rp.sub}</text>
                    <text x={LEFT_WIDTH - 40} y={rp.y + ROW_HEIGHT / 2 + 4} fill="#999" fontSize={11}>{count}项 {expandedSubs.has(rp.sub) ? '▲' : '▼'}</text>
                    <rect x={LEFT_WIDTH} y={rp.y} width={totalDays * DAY_WIDTH} height={ROW_HEIGHT} fill={color} fillOpacity={0.03} />
                  </g>
                );
              }

              const row = rp.rows[0];
              let prevEnd: number | null = null;
              return (
                <g key={`r${row.feature_pk}`}>
                  <text x={12} y={rp.y + 13} fill="#333" fontSize={11} fontWeight={500}>{row.feature_id}</text>
                  <text x={12} y={rp.y + 27} fill="#999" fontSize={9}>{row.feature_name?.slice(0, 16)}</text>
                  {row.stages.map(s => {
                    const bar = renderBar(s, prevEnd);
                    if (s.actual_end) prevEnd = parseDate(s.actual_end);
                    else if (s.plan_end) prevEnd = parseDate(s.plan_end);
                    return <g key={s.stage} transform={`translate(${LEFT_WIDTH}, ${rp.y + 2})`}>{bar}</g>;
                  })}
                </g>
              );
            })}
          </svg>
        </div>
      </Card>

      <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {STAGE_KEYS.map(s => (
          <Space key={s} size={4}>
            <span style={{ display: 'inline-block', width: 16, height: 10, background: STAGE_COLORS[s], opacity: 0.25, border: `1px dashed ${STAGE_COLORS[s]}` }} />
            <span style={{ fontSize: 11, color: '#666' }}>计划</span>
            <span style={{ display: 'inline-block', width: 16, height: 10, background: STAGE_COLORS[s], opacity: 0.7 }} />
            <span style={{ fontSize: 11, color: '#666' }}>{STAGE_SHORT[s]}</span>
          </Space>
        ))}
        <Space size={4}>
          <span style={{ display: 'inline-block', width: 16, height: 10, background: '#ff4d4f', opacity: 0.7 }} />
          <span style={{ fontSize: 11, color: '#666' }}>延期</span>
        </Space>
        <Space size={4}>
          <span style={{ display: 'inline-block', width: 16, height: 2, background: '#1677ff', border: '1px dashed #1677ff' }} />
          <span style={{ fontSize: 11, color: '#666' }}>今天</span>
        </Space>
      </div>
    </div>
  );
};

export default GanttPage;
