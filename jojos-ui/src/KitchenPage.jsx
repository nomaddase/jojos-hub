import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { getKitchenOrders, markReady, markCancel } from './api'

const POLL_MS = 5000
const KITCHEN_BUILD = 'kitchen-prod-v4'

function parseIsoToMs(iso) {
  if (!iso) return null
  const ms = Date.parse(iso)
  return Number.isNaN(ms) ? null : ms
}

function secondsSince(iso, nowMs) {
  const startMs = parseIsoToMs(iso)
  if (!startMs) return 0
  return Math.max(0, Math.floor((nowMs - startMs) / 1000))
}

function formatTime(sec = 0) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function getTiming(order, nowMs) {
  const elapsedSeconds = secondsSince(order.created_at, nowMs)
  const targetPrepSeconds = Number(order.target_prep_seconds || 120)
  const progressRatio = targetPrepSeconds > 0 ? elapsedSeconds / targetPrepSeconds : 0

  let timeState = 'normal'
  if (progressRatio >= 1) timeState = 'overdue'
  else if (progressRatio >= 0.7) timeState = 'warning'

  return {
    elapsedSeconds,
    targetPrepSeconds,
    progressRatio,
    timeState
  }
}

function buildOrderSignature(order) {
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
    contains_sandwich: order.contains_sandwich,
    service_mode: order.service_mode,
    actual_prep_seconds: order.actual_prep_seconds,
    is_overdue: order.is_overdue,
    items: (order.items || []).map(item => ({
      item_id: item.item_id,
      name: item.name,
      display_name: item.display_name,
      qty: item.qty,
      price: item.price,
      modifier_lines: item.modifier_lines || []
    }))
  })
}

function normalizeOrder(order) {
  return {
    ...order,
    service_mode: order.service_mode || 'dine_in',
    items: Array.isArray(order.items) ? order.items : [],
    __signature: buildOrderSignature(order)
  }
}

function mergeOrders(prevOrders, nextOrdersRaw) {
  const prevMap = new Map(prevOrders.map(order => [order.id, order]))
  const nextOrders = []

  for (const raw of nextOrdersRaw) {
    const normalized = normalizeOrder(raw)
    const prev = prevMap.get(normalized.id)

    if (prev && prev.__signature === normalized.__signature) {
      nextOrders.push(prev)
    } else {
      nextOrders.push(normalized)
    }
  }

  nextOrders.sort((a, b) => {
    const aMs = parseIsoToMs(a.created_at) || 0
    const bMs = parseIsoToMs(b.created_at) || 0
    return aMs - bMs
  })

  if (prevOrders.length !== nextOrders.length) {
    return nextOrders
  }

  let changed = false
  for (let i = 0; i < prevOrders.length; i += 1) {
    if (prevOrders[i] !== nextOrders[i]) {
      changed = true
      break
    }
  }

  return changed ? nextOrders : prevOrders
}

