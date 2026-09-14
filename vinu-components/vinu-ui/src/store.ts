import { create } from 'zustand'

export type BoardFmt = 'table' | 'kanban' | 'timeline' | 'raw'
export type DetailTab = 'flow' | 'angles' | 'gates' | 'charts' | 'ledger'

interface UIState {
  boardFmt: BoardFmt
  setBoardFmt: (f: BoardFmt) => void
  sym: string
  setSym: (s: string) => void
  detailTab: DetailTab
  setDetailTab: (t: DetailTab) => void
  family: string
  setFamily: (f: string) => void
}

export const useUI = create<UIState>((set) => ({
  boardFmt: 'table',
  setBoardFmt: (boardFmt) => set({ boardFmt }),
  sym: 'AAPL',
  setSym: (sym) => set({ sym }),
  detailTab: 'flow',
  setDetailTab: (detailTab) => set({ detailTab }),
  family: 'ensemble',
  setFamily: (family) => set({ family }),
}))
