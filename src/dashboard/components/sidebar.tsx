'use client';
import { useRouter, usePathname } from 'next/navigation';
import { api } from '@/lib/api';

const NAV = [
  { href: '/dashboard', label: 'Portfolio', icon: '◈' },
  { href: '/dashboard/projects', label: 'Projects', icon: '⬡' },
  { href: '/dashboard/tasks', label: 'Tasks', icon: '◻' },
  { href: '/dashboard/ideas', label: 'Ideas', icon: '◇' },
  { href: '/dashboard/costs', label: 'Costs', icon: '◎' },
  { href: '/dashboard/findings', label: 'Findings', icon: '◉' },
];

export default function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();

  const handleLogout = async () => {
    await api.logout();
    localStorage.removeItem('apex_token');
    router.replace('/login');
  };

  return (
    <aside style={{
      width: '220px',
      minHeight: '100vh',
      background: 'var(--bg-surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      padding: '0',
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{
        padding: '20px 20px 16px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px', height: '28px',
            background: 'var(--accent)',
            borderRadius: '6px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '13px', fontWeight: '700', color: '#fff',
          }}>A</div>
          <div>
            <div style={{ fontSize: '14px', fontWeight: '700', lineHeight: 1 }}>APEX</div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--mono)', lineHeight: 1.4 }}>v0.1.0</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 8px' }}>
        {NAV.map(item => {
          const active = pathname === item.href;
          return (
            <button
              key={item.href}
              onClick={() => router.push(item.href)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '9px 12px',
                borderRadius: '7px',
                border: 'none',
                background: active ? 'var(--bg-elevated)' : 'transparent',
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontSize: '13px',
                fontWeight: active ? '600' : '400',
                cursor: 'pointer',
                textAlign: 'left',
                marginBottom: '2px',
                borderLeft: active ? '2px solid var(--accent)' : '2px solid transparent',
              }}
            >
              <span style={{ fontSize: '14px', opacity: active ? 1 : 0.6 }}>{item.icon}</span>
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Bottom */}
      <div style={{ padding: '12px 8px', borderTop: '1px solid var(--border)' }}>
        <button
          onClick={handleLogout}
          style={{
            width: '100%',
            padding: '9px 12px',
            background: 'transparent',
            border: 'none',
            borderRadius: '7px',
            color: 'var(--text-muted)',
            fontSize: '13px',
            cursor: 'pointer',
            textAlign: 'left',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <span>⬡</span> Sign out
        </button>
      </div>
    </aside>
  );
}
