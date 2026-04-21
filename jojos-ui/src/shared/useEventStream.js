import { useEffect, useRef } from 'react'

export function useEventStream({ url, eventName, onMessage, onError, onHeartbeat, onOpen }) {
  const onMessageRef = useRef(onMessage)
  const onErrorRef = useRef(onError)
  const onHeartbeatRef = useRef(onHeartbeat)
  const onOpenRef = useRef(onOpen)

  useEffect(() => {
    onMessageRef.current = onMessage
    onErrorRef.current = onError
    onHeartbeatRef.current = onHeartbeat
    onOpenRef.current = onOpen
  }, [onError, onHeartbeat, onMessage, onOpen])

  useEffect(() => {
    if (!url) return undefined

    const source = new EventSource(url)
    const listener = (event) => {
      try {
        const parsed = JSON.parse(event.data)
        onMessageRef.current?.(parsed)
      } catch (e) {
        console.error(e)
      }
    }
    const heartbeatListener = () => onHeartbeatRef.current?.()
    const openListener = () => onOpenRef.current?.()

    source.addEventListener(eventName, listener)
    source.addEventListener('heartbeat', heartbeatListener)
    source.addEventListener('open', openListener)
    source.onopen = openListener
    source.onerror = (error) => {
      onErrorRef.current?.(error)
    }

    return () => {
      source.removeEventListener(eventName, listener)
      source.removeEventListener('heartbeat', heartbeatListener)
      source.removeEventListener('open', openListener)
      source.close()
    }
  }, [eventName, url])
}
