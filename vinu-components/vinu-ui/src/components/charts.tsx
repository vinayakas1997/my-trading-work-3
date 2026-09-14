import { useEffect, useRef } from 'react'
import { createChart, type SeriesMarker } from 'lightweight-charts'
import * as echarts from 'echarts'
import type { Candle } from '../lib/api'

// Candles + entries/exits + forecast cone (line series) — the live+Kronos view.
export function LWCandles({ data, markers, forecast }: {
  data: Candle[]
  markers?: SeriesMarker<string>[]
  forecast?: { time: number; value: number }[]
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || data.length === 0) return
    const chart = createChart(ref.current, {
      layout: { background: { color: '#0A0E14' }, textColor: '#8B93A3', fontFamily: 'JetBrains Mono' },
      grid: { vertLines: { color: '#1E2632' }, horzLines: { color: '#1E2632' } },
      height: 300,
    })
    const cs = chart.addCandlestickSeries({
      upColor: '#26A69A', downColor: '#EF5350',
      wickUpColor: '#26A69A', wickDownColor: '#EF5350', borderVisible: false,
    })
    cs.setData(data as any)
    if (markers?.length) (cs as any).setMarkers(markers)
    if (forecast?.length) {
      const fl = chart.addLineSeries({ color: '#A371F7', lineWidth: 2, lineStyle: 2 as any, priceLineVisible: false })
      fl.setData(forecast as any)
    }
    const onResize = () => chart.applyOptions({ width: ref.current!.clientWidth })
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.remove() }
  }, [data, markers, forecast])

  return <div ref={ref} className="w-full" />
}

// Generic ECharts wrapper (equity, drawdown, correlation, sweep, attribution).
export function EChart({ option, height = 260 }: { option: echarts.EChartsOption; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const inst = echarts.init(ref.current)
    inst.setOption({ backgroundColor: '#0A0E14', textStyle: { color: '#8B93A3', fontFamily: 'JetBrains Mono', fontSize: 10 }, ...option })
    const onResize = () => inst.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); inst.dispose() }
  }, [option])

  return <div ref={ref} style={{ height }} className="w-full" />
}
