import PropTypes from 'prop-types'
import { getTiming } from './kitchenTiming'
import { formatTimer } from '../shared/time'
import { useNow } from '../shared/useNow'

export function KitchenOrderCard({ order, warningRatio, onOpen }) {
  const nowMs = useNow(1000)
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
    </div>
  )
}

KitchenOrderCard.propTypes = {
  order: PropTypes.object.isRequired,
  warningRatio: PropTypes.number.isRequired,
  onOpen: PropTypes.func.isRequired
}
