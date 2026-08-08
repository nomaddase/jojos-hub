export function chunkOrders(orders, perPage) {
  if (!orders.length) return [[]]
  const pages = []
  for (let i = 0; i < orders.length; i += perPage) {
    pages.push(orders.slice(i, i + perPage))
  }
  return pages
}

// The public order board is designed for a 1920x1080 landscape monitor.
// Each side can show up to 16 order numbers before paging, so accepted and
// ready queues together can expose up to 32 orders at once.
export function getGridConfig(totalCount) {
  if (totalCount <= 8) return { cols: 4, rows: 2, density: 'cozy' }
  if (totalCount <= 20) return { cols: 4, rows: 3, density: 'dense' }
  return { cols: 4, rows: 4, density: 'ultra' }
}
