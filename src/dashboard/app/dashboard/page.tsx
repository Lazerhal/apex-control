'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, type Project, type DashboardSummary } from '@/lib/api';

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

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', padding: '18px 20px' }}>
      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: '26px', fontWeight: '700', fontFamily: 'var(--mono)', lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>{sub}</div>}
    </div>
  );
}

function ProjectCard({ project, onClick }: { project: Project; onClick: () => void }) {
  const stageColor = STAGE_COLORS[project.stage] || '#6B7280';
  return (
    <div
      onClick={onClick}
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', padding: '20px', cursor: 'pointer' }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-bright)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div>
          <div style={{ fontSize: '15px', fontWeight: '600', marginBottom: '4px' }}>{project.name}</div>
          <div style={{ fontSize: '11px', fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{project.apex_id}</div>
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '20px', border: "1px solid " + stageColor + "40", color: stageColor, background: stageColor + "15", fontWeight: '500' }}>
            {project.stage}
          </span>
          <span style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '20px', border: '1px solid var(--border-bright)', color: 'var(--text-muted)' }}>
            {TYPE_LABELS[project.type] || project.type}
          </span>
        </div>
      </div>
      {project.short_description && (
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '0 0 14px', lineHeight: '1.5', overflow: 'hidden', maxHeight: '42px' }}>
          {project.short_description}
        </p>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Cost: <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--mono)' }}>${project.monthly_cost_usd}/mo</span>
          </span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Score: <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--mono)' }}>{project.completeness_score}</span>
          </span>
        </div>
        {project.live_url && (
          <a href={project.live_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} style={{ fontSize: '12px', color: 'var(--accent)', textDecoration: 'none' }}>
            ↗ Live
          </a>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getDashboardSummary(), api.getProjects()])
      .then(([s, p]) => { setSummary(s); setProjects(p); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: '13px' }}>Loading portfolio...</div>;
  }

  const profit = summary?.financials.monthly_profit_usd ?? 0;

  return (
    <div>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', margin: '0 0 4px' }}>Portfolio</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
          {summary?.projects.total ?? 0} projects · all systems
        </p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '28px' }}>
        <StatCard label="Projects" value={summary?.projects.total ?? 0} sub={(summary?.projects.by_stage?.live ?? 0) + " live"} />
        <StatCard label="Open Tasks" value={summary?.tasks.open ?? 0} sub={(summary?.tasks.critical ?? 0) + " critical"} />
        <StatCard label="New Ideas" value={summary?.ideas.new ?? 0} />
        <StatCard label="Monthly Cost" value={"$" + (summary?.financials.monthly_cost_usd.toFixed(2) ?? "0")} />
        <StatCard label="Monthly P&L" value={(profit >= 0 ? "+" : "") + "$" + profit.toFixed(2)} sub={profit < 0 ? "pre-revenue" : "profitable"} />
      </div>
      <div>
        <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-secondary)', margin: '0 0 14px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Active Projects
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '14px' }}>
          {projects.map(p => <ProjectCard key={p.id} project={p} onClick={() => router.push(`/dashboard/projects/${p.id}`)} />)}
        </div>
      </div>
    </div>
  );
}
