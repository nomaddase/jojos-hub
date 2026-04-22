import { Routes, Route, Navigate } from 'react-router-dom'
import KsoPage from './KsoPage'
import KitchenPage from './KitchenPage'
import DisplayPage from './DisplayPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/kso" replace />} />
      <Route path="/kso" element={<KsoPage />} />
      <Route path="/kitchen" element={<KitchenPage />} />
      <Route path="/display" element={<DisplayPage />} />
    </Routes>
  )
}
