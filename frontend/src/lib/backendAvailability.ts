export class BackendUnavailableError extends Error {
  constructor() {
    super('Server belum bisa dihubungi. Silakan coba lagi sebentar.');
    this.name = 'BackendUnavailableError';
  }
}

export async function fetchBackend(url: string, options: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error instanceof TypeError || (error instanceof DOMException && error.name === 'TimeoutError')) {
      throw new BackendUnavailableError();
    }
    throw error;
  }

  if ([502, 503, 504].includes(response.status)) {
    throw new BackendUnavailableError();
  }
  return response;
}
