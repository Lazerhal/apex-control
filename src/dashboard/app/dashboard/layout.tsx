'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/sidebar';
import { api } from '@/lib/api';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('apex_token');
    if (!token) {
      router.replace('/login');
      return;
    }
    api.me().then(() => setReady(true)).catch(() => {
      localStorage.removeItem('apex_token');
      router.replace('/login');
    });
  }, [router]);

  if (!ready) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-base)',
      }}>
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: '13px' }}>
          Loading APEX...
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <main style={{
        flex: 1,
        padding: '28px 32px',
        overflow: 'auto',
        background: 'var(--bg-base)',
      }}>
        {children}
      </main>
    </div>
  );
}