const KitchenOrderCard = memo(function KitchenOrderCard({ order, onOpen }) {
  const rootRef = useRef(null)
  const timerRef = useRef(null)
  const barRef = useRef(null)
  const stateRef = useRef(null)

  const initialTiming = useMemo(() => getTiming(order, Date.now()), [order])

  useEffect(() => {
    function applyTiming() {
      const timing = getTiming(order, Date.now())

      if (timerRef.current) {
        timerRef.current.textContent = formatTime(timing.elapsedSeconds)
      }

      if (barRef.current) {
        barRef.current.style.width = `${Math.min(timing.progressRatio * 100, 100)}%`
        barRef.current.className = `tile-bar ${timing.timeState}`
      }

      if (stateRef.current) {
        stateRef.current.textContent = timing.timeState === 'overdue' ? 'Просрочен' : 'В работе'
      }

      if (rootRef.current) {
        rootRef.current.className =
          `kitchen-tile ${timing.timeState} ${order.service_mode === 'takeaway' ? 'takeaway' : ''}`
      }
    }

    applyTiming()
    const timer = setInterval(applyTiming, 1000)
    return () => clearInterval(timer)
  }, [order])

  return (
    <div
      ref={rootRef}
      className={`kitchen-tile ${initialTiming.timeState} ${order.service_mode === 'takeaway' ? 'takeaway' : ''}`}
      onClick={() => onOpen(order)}
    >
      <div className="tile-top">
        <div>
          <div className="tile-label">Заказ</div>
          <div className="order-number">#{order.number}</div>
        </div>

        <div className="order-timer-block">
          <div className="tile-label">Ожидание</div>
          <div ref={timerRef} className="order-timer">
            {formatTime(initialTiming.elapsedSeconds)}
          </div>
        </div>
      </div>

      <div className="tile-badges">
        <div className={`kitchen-badge service ${order.service_mode === 'takeaway' ? 'takeaway' : ''}`}>
          {order.service_mode === 'takeaway' ? 'С собой' : 'В зале'}
        </div>
      </div>

      <div className="tile-bar-wrap">
        <div
          ref={barRef}
          className={`tile-bar ${initialTiming.timeState}`}
          style={{ width: `${Math.min(initialTiming.progressRatio * 100, 100)}%` }}
        />
      </div>

      <div className="tile-meta">
        <span>Цель: {formatTime(initialTiming.targetPrepSeconds)}</span>
        <span ref={stateRef}>{initialTiming.timeState === 'overdue' ? 'Просрочен' : 'В работе'}</span>
      </div>

      <div className="tile-items">
        {(order.items || []).slice(0, 3).map((item, idx) => (
          <div key={idx} className="tile-item">
            <div className="tile-item-main">
              {item.qty} × {item.display_name || item.name}
            </div>

            {Array.isArray(item.modifier_lines) && item.modifier_lines.length > 0 && (
              <div className="tile-item-mods">
                {item.modifier_lines.map((line, modIdx) => (
                  <div key={modIdx} className="tile-item-mod">
                    {line}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
})

const KitchenSidePanel = memo(function KitchenSidePanel({
  order,
  onClose,
  onReady,
  onBeginHold,
  onEndHold
}) {
  const elapsedRef = useRef(null)
  const stateRef = useRef(null)

  const initialTiming = useMemo(() => getTiming(order, Date.now()), [order])

  useEffect(() => {
    function applyTiming() {
      const timing = getTiming(order, Date.now())

      if (elapsedRef.current) {
        elapsedRef.current.textContent = formatTime(timing.elapsedSeconds)
      }

      if (stateRef.current) {
        stateRef.current.textContent =
          timing.timeState === 'overdue'
            ? 'Просрочен'
            : timing.timeState === 'warning'
            ? 'Скоро просрочка'
            : 'В норме'
      }
    }

    applyTiming()
    const timer = setInterval(applyTiming, 1000)
    return () => clearInterval(timer)
  }, [order])

  return (
    <div className="kitchen-side-overlay" onClick={onClose}>
      <aside className="kitchen-side-panel" onClick={(e) => e.stopPropagation()}>
        <div className="kitchen-side-head">
          <div>
            <div className="eyebrow">Подтверждение</div>
            <div className="kitchen-side-title">Заказ #{order.number}</div>
            <div className="kitchen-side-subtitle">
              {order.service_mode === 'takeaway' ? 'Заказ с собой' : 'Заказ в зале'}
            </div>
          </div>

          <div className={`kitchen-badge service ${order.service_mode === 'takeaway' ? 'takeaway' : ''}`}>
            {order.service_mode === 'takeaway' ? 'С собой' : 'В зале'}
          </div>
        </div>

        <div className="kitchen-side-scroll">
          <div className="kitchen-side-block">
            <div className="kitchen-side-block-title">Тайминг</div>

            <div className="kitchen-side-row">
              <span>Прошло</span>
              <b ref={elapsedRef}>{formatTime(initialTiming.elapsedSeconds)}</b>
            </div>

            <div className="kitchen-side-row" style={{ marginTop: '10px' }}>
              <span>Норма</span>
              <b>{formatTime(initialTiming.targetPrepSeconds)}</b>
            </div>

            <div className="kitchen-side-row" style={{ marginTop: '10px' }}>
              <span>Статус</span>
              <b ref={stateRef}>
                {initialTiming.timeState === 'overdue'
                  ? 'Просрочен'
                  : initialTiming.timeState === 'warning'
                  ? 'Скоро просрочка'
                  : 'В норме'}
              </b>
            </div>
          </div>

          <div className="kitchen-side-block">
            <div className="kitchen-side-block-title">Позиции</div>

            <div className="kitchen-side-items">
              {(order.items || []).map((item, idx) => (
                <div key={idx} className="kitchen-side-item">
                  <div className="kitchen-side-item-title">
                    {item.qty} × {item.display_name || item.name}
                  </div>

                  {Array.isArray(item.modifier_lines) && item.modifier_lines.length > 0 && (
                    <div className="kitchen-side-item-mods">
                      {item.modifier_lines.map((line, modIdx) => (
                        <div key={modIdx} className="kitchen-side-item-mod">
                          {line}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="kitchen-side-actions">
          <button className="action-btn ready" onClick={onReady}>
            Готово
          </button>

          <button
            className="action-btn cancel"
            onPointerDown={onBeginHold}
            onPointerUp={onEndHold}
            onPointerCancel={onEndHold}
            onPointerLeave={onEndHold}
          >
            Удерживать
          </button>

          <button className="action-btn close" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </aside>
    </div>
  )
})

export default function KitchenPage() {
  const [orders, setOrders] = useState([])
  const [selectedOrder, setSelectedOrder] = useState(null)
  const selectedOrderRef = useRef(null)
  const holdTimerRef = useRef(null)
  const holdTriggeredRef = useRef(false)

  useEffect(() => {
    selectedOrderRef.current = selectedOrder
  }, [selectedOrder])

  async function load(force = false) {
    if (!force && selectedOrderRef.current) {
      return
    }

    try {
      const data = await getKitchenOrders()
      const nextRaw = Array.isArray(data) ? data : []

      setOrders(prev => mergeOrders(prev, nextRaw))
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    load(true)
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      load(false)
    }, POLL_MS)

    return () => clearInterval(timer)
  }, [])

  function clearHold() {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current)
      holdTimerRef.current = null
    }
  }

  function beginHold(orderId, e) {
    e.preventDefault()
    e.stopPropagation()

    holdTriggeredRef.current = false
    clearHold()

    holdTimerRef.current = setTimeout(async () => {
      holdTriggeredRef.current = true
      try {
        await markCancel(orderId)
        setSelectedOrder(null)
        await load(true)
      } catch (err) {
        console.error(err)
      } finally {
        clearHold()
      }
    }, 900)
  }

  function endHold(e) {
    e.preventDefault()
    e.stopPropagation()
    if (!holdTriggeredRef.current) clearHold()
  }

  return (
    <div className="screen kitchen-screen">
      <div className="k-header">
        <div>
          <div className="eyebrow">JoJo Core · {KITCHEN_BUILD}</div>
          <h1>Кухня</h1>
          <div className="screen-sub">Активные заказы в работе</div>
        </div>

        <div className="summary-chip">
          <span>Заказов</span>
          <b>{orders.length}</b>
        </div>
      </div>

      <div className="kitchen-grid">
        {orders.map(order => (
          <KitchenOrderCard
            key={order.id}
            order={order}
            onOpen={(snapshot) => setSelectedOrder(snapshot)}
          />
        ))}
      </div>

      {selectedOrder && (
        <KitchenSidePanel
          order={selectedOrder}
          onClose={async () => {
            setSelectedOrder(null)
            await load(true)
          }}
          onReady={async () => {
            await markReady(selectedOrder.id)
            setSelectedOrder(null)
            await load(true)
          }}
          onBeginHold={(e) => beginHold(selectedOrder.id, e)}
          onEndHold={endHold}
        />
      )}
    </div>
  )
}
