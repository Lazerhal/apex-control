import { NextRequest, NextResponse } from 'next/server';

const FASTAPI_URL = 'http://localhost:8001';

async function handler(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const pathname = '/' + path.join('/');
  const search = request.nextUrl.search || '';
  const url = `${FASTAPI_URL}${pathname}${search}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const auth = request.headers.get('authorization');
  if (auth) headers['Authorization'] = auth;

  const cookie = request.headers.get('cookie');
  if (cookie) headers['Cookie'] = cookie;

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  if (!['GET', 'HEAD'].includes(request.method)) {
    init.body = await request.text();
  }

  const res = await fetch(url, init);
  const data = await res.text();

  const response = new NextResponse(data, {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  });

  // Forward set-cookie header
  const setCookie = res.headers.get('set-cookie');
  if (setCookie) response.headers.set('set-cookie', setCookie);

  return response;
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
