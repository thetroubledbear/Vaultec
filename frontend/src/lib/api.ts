interface ApiErrorDetail {
  detail?: string;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as ApiErrorDetail;
    return data.detail || response.statusText || 'Unknown error';
  } catch {
    return response.statusText || 'Unknown error';
  }
}

export async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(endpoint, {
    ...options,
    credentials: 'include',
    headers: {
      ...options.headers
    }
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiJson<T>(
  endpoint: string,
  method: string = 'GET',
  body?: unknown
): Promise<T> {
  const options: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json'
    }
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  return apiCall<T>(endpoint, options);
}

export async function apiMultipart<T>(
  endpoint: string,
  formData: FormData
): Promise<T> {
  return apiCall<T>(endpoint, {
    method: 'POST',
    body: formData
  });
}

export async function apiDownload(endpoint: string): Promise<Blob> {
  const response = await fetch(endpoint, {
    credentials: 'include'
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new ApiError(response.status, detail);
  }

  return response.blob();
}

export function contentUrl(docId: string): string {
  return `/api/documents/${docId}/content`;
}

export function downloadUrl(docId: string): string {
  return `/api/documents/${docId}/download`;
}
