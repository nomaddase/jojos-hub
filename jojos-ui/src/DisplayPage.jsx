import { useEffect, useState } from 'react'
import { getDisplayOrders } from './api'

const MAX_ZONE_CARDS = 12

export default function DisplayPage() {
  const [data, setData] = useState({
    accepted_orders: [],
    ready_orders: []
  })

  async function load() {
    try {
      const json = await getDisplayOrders()
      setData(json || { accepted_orders: [], ready_orders: [] })
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 2000)
    return () => clearInterval(timer)
  }, [])

  const acceptedVisible = data.accepted_orders.slice(0, MAX_ZONE_CARDS)
  const acceptedOverflow = Math.max(0, data.accepted_orders.length - MAX_ZONE_CARDS)
  const readyVisible = data.ready_orders.slice(0, MAX_ZONE_CARDS)
  const readyOverflow = Math.max(0, data.ready_orders.length - MAX_ZONE_CARDS)

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

        {data.accepted_orders.length === 0 ? (
          <div className="display-zone-empty">Нет активных принятых заказов</div>
        ) : (
          <div className="display-order-grid">
            {acceptedVisible.map(order => (
              <div className="display-order-card accepted" key={order.id}>
                <div className="display-order-number">#{order.number}</div>
                <div className="display-order-status">Ожидает</div>
              </div>
            ))}
            {acceptedOverflow > 0 && (
              <div className="display-order-card overflow" key="accepted-overflow">
                <div className="display-order-number">+{acceptedOverflow}</div>
                <div className="display-order-status">других заказов</div>
              </div>
            )}
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

        {data.ready_orders.length === 0 ? (
          <div className="display-zone-empty ready">Готовых заказов пока нет</div>
        ) : (
          <div className="display-order-grid">
            {readyVisible.map(order => (
              <div className="display-order-card ready" key={order.id}>
                <div className="display-order-number">#{order.number}</div>
                <div className="display-order-status">Готов</div>
              </div>
            ))}
            {readyOverflow > 0 && (
              <div className="display-order-card overflow" key="ready-overflow">
                <div className="display-order-number">+{readyOverflow}</div>
                <div className="display-order-status">ожидают выдачу</div>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
