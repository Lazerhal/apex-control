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

  // The API limits failed logins per client address, which it only learns from this header
  const clientIp = request.headers.get('cf-connecting-ip');
  if (clientIp) headers['CF-Connecting-IP'] = clientIp;

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  if (!['GET', 'HEAD'].includes(request.method)) {
    init.body = await request.text();
  }

  // A stream request must stop calling the API as soon as the browser goes away.
  // Other requests carry no signal and run to completion.
  const isStreamRequest =
    request.method === 'GET' &&
    (pathname === '/api/events/stream' ||
      (request.headers.get('accept')?.includes('text/event-stream') ?? false));
  if (isStreamRequest) {
    // Registered before fetch so it also covers the wait for response headers
    const upstream = new AbortController();
    const abort = () => upstream.abort();
    if (request.signal.aborted) abort();
    else request.signal.addEventListener('abort', abort, { once: true });
    init.signal = upstream.signal;
  }

  let res: Response;
  let isEventStream: boolean;
  let data: ReadableStream<Uint8Array> | string | null;
  try {
    res = await fetch(url, init);
    // Server-Sent Events never end, so pass the body through instead of buffering it
    isEventStream = res.headers.get('content-type')?.startsWith('text/event-stream') ?? false;
    data = isEventStream ? res.body : await res.text();
  } catch (err) {
    // Only stream requests carry a signal: the browser left, so there is nobody to respond to
    if (init.signal?.aborted && (err as Error).name === 'AbortError') {
      return new NextResponse(null, { status: 499 });
    }
    throw err;
  }

  // These statuses may not have a body, not even an empty one
  const isBodiless = [204, 205, 304].includes(res.status);

  const responseHeaders: Record<string, string> = isBodiless
    ? {}
    : isEventStream
    ? {
        'Content-Type': 'text/event-stream',
        // no-transform keeps Next.js compression from buffering the stream
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
      }
    : { 'Content-Type': 'application/json' };

  const response = new NextResponse(isBodiless ? null : data, {
    status: res.status,
    headers: responseHeaders,
  });

  const retryAfter = res.headers.get('retry-after');
  if (retryAfter) response.headers.set('retry-after', retryAfter);

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
