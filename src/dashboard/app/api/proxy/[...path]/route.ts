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

  const upstream = new AbortController();
  const res = await fetch(url, { ...init, signal: upstream.signal });
  // Server-Sent Events never end, so pass the body through instead of buffering it
  const isEventStream = res.headers.get('content-type')?.startsWith('text/event-stream') ?? false;
  const data = isEventStream ? res.body : await res.text();
  if (isEventStream) {
    // Close the upstream connection when the browser goes away, or the API keeps listening
    if (request.signal.aborted) upstream.abort();
    request.signal.addEventListener('abort', () => upstream.abort(), { once: true });
  }

  const responseHeaders: Record<string, string> = isEventStream
    ? {
        'Content-Type': 'text/event-stream',
        // no-transform keeps Next.js compression from buffering the stream
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
      }
    : { 'Content-Type': 'application/json' };

  const response = new NextResponse(data, {
    status: res.status,
    headers: responseHeaders,
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
