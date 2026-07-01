export function getApiErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const candidate = error as {
      data?: { detail?: string }
    }
    if (candidate.data?.detail) return candidate.data.detail
  }
  return '目前無法連線到知識服務，請稍後再試。'
}
