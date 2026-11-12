import { API_BASE_URL } from '../../../lib/apiConfig';

export async function GET() {
  const origin = (process.env.BACKEND_ORIGIN || API_BASE_URL).replace(/\/+$/, '');
  let available = false;

  try {
    const response = await fetch(`${origin}/health/liveness`, {
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(20_000),
    });
    if (response.ok) {
      const health = await response.json();
      available = health?.status === 'alive';
    }
  } catch {
    // A connection failure or a slow startup can leave the probe unanswered.
  }

  return Response.json({ available }, {
    status: available ? 200 : 503,
    headers: { 'Cache-Control': 'no-store' },
  });
}
