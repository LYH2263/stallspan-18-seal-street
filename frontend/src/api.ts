export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text || res.statusText
    try {
      const j = JSON.parse(text)
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* 非 JSON 错误体，原样透出 */ }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
