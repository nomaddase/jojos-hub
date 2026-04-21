import { DisplayZone } from './display/DisplayZone'
import { useDisplayBoard } from './display/useDisplayBoard'

export default function DisplayPage() {
  const { data, gridConfig, page, pageCount, acceptedVisible, readyVisible } = useDisplayBoard()

  return (
    <div className="screen display-board">
      <DisplayZone title="Принятые" count={data.accepted_orders.length} orders={acceptedVisible} gridConfig={gridConfig} />
      <DisplayZone title="Готовые" count={data.ready_orders.length} orders={readyVisible} gridConfig={gridConfig} ready />
      {pageCount > 1 && <div className="display-page-indicator">Страница {page + 1} / {pageCount}</div>}
    </div>
  )
}
