import { useEffect, useMemo, useState } from 'react'
import { getDisplayOrders } from './api'

const POLL_MS = 2000
const PAGE_MS = 9000

function mergeOrderLists(prev, next) {
  if (!Array.isArray(next)) return prev
  if (prev.length !== next.length) return next

  for (let i = 0; i < next.length; i += 1) {
    const a = prev[i]
    const b = next[i]
    if (!a || !b) return next
    if (a.id !== b.id || a.status !== b.status || a.wait_seconds !== b.wait_seconds || a.number !== b.number) {
      return next
    }
  }

  return prev
}

function chunkOrders(orders, perPage) {
  if (!orders.length) return [[]]
  const pages = []
  for (let i = 0; i < orders.length; i += perPage) {
    pages.push(orders.slice(i, i + perPage))
  }
  return pages
}

function getGridConfig(totalCount) {
  if (totalCount <= 8) return { cols: 2, rows: 2, density: 'cozy' }
  if (totalCount <= 18) return { cols: 3, rows: 3, density: 'dense' }
  return { cols: 3, rows: 4, density: 'ultra' }
}

export default function DisplayPage() {
  const [data, setData] = useState({ accepted_orders: [], ready_orders: [] })
  const [page, setPage] = useState(0)

  useEffect(() => {
    async function load() {
      try {
        const json = await getDisplayOrders()
        setData(prev => {
          const nextData = json || { accepted_orders: [], ready_orders: [] }
          return {
            ...nextData,
            accepted_orders: mergeOrderLists(prev.accepted_orders, nextData.accepted_orders),
            ready_orders: mergeOrderLists(prev.ready_orders, nextData.ready_orders)
          }
        })
      } catch (e) {
        console.error(e)
      }
    }

    load()
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [])

  const totalCards = data.accepted_orders.length + data.ready_orders.length
  const gridConfig = getGridConfig(totalCards)
  const cardsPerZonePage = gridConfig.cols * gridConfig.rows

  const acceptedPages = useMemo(
    () => chunkOrders(data.accepted_orders, cardsPerZonePage),
    [cardsPerZonePage, data.accepted_orders]
  )
  const readyPages = useMemo(
    () => chunkOrders(data.ready_orders, cardsPerZonePage),
    [cardsPerZonePage, data.ready_orders]
  )

  const pageCount = Math.max(acceptedPages.length, readyPages.length)

  useEffect(() => {
    setPage(prev => {
      if (pageCount <= 1) return 0
      return Math.min(prev, pageCount - 1)
    })
  }, [pageCount])

  useEffect(() => {
    if (pageCount <= 1) return undefined

    const timer = setInterval(() => {
      setPage(prev => (prev + 1) % pageCount)
    }, PAGE_MS)

    return () => clearInterval(timer)
  }, [pageCount])

  const acceptedVisible = acceptedPages[Math.min(page, acceptedPages.length - 1)] || []
  const readyVisible = readyPages[Math.min(page, readyPages.length - 1)] || []

  return (
    <div className="screen display-board">
      <section className="display-zone accepted-zone">
        <div className="display-zone-head">
          <div>
            <div className="eyebrow">JoJo’s</div>
            <div className="display-zone-title">Принятые заказы</div>
          </div>
          <div className="display-zone-count">{data.accepted_orders.length}</div>
        </div>

        {acceptedVisible.length === 0 ? (
          <div className="display-zone-empty">Нет активных принятых заказов</div>
        ) : (
          <div
            className={`display-order-grid ${gridConfig.density} cols-${gridConfig.cols}`}
            style={{ '--display-grid-rows': gridConfig.rows }}
          >
            {acceptedVisible.map(order => (
              <div className="display-order-card accepted" key={order.id}>
                <div className="display-order-number">#{order.number}</div>
                <div className="display-order-status">Ожидает · {Math.floor((order.wait_seconds || 0) / 60)} мин</div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="display-zone ready-zone">
        <div className="display-zone-head">
          <div>
            <div className="eyebrow">JoJo’s</div>
            <div className="display-zone-title">Готовые заказы</div>
          </div>
          <div className="display-zone-count">{data.ready_orders.length}</div>
        </div>

        {readyVisible.length === 0 ? (
          <div className="display-zone-empty ready">Готовых заказов пока нет</div>
        ) : (
          <div
            className={`display-order-grid ${gridConfig.density} cols-${gridConfig.cols}`}
            style={{ '--display-grid-rows': gridConfig.rows }}
          >
            {readyVisible.map(order => (
              <div className="display-order-card ready" key={order.id}>
                <div className="display-order-number">#{order.number}</div>
                <div className="display-order-status">Готов · {Math.floor((order.wait_seconds || 0) / 60)} мин</div>
              </div>
            ))}
          </div>
        )}

        {pageCount > 1 && (
          <div className="display-page-indicator">
            Страница {page + 1} / {pageCount}
          </div>
        )}
      </section>
    </div>
  )
}
