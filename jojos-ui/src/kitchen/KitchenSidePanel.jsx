import PropTypes from 'prop-types'
import { getTiming } from './kitchenTiming'
import { formatTimer } from '../shared/time'

export function KitchenSidePanel({ order, warningRatio, onClose, onReady, onBeginHold, onEndHold, nowMs }) {
  const timing = getTiming(order, nowMs, warningRatio)

  return (
    <div className="kitchen-side-overlay" onClick={onClose}>
      <aside className="kitchen-side-panel" onClick={(e) => e.stopPropagation()}>
        <div className="kitchen-side-head">
          <div>
            <div className="eyebrow">Подтверждение</div>
            <div className="kitchen-side-title">Заказ #{order.number}</div>
          </div>
          <div className={`kitchen-badge service ${order.service_mode === 'takeaway' ? 'takeaway' : ''}`}>
            {order.service_mode === 'takeaway' ? 'С собой' : 'В зале'}
          </div>
        </div>
        <div className="kitchen-side-scroll">
          <div className="kitchen-side-block">
            <div className="kitchen-side-row"><span>Прошло</span><b>{formatTimer(timing.elapsedSeconds)}</b></div>
            <div className="kitchen-side-row"><span>Норма</span><b>{formatTimer(timing.targetPrepSeconds)}</b></div>
            <div className="kitchen-side-row"><span>Статус</span><b>{timing.timeState}</b></div>
          </div>

          <div className="kitchen-side-block">
            <div className="kitchen-side-block-title">Состав заказа</div>
            <div className="kitchen-side-items">
              {(order.items || []).map((item, idx) => (
                <div className="kitchen-side-item" key={`${item.item_id || item.name}-${idx}`}>
                  <div className="kitchen-side-item-title">{item.qty} × {item.display_name || item.name}</div>
                  {(item.modifier_lines || []).length > 0 && (
                    <div className="kitchen-side-item-mods">
                      {(item.modifier_lines || []).map((mod, modIdx) => (
                        <div className="kitchen-side-item-mod" key={`${idx}-mod-${modIdx}`}>{mod}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="kitchen-side-actions">
          <button className="action-btn ready" onClick={onReady}>Готово</button>
          <button className="action-btn cancel" onPointerDown={onBeginHold} onPointerUp={onEndHold} onPointerCancel={onEndHold} onPointerLeave={onEndHold}>Удерживать</button>
          <button className="action-btn close" onClick={onClose}>Закрыть</button>
        </div>
      </aside>
    </div>
  )
}

KitchenSidePanel.propTypes = {
  order: PropTypes.object.isRequired,
  warningRatio: PropTypes.number.isRequired,
  onClose: PropTypes.func.isRequired,
  onReady: PropTypes.func.isRequired,
  onBeginHold: PropTypes.func.isRequired,
  onEndHold: PropTypes.func.isRequired,
  nowMs: PropTypes.number.isRequired
}
