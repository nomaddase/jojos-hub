export function chunkOrders(orders, perPage) {
  if (!orders.length) return [[]]
  const pages = []
  for (let i = 0; i < orders.length; i += perPage) {
    pages.push(orders.slice(i, i + perPage))
  }
  return pages
}

export function getGridConfig(totalCount) {
  if (totalCount <= 8) return { cols: 2, rows: 2, density: 'cozy' }
  if (totalCount <= 18) return { cols: 3, rows: 3, density: 'dense' }
  return { cols: 3, rows: 4, density: 'ultra' }
}
