'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, apiFetch, type Project } from '@/lib/api';

type Task = { id: string; apex_task_id: string; title: string; priority: string; type: string; status: string; description?: string; estimated_effort?: string; assigned_to?: string; created_at: string; };
type Note = { id: string; content: string; source: string; created_at: string; };

const PRIORITY_COLORS: Record<string, string> = { critical: '#EF4444', high: '#F59E0B', medium: '#3B82F6', low: '#6B7280', backlog: '#4B5563' };
const STAGE_COLORS: Record<string, string> = { live: '#10B981', 'active-development': '#3B82F6', planning: '#F59E0B', idea: '#8B5CF6', paused: '#6B7280', retired: '#4B5563' };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '28px' }}>
      <h2 style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)', margin: '0 0 12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</h2>
      {children}
    </div>
  );
}

export default function ProjectDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview'|'tasks'|'notes'>('overview');
  const [newNote, setNewNote] = useState('');
  const [newTask, setNewTask] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.getProject(id as string),
      apiFetch(`/api/projects/${id}/tasks`),
      apiFetch(`/api/projects/${id}/notes`),
    ]).then(([p, t, n]) => {
      setProject(p);
      setTasks(t);
      setNotes(n);
    }).catch(console.error).finally(() => setLoading(false));
  }, [id]);

  const addNote = async () => {
    if (!newNote.trim() || !id) return;
    setSaving(true);
    try {
      const n = await apiFetch(`/api/projects/${id}/notes`, { method: 'POST', body: JSON.stringify({ content: newNote, source: 'dashboard' }) });
      setNotes(prev => [n, ...prev]);
      setNewNote('');
    } catch(e) { console.error(e); } finally { setSaving(false); }
  };

  const addTask = async () => {
    if (!newTask.trim() || !id) return;
    setSaving(true);
    try {
      const t = await apiFetch(`/api/projects/${id}/tasks`, { method: 'POST', body: JSON.stringify({ title: newTask, priority: 'medium', type: 'feature' }) });
      setTasks(prev => [t, ...prev]);
      setNewTask('');
    } catch(e) { console.error(e); } finally { setSaving(false); }
  };

  if (loading) return <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: '13px' }}>Loading...</div>;
  if (!project) return <div style={{ color: 'var(--text-muted)' }}>Project not found</div>;

  const stageColor = STAGE_COLORS[project.stage] || '#6B7280';
  const openTasks = tasks.filter(t => t.status === 'open');
  const criticalTasks = tasks.filter(t => t.status === 'open' && t.priority === 'critical');

  return (
    <div>
      {/* Back */}
      <button onClick={() => router.back()} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '13px', marginBottom: '16px', padding: 0 }}>
        ← Back
      </button>

      {/* Header */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: '700', margin: '0 0 4px' }}>{project.name}</h1>
            <div style={{ fontSize: '12px', fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{project.apex_id}</div>
          </div>
          <span style={{ fontSize: '12px', padding: '4px 12px', borderRadius: '20px', border: `1px solid ${stageColor}40`, color: stageColor, background: `${stageColor}15`, fontWeight: '600' }}>
            {project.stage}
          </span>
        </div>

        {project.status_note && (
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: '0 0 16px', lineHeight: '1.6' }}>{project.status_note}</p>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
          {[
            { label: 'Monthly Cost', value: `$${project.monthly_cost_usd}/mo` },
            { label: 'Revenue', value: `$${project.monthly_revenue_usd}/mo` },
            { label: 'Open Tasks', value: openTasks.length },
            { label: 'Critical', value: criticalTasks.length },
            { label: 'Completeness', value: `${project.completeness_score}%` },
          ].map(s => (
            <div key={s.label} style={{ background: 'var(--bg-elevated)', borderRadius: '8px', padding: '12px 14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
              <div style={{ fontSize: '18px', fontWeight: '700', fontFamily: 'var(--mono)' }}>{s.value}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
          {project.live_url && <a href={project.live_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '13px', color: 'var(--accent)', textDecoration: 'none' }}>↗ Live Site</a>}
          {project.github_repo && <a href={project.github_repo} target="_blank" rel="noopener noreferrer" style={{ fontSize: '13px', color: 'var(--text-secondary)', textDecoration: 'none' }}>⎇ GitHub</a>}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', borderBottom: '1px solid var(--border)', paddingBottom: '0' }}>
        {(['overview', 'tasks', 'notes'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} style={{
            padding: '8px 16px', background: 'none', border: 'none',
            borderBottom: activeTab === tab ? '2px solid var(--accent)' : '2px solid transparent',
            color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-muted)',
            fontSize: '13px', fontWeight: activeTab === tab ? '600' : '400',
            cursor: 'pointer', marginBottom: '-1px', textTransform: 'capitalize',
          }}>{tab} {tab === 'tasks' ? `(${openTasks.length})` : tab === 'notes' ? `(${notes.length})` : ''}</button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div>
          {project.short_description && (
            <Section title="Description">
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.6', margin: 0 }}>{project.short_description}</p>
            </Section>
          )}
          {project.goal && (
            <Section title="Goal">
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.6', margin: 0 }}>{project.goal}</p>
            </Section>
          )}
          <Section title="Details">
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
              {[
                { label: 'Type', value: project.type },
                { label: 'Stage', value: project.stage },
                { label: 'Owner', value: project.owner },
                { label: 'Cost Efficiency', value: project.cost_efficiency_flag },
                { label: 'Created', value: new Date(project.created_at).toLocaleDateString() },
                { label: 'Last Updated', value: new Date(project.updated_at).toLocaleDateString() },
              ].map((row, i) => (
                <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 16px', borderBottom: i < 5 ? '1px solid var(--border)' : 'none' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{row.label}</span>
                  <span style={{ fontSize: '13px', fontFamily: 'var(--mono)', color: 'var(--text-secondary)' }}>{row.value}</span>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {/* Tasks Tab */}
      {activeTab === 'tasks' && (
        <div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <input
              value={newTask}
              onChange={e => setNewTask(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addTask()}
              placeholder="Add a task and press Enter..."
              style={{ flex: 1, padding: '9px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border-bright)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '13px', outline: 'none' }}
            />
            <button onClick={addTask} disabled={saving} style={{ padding: '9px 16px', background: 'var(--accent)', border: 'none', borderRadius: '8px', color: '#fff', fontSize: '13px', cursor: 'pointer' }}>
              Add
            </button>
          </div>

          {criticalTasks.length > 0 && (
            <div style={{ background: '#7f1d1d20', border: '1px solid #ef444440', borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', fontSize: '13px', color: '#fca5a5' }}>
              ⚠ {criticalTasks.length} critical task{criticalTasks.length > 1 ? 's' : ''} need attention
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {tasks.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No tasks yet.</div>}
            {tasks.map(task => (
              <div key={task.id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '14px 16px', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '11px', padding: '2px 7px', borderRadius: '4px', background: `${PRIORITY_COLORS[task.priority]}20`, color: PRIORITY_COLORS[task.priority], fontWeight: '600', whiteSpace: 'nowrap', marginTop: '2px' }}>
                  {task.priority}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '13px', fontWeight: '500', marginBottom: task.description ? '4px' : 0 }}>{task.title}</div>
                  {task.description && <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.5' }}>{task.description}</div>}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                  <span style={{ fontSize: '11px', fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{task.apex_task_id}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{task.type}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Notes Tab */}
      {activeTab === 'notes' && (
        <div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <textarea
              value={newNote}
              onChange={e => setNewNote(e.target.value)}
              placeholder="Add a note..."
              rows={3}
              style={{ flex: 1, padding: '9px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border-bright)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '13px', outline: 'none', resize: 'vertical', fontFamily: 'inherit' }}
            />
            <button onClick={addNote} disabled={saving} style={{ padding: '9px 16px', background: 'var(--accent)', border: 'none', borderRadius: '8px', color: '#fff', fontSize: '13px', cursor: 'pointer', alignSelf: 'flex-start' }}>
              Add
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {notes.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No notes yet.</div>}
            {notes.map(note => (
              <div key={note.id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '14px 16px' }}>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.6', whiteSpace: 'pre-wrap', marginBottom: '8px' }}>{note.content}</div>
                <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
                  <span>{new Date(note.created_at).toLocaleString()}</span>
                  <span>{note.source}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
