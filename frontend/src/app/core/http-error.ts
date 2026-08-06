/** Normalize FastAPI / Angular HttpErrorResponse detail into a short user message. */
export function httpErrorDetail(err: unknown, fallback = 'Request failed'): string {
  const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    if (typeof first === 'string') {
      return first;
    }
    if (first && typeof first === 'object' && 'msg' in first) {
      return String((first as { msg: unknown }).msg);
    }
  }
  return fallback;
}
