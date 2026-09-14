import { Link, NavLink, useLocation } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import {
  CandlestickChart, Activity, FlaskConical, Bot, Wallet, Filter, Microscope, Moon, Sun,
} from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import FlowCanvas from './FlowCanvas'

const NAV = [
  { to: '/tickers', icon: CandlestickChart, label: 'Tickers' },
  { to: '/live', icon: Activity, label: 'Live' },
  { to: '/simulator', icon: FlaskConical, label: 'Simulator' },
  { to: '/agents', icon: Bot, label: 'Agents' },
  { to: '/portfolio', icon: Wallet, label: 'Portfolio' },
  { to: '/screener', icon: Filter, label: 'Screener' },
  { to: '/research', icon: Microscope, label: 'Research' },
]

function useFleet() {
  const broker = useQuery({ queryKey: ['broker-status'], queryFn: api.brokerStatus, refetchInterval: 10_000 })
  const risk = useQuery({ queryKey: ['pf-risk'], queryFn: api.pfRisk, refetchInterval: 60_000 })
  const emergency = useQuery({ queryKey: ['emergency'], queryFn: api.emergencyStatus, refetchInterval: 10_000 })
  return { broker: broker.data, risk: risk.data, emergency: emergency.data }
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const [dark, setDark] = useState(true)
  const loc = useLocation()
  const { broker, risk, emergency } = useFleet()
  const halted =
    (broker as any)?.halted === true ||
    (broker as any)?.trading_halted === true ||
    (emergency as any)?.halted === true

  return (
    <div className={dark ? 'dark' : ''}>
      <div className="min-h-screen bg-base text-ink font-sans">
        <div className="flex">
          {/* Sidebar — one glance nav, never stuffed */}
          <aside className="w-16 md:w-60 shrink-0 border-r border-edge bg-panel flex flex-col min-h-screen sticky top-0 h-screen">
            <Link to="/tickers" className="p-4 flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center font-extrabold text-white" style={{ background: 'linear-gradient(135deg,#2F81F7,#A371F7)' }}>V</div>
              <span className="hidden md:block font-extrabold tracking-tight">Vinu <span className="text-accent">·</span> Mirror</span>
            </Link>
            <nav className="px-2 space-y-0.5">
              {NAV.map(({ to, icon: Icon, label }) => {
                const active = loc.pathname.startsWith(to)
                return (
                  <NavLink key={to} to={to}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] transition-colors ${active ? 'bg-accent/15 text-accent font-semibold' : 'text-muted hover:bg-raised hover:text-ink'}`}>
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="hidden md:block">{label}</span>
                  </NavLink>
                )
              })}
            </nav>
            <div className="mt-auto p-3 border-t border-edge">
              <button onClick={() => setDark(!dark)} className="flex items-center gap-2 text-xs text-muted hover:text-ink">
                {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                <span className="hidden md:block">{dark ? 'Light' : 'Dark'}</span>
              </button>
              <div className="hidden md:block mt-2 text-[10px] text-faint num">
                {broker ? '● services live' : '○ services unreachable · mock'}
              </div>
            </div>
          </aside>

          {/* Main */}
          <div className="flex-1 min-w-0">
            {/* Fleet strip — always visible, one line */}
            <div className={`px-4 md:px-6 pt-4 ${halted ? '' : ''}`}>
              {halted && (
                <div className="card halt-glow p-3 mb-3 flex items-center gap-3" style={{ borderColor: '#F85149' }}>
                  <span className="dot" style={{ background: '#F85149' }} />
                  <div className="text-sm"><b className="text-halt">TRADING HALTED</b> <span className="text-muted">· entries + PEND→ACTIVE blocked · reduce-only exits still pass</span></div>
                </div>
              )}
              <div className="flex flex-wrap gap-2 text-xs items-center">
                <span className="chip"><span className="dot" style={{ background: halted ? '#F85149' : '#3FB950' }} />{halted ? 'HALTED' : 'CLEAR'}</span>
                <span className="chip"><span className="dot" style={{ background: '#3FB950' }} />broker {broker ? 'healthy' : 'unknown'}</span>
                <span className="chip"><span className="dot" style={{ background: '#F0B90B' }} />drawdown <span className="num">{(risk as any)?.drawdown_pct ?? '—'}</span></span>
                <span className="chip">OOD dormant</span>
                <span className="chip num">live 5m · risk 15m · shadow 1h</span>
              </div>
            </div>
            <main className="p-4 md:p-6 space-y-4 max-w-7xl mx-auto">
              <FlowCanvas height={30} density={22} />
              {children}
            </main>
          </div>
        </div>
      </div>
    </div>
  )
}
