import { secondsSince } from '../shared/time'

export function getTiming(order, nowMs, warningRatio = 0.7) {
  const elapsedSeconds = secondsSince(order.accepted_at || order.created_at, nowMs)
  const targetPrepSeconds = Number(order.target_prep_seconds || 120)
  const progressRatio = targetPrepSeconds > 0 ? elapsedSeconds / targetPrepSeconds : 0

  let timeState = 'normal'
  if (progressRatio >= 1) timeState = 'overdue'
  else if (progressRatio >= warningRatio) timeState = 'warning'

  return { elapsedSeconds, targetPrepSeconds, progressRatio, timeState }
}

export function buildOrderSignature(order) {
  return JSON.stringify({
    id: order.id,
    number: order.number,
    status: order.status,
    created_at: order.created_at,
    accepted_at: order.accepted_at,
    ready_at: order.ready_at,
    cancelled_at: order.cancelled_at,
    total: order.total,
    target_prep_seconds: order.target_prep_seconds,
    service_mode: order.service_mode,
    items: (order.items || []).map((item) => ({
      item_id: item.item_id,
      name: item.name,
      display_name: item.display_name,
      qty: item.qty,
      modifier_lines: item.modifier_lines || []
    }))
  })
}

export function mergeOrders(prevOrders, nextOrdersRaw) {
  const prevMap = new Map(prevOrders.map((order) => [order.id, order]))
  const nextOrders = nextOrdersRaw.map((order) => {
    const normalized = {
      ...order,
      service_mode: order.service_mode || 'dine_in',
      items: Array.isArray(order.items) ? order.items : [],
      __signature: buildOrderSignature(order)
    }
    const prev = prevMap.get(normalized.id)
    return prev && prev.__signature === normalized.__signature ? prev : normalized
  })

  nextOrders.sort((a, b) => Date.parse(a.created_at || 0) - Date.parse(b.created_at || 0))

  if (prevOrders.length === nextOrders.length && prevOrders.every((order, idx) => order === nextOrders[idx])) {
    return prevOrders
  }

  return nextOrders
}
