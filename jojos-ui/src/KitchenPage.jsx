import { useEffect, useRef, useState } from 'react'
import { getSettings, markCancel, markReady } from './api'
import { KitchenOrderCard } from './kitchen/KitchenOrderCard'
import { KitchenSidePanel } from './kitchen/KitchenSidePanel'
import { useKitchenOrders } from './kitchen/useKitchenOrders'

const KITCHEN_BUILD = import.meta.env.VITE_BUILD_MARKER || 'kitchen-prod-final'

export default function KitchenPage() {
  const { orders, reload } = useKitchenOrders()
  const [selectedOrder, setSelectedOrder] = useState(null)
  const [warningRatio, setWarningRatio] = useState(0.7)
  const [actionPending, setActionPending] = useState(false)
  const holdTimerRef = useRef(null)
  const holdTriggeredRef = useRef(false)

  useEffect(() => {
    getSettings().then((payload) => {
      const ratio = Number(payload?.effective?.kitchen?.warning_ratio ?? 0.7)
      setWarningRatio(Number.isFinite(ratio) ? Math.min(0.95, Math.max(0.1, ratio)) : 0.7)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedOrder) return
    const next = orders.find((order) => order.id === selectedOrder.id)
    if (next) setSelectedOrder(next)
  }, [orders, selectedOrder])

  function clearHold() {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current)
      holdTimerRef.current = null
    }
  }

  function beginHold(orderId, e) {
    e.preventDefault()
    holdTriggeredRef.current = false
    clearHold()
    holdTimerRef.current = setTimeout(async () => {
      holdTriggeredRef.current = true
      setActionPending(true)
      try {
        await markCancel(orderId)
        setSelectedOrder(null)
        await reload()
      } finally {
        setActionPending(false)
        clearHold()
      }
    }, 900)
  }

  function endHold(e) {
    e.preventDefault()
    if (!holdTriggeredRef.current) clearHold()
  }

  return (
    <div className="screen kitchen-screen">
      <div className="k-header">
        <div>
          <div className="eyebrow">JoJo Core · {KITCHEN_BUILD}</div>
          <h1>Кухня</h1>
          <div className="screen-sub">Событийное обновление без визуальных перезагрузок</div>
        </div>
        <div className="summary-chip"><span>Заказов</span><b>{orders.length}</b></div>
      </div>

      <div className="kitchen-grid">
        {orders.map((order) => (
          <KitchenOrderCard key={order.id} order={order} warningRatio={warningRatio} onOpen={setSelectedOrder} />
        ))}
      </div>

      {selectedOrder && (
        <KitchenSidePanel
          order={selectedOrder}
          warningRatio={warningRatio}
          onClose={() => setSelectedOrder(null)}
          onReady={async () => {
            if (actionPending) return
            setActionPending(true)
            try {
              await markReady(selectedOrder.id)
              setSelectedOrder(null)
              await reload()
            } finally {
              setActionPending(false)
            }
          }}
          onBeginHold={(e) => beginHold(selectedOrder.id, e)}
          onEndHold={endHold}
        />
      )}
    </div>
  )
}
