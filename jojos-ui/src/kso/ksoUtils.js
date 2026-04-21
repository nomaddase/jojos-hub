import { formatEta } from '../shared/time'

export function formatPrice(value) {
  return `${Number(value || 0).toLocaleString('ru-RU')} ₸`
}

export function getLabel(lang) {
  const key = String(lang || '').toLowerCase()
  if (key === 'ru') return 'RU'
  if (key === 'kz' || key === 'kaz') return 'KAZ'
  if (key === 'en') return 'EN'
  return String(lang).toUpperCase()
}

export { formatEta }
