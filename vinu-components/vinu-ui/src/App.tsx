import { Routes, Route, Navigate, useParams } from 'react-router'
import { useEffect } from 'react'
import Layout from './components/Layout'
import Terminal from './terminal/Terminal'
import { useUI } from './store'

function SymSync() {
  const { sym } = useParams()
  const setSym = useUI((s) => s.setSym)
  useEffect(() => { if (sym) setSym(sym) }, [sym, setSym])
  return <Terminal />
}
import Tickers from './pages/Tickers'
import TickerDetail from './pages/TickerDetail'
import Live from './pages/Live'
import Simulator from './pages/Simulator'
import Agents from './pages/Agents'
import More from './pages/More'

export default function App() {
  // Dense operator terminal is the default screen; nav pages stay as drill-downs.
  return (
    <Routes>
      <Route path="/" element={<Terminal />} />
      <Route path="/classic/*" element={
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/classic/tickers" replace />} />
            <Route path="/tickers" element={<Tickers />} />
            <Route path="/tickers/:sym" element={<TickerDetail />} />
            <Route path="/live" element={<Live />} />
            <Route path="/simulator" element={<Simulator />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/portfolio" element={<More section="portfolio" />} />
            <Route path="/screener" element={<More section="screener" />} />
            <Route path="/research" element={<More section="research" />} />
          </Routes>
        </Layout>
      } />
      <Route path="/tickers" element={<Terminal />} />
      <Route path="/tickers/:sym" element={<SymSync />} />
      <Route path="/live" element={<Terminal />} />
      <Route path="/simulator" element={<Terminal />} />
      <Route path="/agents" element={<Terminal />} />
      <Route path="/portfolio" element={<Terminal />} />
      <Route path="/screener" element={<Terminal />} />
      <Route path="/research" element={<Terminal />} />
    </Routes>
  )
}
