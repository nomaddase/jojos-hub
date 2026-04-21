import { useEffect, useRef } from 'react'

export function useEventStream({ url, eventName, onMessage, onError }) {
  const onMessageRef = useRef(onMessage)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onMessageRef.current = onMessage
    onErrorRef.current = onError
  }, [onError, onMessage])

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

    source.addEventListener(eventName, listener)
    source.onerror = (error) => {
      onErrorRef.current?.(error)
      source.close()
    }

    return () => {
      source.removeEventListener(eventName, listener)
      source.close()
    }
  }, [eventName, url])
}
