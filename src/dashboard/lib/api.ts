const API_BASE = '/api/proxy';

async function apiFetch(path: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('apex_token') : null;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    credentials: 'include',
  });
  if (!res.ok) {
    if (res.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('apex_token');
        window.location.href = '/login';
      }
    }
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => apiFetch('/auth/me'),
  logout: () => apiFetch('/auth/logout', { method: 'POST' }),
  getProjects: (params?: { stage?: string; type?: string }) => {
    const q = params ? '?' + new URLSearchParams(params as Record<string, string>).toString() : '';
    return apiFetch(`/api/projects${q}`);
  },
  getProject: (id: string) => apiFetch(`/api/projects/${id}`),
  getDashboardSummary: () => apiFetch('/api/dashboard/summary'),
  createIdea: (data: { title: string; raw_description: string }) =>
    apiFetch('/api/ideas', { method: 'POST', body: JSON.stringify({ ...data, source: 'dashboard' }) }),
  getIdeas: () => apiFetch('/api/ideas'),
};

export type Project = {
  id: string;
  apex_id: string;
  name: string;
  type: string;
  stage: string;
  owner: string;
  short_description: string | null;
  goal: string | null;
  status_note: string | null;
  live_url: string | null;
  github_repo: string | null;
  monthly_cost_usd: number;
  monthly_revenue_usd: number;
  cost_efficiency_flag: string;
  completeness_score: number;
  created_at: string;
  updated_at: string;
};

export type DashboardSummary = {
  projects: { total: number; by_stage: Record<string, number> };
  tasks: { open: number; critical: number };
  ideas: { new: number };
  recommendations: { new: number };
  financials: { monthly_cost_usd: number; monthly_revenue_usd: number; monthly_profit_usd: number };
};
