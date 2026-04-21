import PropTypes from 'prop-types'

export function DisplayZone({ title, count, orders, gridConfig, ready }) {
  return (
    <section className={`display-zone ${ready ? 'ready-zone' : 'accepted-zone'}`}>
      <div className="display-zone-head">
        <div><div className="eyebrow">JoJo’s</div><div className="display-zone-title">{title}</div></div>
        <div className="display-zone-count">{count}</div>
      </div>

      {orders.length === 0 ? (
        <div className={`display-zone-empty ${ready ? 'ready' : ''}`}>{ready ? 'Готовых заказов пока нет' : 'Нет активных принятых заказов'}</div>
      ) : (
        <div className={`display-order-grid ${gridConfig.density} cols-${gridConfig.cols}`} style={{ '--display-grid-rows': gridConfig.rows }}>
          {orders.map((order) => (
            <div className={`display-order-card ${ready ? 'ready' : 'accepted'}`} key={order.id}>
              <div className="display-order-number">#{order.number}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

DisplayZone.propTypes = {
  title: PropTypes.string.isRequired,
  count: PropTypes.number.isRequired,
  orders: PropTypes.array.isRequired,
  gridConfig: PropTypes.object.isRequired,
  ready: PropTypes.bool
}
