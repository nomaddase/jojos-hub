import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getDisplayEventsUrl, getDisplayOrders } from '../api'
import { useEventStream } from '../shared/useEventStream'
import { chunkOrders, getGridConfig } from './displayLayout'

const PAGE_MS = 9000

export function useDisplayBoard() {
  const [data, setData] = useState({ accepted_orders: [], ready_orders: [] })
  const [page, setPage] = useState(0)
  const [eventsHealthy, setEventsHealthy] = useState(true)
  const revisionRef = useRef(null)

  const syncData = useCallback((payload) => {
    const next = payload || { accepted_orders: [], ready_orders: [] }
    setData(next)
  }, [])

  const loadFallback = useCallback(async () => {
    const payload = await getDisplayOrders()
    syncData(payload)
  }, [syncData])

  useEventStream({
    url: getDisplayEventsUrl(),
    eventName: 'display_update',
    onMessage: ({ revision, payload }) => {
      setEventsHealthy(true)
      if (revision && revision === revisionRef.current) return
      revisionRef.current = revision
      syncData(payload)
    },
    onError: () => setEventsHealthy(false)
  })

  useEffect(() => {
    loadFallback().catch(console.error)
  }, [loadFallback])

  useEffect(() => {
    if (eventsHealthy) return undefined
    const timer = setInterval(() => loadFallback().catch(console.error), 3000)
    return () => clearInterval(timer)
  }, [eventsHealthy, loadFallback])

  const totalCards = data.accepted_orders.length + data.ready_orders.length
  const gridConfig = getGridConfig(totalCards)
  const perPage = gridConfig.cols * gridConfig.rows

  const acceptedPages = useMemo(() => chunkOrders(data.accepted_orders, perPage), [data.accepted_orders, perPage])
  const readyPages = useMemo(() => chunkOrders(data.ready_orders, perPage), [data.ready_orders, perPage])
  const pageCount = Math.max(acceptedPages.length, readyPages.length)

  useEffect(() => setPage((prev) => (pageCount <= 1 ? 0 : Math.min(prev, pageCount - 1))), [pageCount])
  useEffect(() => {
    if (pageCount <= 1) return undefined
    const timer = setInterval(() => setPage((prev) => (prev + 1) % pageCount), PAGE_MS)
    return () => clearInterval(timer)
  }, [pageCount])

  return {
    data,
    gridConfig,
    page,
    pageCount,
    acceptedVisible: acceptedPages[Math.min(page, acceptedPages.length - 1)] || [],
    readyVisible: readyPages[Math.min(page, readyPages.length - 1)] || []
  }
}
