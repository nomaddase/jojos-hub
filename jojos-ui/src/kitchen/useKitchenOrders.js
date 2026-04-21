import { useCallback, useEffect, useRef, useState } from 'react'
import { getKitchenEventsUrl, getKitchenOrders } from '../api'
import { useEventStream } from '../shared/useEventStream'
import { mergeOrders } from './kitchenTiming'

export function useKitchenOrders() {
  const [orders, setOrders] = useState([])
  const [eventsHealthy, setEventsHealthy] = useState(true)
  const revisionRef = useRef(null)

  const hydrateFromPayload = useCallback((payload) => {
    const next = Array.isArray(payload) ? payload : []
    setOrders((prev) => mergeOrders(prev, next))
  }, [])

  const loadFallback = useCallback(async () => {
    const data = await getKitchenOrders()
    hydrateFromPayload(data)
  }, [hydrateFromPayload])

  useEventStream({
    url: getKitchenEventsUrl(),
    eventName: 'kitchen_update',
    onMessage: ({ revision, payload }) => {
      setEventsHealthy(true)
      if (revision && revision === revisionRef.current) return
      revisionRef.current = revision
      hydrateFromPayload(payload)
    },
    onError: () => setEventsHealthy(false)
  })

  useEffect(() => {
    loadFallback().catch(console.error)
  }, [loadFallback])

  useEffect(() => {
    if (eventsHealthy) return undefined
    const timer = setInterval(() => {
      loadFallback().catch(console.error)
    }, 3000)
    return () => clearInterval(timer)
  }, [eventsHealthy, loadFallback])

  return { orders, eventsHealthy, reload: loadFallback }
}
