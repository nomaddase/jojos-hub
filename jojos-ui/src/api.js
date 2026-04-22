const API = ''

async function parse(res) {
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json()
}

export async function getCatalog() {
  return fetch(`${API}/api/catalog`).then(parse)
}

export async function getKitchenOrders() {
  return fetch(`${API}/api/kitchen/orders`).then(parse)
}

export async function getDisplayOrders() {
  return fetch(`${API}/api/display/orders`).then(parse)
}

export async function getOrders() {
  return fetch(`${API}/api/orders`).then(parse)
}

export async function getSettings() {
  return fetch(`${API}/api/settings`).then(parse)
}

export async function getCurrentEta() {
  return fetch(`${API}/api/orders/eta/current`).then(parse)
}

export async function previewEta(payload) {
  return fetch(`${API}/api/orders/eta/preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  }).then(parse)
}

export async function markReady(orderId) {
  return fetch(`${API}/api/orders/${orderId}/ready`, {
    method: 'POST'
  }).then(parse)
}

export async function markCancel(orderId) {
  return fetch(`${API}/api/orders/${orderId}/cancel`, {
    method: 'POST'
  }).then(parse)
}

export async function createOrder(payload) {
  return fetch(`${API}/api/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  }).then(parse)
}
