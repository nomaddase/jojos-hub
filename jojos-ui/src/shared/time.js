export function parseIsoToMs(iso) {
  if (!iso) return null
  const ms = Date.parse(iso)
  return Number.isNaN(ms) ? null : ms
}

export function secondsSince(iso, nowMs = Date.now()) {
  const startMs = parseIsoToMs(iso)
  if (!startMs) return 0
  return Math.max(0, Math.floor((nowMs - startMs) / 1000))
}

export function formatTimer(sec = 0) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function formatEta(seconds = 0) {
  if (!seconds || seconds <= 0) return 'без очереди'
  const min = Math.max(1, Math.ceil(seconds / 60))
  return `≈ ${min} мин`
}
