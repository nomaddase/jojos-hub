import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createOrder, getCatalog, getCurrentEta, getSettings, previewEta } from './api'
import { buildEffectiveRuntimeSettings, getRuntimeDefaults } from './runtimeSettings'

const runtimeDefaults = getRuntimeDefaults()
const DEFAULT_IDLE_TIMEOUT_MS = runtimeDefaults.idleTimeoutSeconds * 1000
const DEFAULT_LANGUAGES = runtimeDefaults.languages
const DEFAULT_SERVICE_MODES = runtimeDefaults.serviceModes.enabled


function formatPrice(value) {
  return `${Number(value || 0).toLocaleString('ru-RU')} ₸`
}

function formatEta(seconds = 0) {
  if (!seconds || seconds <= 0) return 'без очереди'
  const min = Math.max(1, Math.ceil(seconds / 60))
  return `≈ ${min} мин`
}

function getLabel(lang) {
  const key = String(lang || '').toLowerCase()
  if (key === 'ru') return 'RU'
  if (key === 'kz' || key === 'kaz') return 'KAZ'
  if (key === 'en') return 'EN'
  return String(lang).toUpperCase()
}

export default function KsoPage() {
  const [catalog, setCatalog] = useState({ groups: [] })
  const [languages, setLanguages] = useState(DEFAULT_LANGUAGES)
  const [currentLanguage, setCurrentLanguage] = useState('ru')
  const [idleTimeoutMs, setIdleTimeoutMs] = useState(DEFAULT_IDLE_TIMEOUT_MS)
  const [serviceModes, setServiceModes] = useState(DEFAULT_SERVICE_MODES)

  const [activeGroup, setActiveGroup] = useState('all')
  const [selectedItem, setSelectedItem] = useState(null)
  const [selectedOptions, setSelectedOptions] = useState({})
  const [qty, setQty] = useState(1)
  const [cart, setCart] = useState([])
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [success, setSuccess] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const [started, setStarted] = useState(false)
  const [serviceMode, setServiceMode] = useState(null)

  const [currentEta, setCurrentEta] = useState(null)
  const [orderEta, setOrderEta] = useState(null)

  const idleTimerRef = useRef(null)

  const visibleGroups = useMemo(() => catalog.groups || [], [catalog.groups])

  const resetKsoState = useCallback(() => {
    setActiveGroup('all')
    setSelectedItem(null)
    setSelectedOptions({})
    setQty(1)
    setCart([])
    setCheckoutOpen(false)
    setSuccess(null)
    setStarted(false)
    setServiceMode(null)
  }, [])

  const restartIdleTimer = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current)
    }
    if (!started) return

    idleTimerRef.current = setTimeout(() => {
      resetKsoState()
    }, idleTimeoutMs)
  }, [idleTimeoutMs, resetKsoState, started])

  useEffect(() => {
    let mounted = true

    async function load() {
      try {
        const [catalogData, settingsData, etaData] = await Promise.all([
          getCatalog(),
          getSettings().catch(() => ({ items: [], effective: {} })),
          getCurrentEta().catch(() => null)
        ])

        if (!mounted) return
        setCatalog(catalogData || { groups: [] })

        const runtimeSettings = buildEffectiveRuntimeSettings(settingsData)
        setLanguages(runtimeSettings.languages)
        setServiceModes(runtimeSettings.serviceModes.enabled)
        setIdleTimeoutMs(runtimeSettings.idleTimeoutSeconds * 1000)

        setCurrentLanguage(prev => {
          if (runtimeSettings.languages.includes(prev)) return prev
          return runtimeSettings.defaultLanguage
        })

        if (etaData) setCurrentEta(etaData)
      } catch (e) {
        console.error(e)
      } finally {
        if (mounted) setLoading(false)
      }
    }

    load()
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    async function refreshEta() {
      try {
        const eta = await getCurrentEta()
        setCurrentEta(eta)
      } catch (e) {
        console.error(e)
      }
    }

    refreshEta()
    const timer = setInterval(refreshEta, 5000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    async function loadPreview() {
      if (!cart.length) {
        setOrderEta(null)
        return
      }

      try {
        const data = await previewEta({
          source: 'kso',
          service_mode: serviceMode || 'dine_in',
          items: cart.map(item => ({
            item_id: item.item_id,
            name: item.name,
            qty: item.qty,
            price: item.price,
            options: item.options
          }))
        })
        setOrderEta(data)
      } catch (e) {
        console.error(e)
      }
    }

    loadPreview()
  }, [cart, serviceMode])

  useEffect(() => {
    restartIdleTimer()
    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    }
  }, [restartIdleTimer, selectedItem, checkoutOpen, success, cart, serviceMode])

  useEffect(() => {
    function onAnyActivity() {
      restartIdleTimer()
    }

    window.addEventListener('pointerdown', onAnyActivity)
    window.addEventListener('touchstart', onAnyActivity)
    window.addEventListener('keydown', onAnyActivity)

    return () => {
      window.removeEventListener('pointerdown', onAnyActivity)
      window.removeEventListener('touchstart', onAnyActivity)
      window.removeEventListener('keydown', onAnyActivity)
    }
  }, [restartIdleTimer])

  const visibleCatalog = useMemo(() => {
    if (activeGroup === 'all') return visibleGroups
    return visibleGroups.filter(group => group.id === activeGroup)
  }, [activeGroup, visibleGroups])

  const upsellItems = useMemo(() => {
    if (!cart.length) return []

    const cartIds = new Set(cart.map(x => x.item_id))
    const cartGroups = new Set()

    for (const group of visibleGroups) {
      for (const item of group.items || []) {
        if (cartIds.has(item.id)) cartGroups.add(group.id)
      }
    }

    const result = []
    for (const group of visibleGroups) {
      if (cartGroups.has(group.id)) continue

      for (const item of group.items || []) {
        if (cartIds.has(item.id)) continue
        if ((item.options || []).length > 0) continue
        result.push(item)
      }
    }

    return result.slice(0, 8)
  }, [cart, visibleGroups])

  function openItem(item) {
    setSelectedItem(item)
    setSelectedOptions({})
    setQty(1)
  }

  function closeItem() {
    setSelectedItem(null)
    setSelectedOptions({})
    setQty(1)
  }

  function toggleOption(group, option) {
    setSelectedOptions(prev => {
      const current = prev[group.id] || []

      if (group.mode === 'single') {
        return { ...prev, [group.id]: [option] }
      }

      const exists = current.some(x => x.id === option.id)
      if (exists) {
        return {
          ...prev,
          [group.id]: current.filter(x => x.id !== option.id)
        }
      }

      return {
        ...prev,
        [group.id]: [...current, option]
      }
    })
  }

  function getOptionGroupById(groupId) {
    if (!selectedItem?.options) return null
    return selectedItem.options.find(group => group.id === groupId) || null
  }

  function getEffectiveOptionsForSubmit() {
    const result = []

    Object.entries(selectedOptions).forEach(([groupId, options]) => {
      const group = getOptionGroupById(groupId)
      if (!group || !Array.isArray(options) || options.length === 0) return

      if (group.mode === 'single') {
        options.forEach(opt => {
          result.push({
            group_id: groupId,
            option_id: opt.id,
            name: opt.name,
            price: 0
          })
        })
        return
      }

      options.forEach((opt, idx) => {
        result.push({
          group_id: groupId,
          option_id: opt.id,
          name: opt.name,
          price: idx === 0 ? 0 : Number(opt.price || 0)
        })
      })
    })

    return result
  }

  function getDisplaySelectionLines() {
    return getEffectiveOptionsForSubmit().map(opt => ({
      ...opt,
      line: `+ ${opt.name}${Number(opt.price || 0) > 0 ? ` (+${opt.price} ₸)` : ''}`
    }))
  }

  function getOptionChipPriceLabel(group, option) {
    const current = selectedOptions[group.id] || []
    const idx = current.findIndex(x => x.id === option.id)

    if (group.mode === 'single') return 'включено'
    if (idx === 0) return 'включено'
    return Number(option.price || 0) > 0 ? `+${option.price} ₸` : 'включено'
  }

  function calculateCurrentItemTotal() {
    if (!selectedItem) return 0

    const basePrice = Number(selectedItem.price || 0)
    const optionsTotal = getEffectiveOptionsForSubmit().reduce(
      (sum, opt) => sum + Number(opt.price || 0),
      0
    )

    return (basePrice + optionsTotal) * qty
  }

  function addSimpleItemToCart(item) {
    const basePrice = Number(item.price || 0)
    setCart(prev => [
      ...prev,
      {
        local_id: `${Date.now()}-${Math.floor(Math.random() * 1000000)}`,
        item_id: item.id,
        name: item.name,
        qty: 1,
        price: basePrice,
        options: [],
        option_total: 0,
        lineTotal: basePrice
      }
    ])
  }

  function addToCart() {
    if (!selectedItem) return

    const options = getEffectiveOptionsForSubmit()
    const basePrice = Number(selectedItem.price || 0)
    const optionTotal = options.reduce((sum, opt) => sum + Number(opt.price || 0), 0)
    const lineTotal = (basePrice + optionTotal) * qty

    setCart(prev => [
      ...prev,
      {
        local_id: `${Date.now()}-${Math.floor(Math.random() * 1000000)}`,
        item_id: selectedItem.id,
        name: selectedItem.name,
        qty,
        price: basePrice,
        options,
        option_total: optionTotal,
        lineTotal
      }
    ])

    closeItem()
  }

  function removeCartItem(localId) {
    setCart(prev => prev.filter(item => item.local_id !== localId))
  }

  async function submitOrder() {
    if (!cart.length || submitting || !serviceMode) return

    setSubmitting(true)
    try {
      const payload = {
        source: 'kso',
        service_mode: serviceMode,
        items: cart.map(item => ({
          item_id: item.item_id,
          name: item.name,
          qty: item.qty,
          price: item.price,
          options: item.options
        }))
      }

      const result = await createOrder(payload)
      setSuccess(result)
      setCart([])
      setCheckoutOpen(false)
      setSelectedItem(null)
    } catch (e) {
      console.error(e)
      alert('Не удалось создать заказ')
    } finally {
      setSubmitting(false)
    }
  }

  const cartTotal = cart.reduce((sum, item) => sum + Number(item.lineTotal || 0), 0)
  const etaText = orderEta
    ? `Примерное время готовности: ${formatEta(orderEta.eta_seconds)}`
    : `Текущее ожидание: ${formatEta(currentEta?.queue_remaining_seconds || 0)}`

  if (!started) {
    return (
      <div className="kso-landing">
        <div className="kso-landing-card">
          <div className="kso-landing-logo">
            <div className="kso-landing-mark">J</div>
            <div className="kso-landing-wordmark">JoJo’s</div>
          </div>

          <div className="kso-landing-title">Самостоятельное оформление заказа</div>
          <div className="kso-landing-subtitle">
            Выберите язык и начните заказ на этом терминале
          </div>

          <div className="kso-landing-eta">
            {currentEta?.queue_remaining_seconds > 0
              ? `Сейчас примерное ожидание: ${formatEta(currentEta.queue_remaining_seconds)}`
              : 'Сейчас без очереди'}
          </div>

          <div className="kso-landing-languages">
            {languages.map(lang => (
              <button
                key={lang}
                className={`kso-lang-pill ${currentLanguage === lang ? 'active' : ''}`}
                onClick={() => setCurrentLanguage(lang)}
              >
                {getLabel(lang)}
              </button>
            ))}
          </div>

          <button className="kso-primary-cta" onClick={() => setStarted(true)}>
            Начать заказ
          </button>
        </div>
      </div>
    )
  }

  if (!serviceMode) {
    return (
      <div className="kso-mode-screen">
        <div className="kso-mode-card">
          <div className="kso-mode-top">
            <div className="kso-mode-mark">J</div>
            <div>
              <div className="kso-mode-title">Формат заказа</div>
              <div className="kso-mode-subtitle">Выберите удобный вариант обслуживания</div>
            </div>
          </div>

          <div className="kso-mode-wait">
            Текущее ожидание: {formatEta(currentEta?.queue_remaining_seconds || 0)}
          </div>

          <div className="kso-mode-grid">
            {serviceModes.includes('dine_in') && (
              <button className="kso-mode-option" onClick={() => setServiceMode('dine_in')}>
                <div className="kso-mode-option-title">В зале</div>
                <div className="kso-mode-option-subtitle">Подача для гостей внутри заведения</div>
              </button>
            )}

            {serviceModes.includes('takeaway') && (
              <button className="kso-mode-option takeaway" onClick={() => setServiceMode('takeaway')}>
                <div className="kso-mode-option-title">С собой</div>
                <div className="kso-mode-option-subtitle">Упакуем заказ для выдачи на вынос</div>
              </button>
            )}
          </div>

          <div className="kso-mode-actions">
            <button className="kso-secondary-btn" onClick={resetKsoState}>Назад</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="kso-shell">
      <header className="kso-header">
        <div className="kso-header-left">
          <div className="kso-brand-badge">J</div>
          <div>
            <div className="kso-header-title">JoJo’s KSO</div>
            <div className="kso-header-subtitle">
              {serviceMode === 'takeaway' ? 'Заказ с собой' : 'Заказ в зале'}
            </div>
          </div>
        </div>

        <div className="kso-header-right">
          <div className={`kso-service-badge ${serviceMode === 'takeaway' ? 'takeaway' : ''}`}>
            {serviceMode === 'takeaway' ? 'С собой' : 'В зале'}
          </div>

          <div className="kso-header-langs">
            {languages.map(lang => (
              <button
                key={lang}
                className={`kso-lang-pill compact ${currentLanguage === lang ? 'active' : ''}`}
                onClick={() => setCurrentLanguage(lang)}
              >
                {getLabel(lang)}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="kso-main">
        <aside className="kso-sidebar">
          <button
            className={`kso-group-btn ${activeGroup === 'all' ? 'active' : ''}`}
            onClick={() => setActiveGroup('all')}
          >
            Все продукты
          </button>

          {visibleGroups.map(group => (
            <button
              key={group.id}
              className={`kso-group-btn ${activeGroup === group.id ? 'active' : ''}`}
              onClick={() => setActiveGroup(group.id)}
            >
              {group.name}
            </button>
          ))}
        </aside>

        <main className="kso-content">
          <div className="kso-wait-strip">
            {etaText}
          </div>

          {loading && <div className="kso-empty">Загрузка каталога…</div>}

          {!loading && visibleCatalog.map(group => (
            <section className="kso-section" key={group.id}>
              <div className="kso-section-head">
                <div>
                  <h2>{group.name}</h2>
                  <p>Выберите позицию для добавления в заказ</p>
                </div>
                <div className="kso-section-count">{group.items.length}</div>
              </div>

              <div className="kso-product-grid">
                {group.items.map(item => (
                  <article
                    className="kso-product-card"
                    key={item.id}
                    onClick={() => openItem(item)}
                  >
                    <div className="kso-product-image">JOJO’S</div>

                    <div className="kso-product-body">
                      <div className="kso-product-name">{item.name}</div>
                      <div className="kso-product-description">{item.description}</div>

                      <div className="kso-product-footer">
                        <div>
                          <div className="kso-product-price">{formatPrice(item.price)}</div>
                          <div className="kso-product-prep">~ {formatEta(item.prep_seconds || 0)}</div>
                        </div>

                        <button
                          className="kso-select-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            openItem(item)
                          }}
                        >
                          Выбрать
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}

        </main>
      </div>

      <footer className="kso-bottom-bar">
        <div className="kso-bottom-summary">
          <div className="kso-bottom-label">Корзина</div>
          <div className="kso-bottom-value">{cart.length} позиций · {formatPrice(cartTotal)}</div>
        </div>

        <div className="kso-bottom-extra">
          {etaText}
        </div>

        <div className="kso-bottom-actions">
          <button className="kso-secondary-btn" onClick={resetKsoState}>Сбросить</button>
          <button className="kso-primary-btn" onClick={() => setCheckoutOpen(true)} disabled={cart.length === 0}>
            Оформить заказ
          </button>
        </div>
      </footer>

      {selectedItem && (
        <div className="kso-overlay" onClick={closeItem}>
          <div className="kso-config-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="kso-config-left">
              <div className="kso-config-hero">JOJO’S</div>
              <div className="kso-config-title">{selectedItem.name}</div>
              <div className="kso-config-text">{selectedItem.description}</div>
              <div className="kso-config-eta">
                Примерное приготовление: {formatEta(selectedItem.prep_seconds || 0)}
              </div>
            </div>

            <div className="kso-config-right">
              <div className="kso-config-scroll">
                {(selectedItem.options || []).map(group => (
                  <section className="kso-option-section" key={group.id}>
                    <div className="kso-option-head">
                      <div className="kso-option-title">{group.name}</div>
                      <div className="kso-option-note">
                        {group.mode === 'single' ? '1 выбор бесплатно' : 'первый выбор бесплатно'}
                      </div>
                    </div>

                    <div className="kso-option-grid">
                      {group.items.map(option => {
                        const selected = (selectedOptions[group.id] || []).some(x => x.id === option.id)

                        return (
                          <button
                            key={option.id}
                            className={`kso-option-chip ${selected ? 'selected' : ''}`}
                            onClick={() => toggleOption(group, option)}
                          >
                            <div className="kso-option-chip-name">{option.name}</div>
                            <div className="kso-option-chip-price">
                              {getOptionChipPriceLabel(group, option)}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </section>
                ))}
              </div>

              <div className="kso-config-summary">
                <div className="kso-summary-card">
                  <div className="kso-summary-title">Выбрано</div>
                  <div className="kso-summary-lines">
                    {getDisplaySelectionLines().length > 0 ? (
                      getDisplaySelectionLines().map((opt, idx) => (
                        <div key={idx} className="kso-summary-line">
                          {opt.line}
                        </div>
                      ))
                    ) : (
                      <div className="kso-summary-line muted">Без дополнительных опций</div>
                    )}
                  </div>
                </div>

                <div className="kso-qty-row">
                  <button className="kso-qty-btn" onClick={() => setQty(q => Math.max(1, q - 1))}>−</button>
                  <div className="kso-qty-value">{qty}</div>
                  <button className="kso-qty-btn" onClick={() => setQty(q => q + 1)}>+</button>
                </div>

                <div className="kso-config-actions">
                  <button className="kso-secondary-btn" onClick={closeItem}>Назад</button>
                  <button className="kso-primary-btn" onClick={addToCart}>
                    Добавить · {formatPrice(calculateCurrentItemTotal())}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {checkoutOpen && (
        <div className="kso-drawer-overlay" onClick={() => setCheckoutOpen(false)}>
          <aside className="kso-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="kso-drawer-head">
              <div>
                <div className="kso-drawer-eyebrow">Оформление заказа</div>
                <div className="kso-drawer-title">Корзина</div>
              </div>
              <button className="kso-secondary-btn small" onClick={() => setCheckoutOpen(false)}>Закрыть</button>
            </div>

            <div className="kso-drawer-service">
              <div className={`kso-service-badge ${serviceMode === 'takeaway' ? 'takeaway' : ''}`}>
                {serviceMode === 'takeaway' ? 'С собой' : 'В зале'}
              </div>
            </div>

            <div className="kso-drawer-scroll">
              <div className="kso-cart-list">
                {cart.length === 0 && <div className="kso-empty">Корзина пуста</div>}

                {cart.map(item => (
                  <div className="kso-cart-row" key={item.local_id}>
                    <div className="kso-cart-row-left">
                      <div className="kso-cart-row-title">{item.qty} × {item.name}</div>

                      {item.options.length > 0 ? (
                        <div className="kso-cart-row-options">
                          {item.options.map((opt, idx) => (
                            <div key={idx} className="kso-cart-row-option">
                              + {opt.name}{Number(opt.price || 0) > 0 ? ` (+${opt.price} ₸)` : ''}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="kso-cart-row-note">Без дополнительных опций</div>
                      )}
                    </div>

                    <div className="kso-cart-row-right">
                      <div className="kso-cart-row-price">{formatPrice(item.lineTotal)}</div>
                      <button className="kso-remove-btn" onClick={() => removeCartItem(item.local_id)}>×</button>
                    </div>
                  </div>
                ))}
              </div>

              {upsellItems.length > 0 && (
                <div className="kso-upsell-block">
                  <div className="kso-upsell-head">
                    <div className="kso-upsell-title">Добавить к заказу</div>
                    <div className="kso-upsell-subtitle">Быстрые рекомендации</div>
                  </div>

                  <div className="kso-upsell-list">
                    {upsellItems.map(item => (
                      <div className="kso-upsell-card" key={item.id}>
                        <div>
                          <div className="kso-upsell-name">{item.name}</div>
                          <div className="kso-upsell-price">{formatPrice(item.price)}</div>
                        </div>
                        <button className="kso-select-btn" onClick={() => addSimpleItemToCart(item)}>
                          Добавить
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="kso-drawer-footer">
              <div className="kso-drawer-total">
                <span>Итого</span>
                <b>{formatPrice(cartTotal)}</b>
              </div>

              <div className="kso-drawer-eta">
                {etaText}
              </div>

              <button
                className="kso-primary-btn wide"
                onClick={submitOrder}
                disabled={submitting || cart.length === 0}
              >
                {submitting ? 'Отправка…' : 'Подтвердить заказ'}
              </button>
            </div>
          </aside>
        </div>
      )}

      {success && (
        <div className="kso-success-overlay" onClick={resetKsoState}>
          <div className="kso-success-card" onClick={(e) => e.stopPropagation()}>
            <div className="kso-success-mark">J</div>
            <div className="kso-success-eyebrow">Заказ создан</div>
            <div className="kso-success-title">Номер заказа #{success.number}</div>
            <div className="kso-success-text">
              Следите за статусом заказа на экране выдачи
            </div>

            <div className="kso-success-actions">
              <button className="kso-primary-btn wide" onClick={resetKsoState}>
                Новый заказ
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
