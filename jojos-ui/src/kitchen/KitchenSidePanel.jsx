import PropTypes from 'prop-types'
import { getTiming } from './kitchenTiming'
import { formatTimer } from '../shared/time'
import { useNow } from '../shared/useNow'

export function KitchenSidePanel({ order, warningRatio, onClose, onReady, onBeginHold, onEndHold }) {
  const nowMs = useNow(1000)
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
          <div className="kitchen-side-row"><span>Прошло</span><b>{formatTimer(timing.elapsedSeconds)}</b></div>
          <div className="kitchen-side-row"><span>Норма</span><b>{formatTimer(timing.targetPrepSeconds)}</b></div>
          <div className="kitchen-side-row"><span>Статус</span><b>{timing.timeState}</b></div>
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
  onEndHold: PropTypes.func.isRequired
}
