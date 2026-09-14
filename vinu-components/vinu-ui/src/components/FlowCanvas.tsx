import { useEffect, useRef } from 'react'

// Subtle animated particle flow (data drifting left → right through stages).
// Capped DPR, low density, paused when tab hidden — cheap by design.
export default function FlowCanvas({ height = 30, density = 14 }: { height?: number; density?: number }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    let raf = 0
    let w = (canvas.width = canvas.offsetWidth * dpr)
    const h = (canvas.height = height * dpr)
    const parts = Array.from({ length: density }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      v: (0.4 + Math.random() * 0.9) * dpr,
      r: (1 + Math.random() * 1.6) * dpr,
      hue: Math.random() < 0.12 ? '248,81,73' : Math.random() < 0.3 ? '163,113,247' : '47,129,247',
    }))
    const tick = () => {
      if (document.hidden) { raf = requestAnimationFrame(tick); return }
      ctx.clearRect(0, 0, w, h)
      for (const p of parts) {
        p.x += p.v
        if (p.x > w) { p.x = -4; p.y = Math.random() * h }
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${p.hue},0.55)`
        ctx.fill()
      }
      raf = requestAnimationFrame(tick)
    }
    const onResize = () => { w = canvas.width = canvas.offsetWidth * dpr }
    const onVis = () => { /* tick self-skips while hidden */ }
    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', onVis)
    tick()
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize); document.removeEventListener('visibilitychange', onVis) }
  }, [height, density])

  return <canvas ref={ref} style={{ height }} className="w-full opacity-70" aria-hidden />
}
