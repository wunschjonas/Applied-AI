export const API_BASE_URL = 'http://localhost:8080';

/** The backend returns image URLs relative to its own root, e.g. /generated-images/<post_id>.png */
export function toAbsoluteApiUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}
