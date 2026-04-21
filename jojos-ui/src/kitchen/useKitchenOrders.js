import { useCallback, useEffect, useRef, useState } from 'react'
import { getKitchenEventsUrl, getKitchenOrders } from '../api'
import { useEventStream } from '../shared/useEventStream'
import { mergeOrders } from './kitchenTiming'

export function useKitchenOrders() {
  const [orders, setOrders] = useState([])
  const [eventsHealthy, setEventsHealthy] = useState(true)
  const revisionRef = useRef(null)
  const lastEventAtRef = useRef(Date.now())
  const disconnectedTimerRef = useRef(null)

  const hydrateFromPayload = useCallback((payload) => {
    const next = Array.isArray(payload) ? payload : []
    setOrders((prev) => mergeOrders(prev, next))
  }, [])

  const loadFallback = useCallback(async () => {
    const data = await getKitchenOrders()
    hydrateFromPayload(data)
  }, [hydrateFromPayload])

  const markHealthy = useCallback(() => {
    lastEventAtRef.current = Date.now()
    setEventsHealthy(true)
    if (disconnectedTimerRef.current) {
      clearTimeout(disconnectedTimerRef.current)
      disconnectedTimerRef.current = null
    }
  }, [])

  const scheduleUnhealthyCheck = useCallback(() => {
    if (disconnectedTimerRef.current) return
    disconnectedTimerRef.current = setTimeout(() => {
      disconnectedTimerRef.current = null
      if (Date.now() - lastEventAtRef.current >= 15000) {
        setEventsHealthy(false)
      }
    }, 15000)
  }, [])

  useEventStream({
    url: getKitchenEventsUrl(),
    eventName: 'kitchen_update',
    onMessage: ({ revision, payload }) => {
      markHealthy()
      if (revision && revision === revisionRef.current) return
      revisionRef.current = revision
      hydrateFromPayload(payload)
    },
    onHeartbeat: markHealthy,
    onOpen: markHealthy,
    onError: scheduleUnhealthyCheck
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

  useEffect(() => () => {
    if (disconnectedTimerRef.current) clearTimeout(disconnectedTimerRef.current)
  }, [])

  return { orders, eventsHealthy, reload: loadFallback }
}
