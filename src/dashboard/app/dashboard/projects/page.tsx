'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, type Project } from '@/lib/api';

const STAGE_COLORS: Record<string, string> = {
  live: '#10B981',
  'active-development': '#3B82F6',
  planning: '#F59E0B',
  idea: '#8B5CF6',
  paused: '#6B7280',
  retired: '#4B5563',
};

const TYPE_LABELS: Record<string, string> = {
  'product-tool': 'Product',
  'content-engine': 'Content',
  saas: 'SaaS',
  'governed-system': 'Governed',
  infrastructure: 'Infra',
  idea: 'Idea',
};

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    api.getProjects().then(setProjects).catch(console.error).finally(() => setLoading(false));
  }, []);

  const filtered = filter === 'all' ? projects : projects.filter(p => p.stage === filter);
  const stages = ['all', ...Array.from(new Set(projects.map(p => p.stage)))];

  if (loading) return <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: '13px' }}>Loading...</div>;

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', margin: '0 0 4px' }}>Projects</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>{projects.length} total</p>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {stages.map(s => (
          <button key={s} onClick={() => setFilter(s)} style={{
            padding: '6px 14px', borderRadius: '20px', border: '1px solid',
            borderColor: filter === s ? 'var(--accent)' : 'var(--border-bright)',
            background: filter === s ? 'var(--accent)' : 'transparent',
            color: filter === s ? '#fff' : 'var(--text-secondary)',
            fontSize: '12px', cursor: 'pointer', fontWeight: filter === s ? '600' : '400',
          }}>{s}</button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '14px' }}>
        {filtered.map(p => {
          const stageColor = STAGE_COLORS[p.stage] || '#6B7280';
          return (
            <div key={p.id} onClick={() => router.push(`/dashboard/projects/${p.id}`)}
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', padding: '20px', cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-bright)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <div>
                  <div style={{ fontSize: '15px', fontWeight: '600', marginBottom: '3px' }}>{p.name}</div>
                  <div style={{ fontSize: '11px', fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{p.apex_id}</div>
                </div>
                <span style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '20px', border: `1px solid ${stageColor}40`, color: stageColor, background: `${stageColor}15`, fontWeight: '500', height: 'fit-content' }}>
                  {p.stage}
                </span>
              </div>
              {p.short_description && (
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '0 0 12px', lineHeight: '1.5', overflow: 'hidden', maxHeight: '40px' }}>
                  {p.short_description}
                </p>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '12px', borderTop: '1px solid var(--border)', fontSize: '12px', color: 'var(--text-muted)' }}>
                <span>{TYPE_LABELS[p.type] || p.type}</span>
                <span style={{ fontFamily: 'var(--mono)' }}>${p.monthly_cost_usd}/mo</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
