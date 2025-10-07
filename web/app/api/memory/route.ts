const serverBase = process.env.PY_SERVER_URL || 'http://localhost:8001';
const pausePath = `${serverBase.replace(/\/$/, '')}/api/v1/chat/memory/pause`;
const resumePath = `${serverBase.replace(/\/$/, '')}/api/v1/chat/memory/resume`;
const statusPath = `${serverBase.replace(/\/$/, '')}/api/v1/chat/memory/status`;

async function forward(method: 'POST' | 'GET', endpoint: string) {
  try {
    const url = endpoint === 'pause' ? pausePath : endpoint === 'resume' ? resumePath : statusPath;
    const res = await fetch(url, {
      method,
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    const bodyText = await res.text();
    const headers = new Headers({ 'Content-Type': 'application/json; charset=utf-8' });
    return new Response(bodyText || '{}', { status: res.status, headers });
  } catch (error: any) {
    const message = error?.message || 'Failed to reach Python server';
    return new Response(JSON.stringify({ error: message }), {
      status: 502,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }
}

export async function POST(request: Request) {
  const { action } = await request.json();
  return forward('POST', action);
}

export async function GET() {
  return forward('GET', 'status');
}
