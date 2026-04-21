import PropTypes from 'prop-types'
import { getTiming } from './kitchenTiming'
import { formatTimer } from '../shared/time'

export function KitchenOrderCard({ order, warningRatio, onOpen, nowMs }) {
  const timing = getTiming(order, nowMs, warningRatio)

  return (
    <div
      className={`kitchen-tile ${timing.timeState} ${order.service_mode === 'takeaway' ? 'takeaway' : ''}`}
      onClick={() => onOpen(order)}
    >
      <div className="tile-top">
        <div>
          <div className="tile-label">Заказ</div>
          <div className="order-number">#{order.number}</div>
        </div>
        <div className="order-timer-block">
          <div className="tile-label">Ожидание</div>
          <div className="order-timer">{formatTimer(timing.elapsedSeconds)}</div>
        </div>
      </div>

      <div className="tile-badges">
        <div className={`kitchen-badge service ${order.service_mode === 'takeaway' ? 'takeaway' : ''}`}>
          {order.service_mode === 'takeaway' ? 'С собой' : 'В зале'}
        </div>
      </div>

      <div className="tile-bar-wrap">
        <div className={`tile-bar ${timing.timeState}`} style={{ width: `${Math.min(timing.progressRatio * 100, 100)}%` }} />
      </div>

      <div className="tile-meta">
        <span>Цель: {formatTimer(timing.targetPrepSeconds)}</span>
        <span>{timing.timeState === 'overdue' ? 'Просрочен' : 'В работе'}</span>
      </div>

      <div className="tile-items">
        {(order.items || []).slice(0, 3).map((item, idx) => (
          <div key={`${item.item_id || item.name}-${idx}`} className="tile-item">
            <div className="tile-item-main">{item.qty} × {item.display_name || item.name}</div>
            {(item.modifier_lines || []).length > 0 && (
              <div className="tile-item-mods">
                {(item.modifier_lines || []).map((mod, modIdx) => (
                  <div key={`${idx}-mod-${modIdx}`} className="tile-item-mod">{mod}</div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

KitchenOrderCard.propTypes = {
  order: PropTypes.object.isRequired,
  warningRatio: PropTypes.number.isRequired,
  onOpen: PropTypes.func.isRequired,
  nowMs: PropTypes.number.isRequired
}
