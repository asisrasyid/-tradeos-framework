import { useState, useEffect, useRef } from 'react'
import { api } from '../lib/api'

export interface AlertLog {
  id:         string
  ts:         string   // "14:32:05"
  tf:         string   // "M1,M5,H1" (merged) | "--"
  tag:        string   // STATE | S/R | LIQ | VOL | MOM | DIV | SYS
  msg:        string
  severity:   'info' | 'warning' | 'danger' | 'divergence' | 'system'
  confidence: number   // 0.0–1.0 (0 for system messages)
  action:     'BUY' | 'SELL' | 'NEUTRAL' | ''  // '' for system messages
}

const STORAGE_KEY = 'hmm_alert_log_v1'
const MAX_LOGS    = 500

function getTFsForNow(now: Date): string[] {
  const m = now.getMinutes()
  const h = now.getHours()
  const tfs: string[] = ['M1', 'M5']
  if (m % 5  === 0) tfs.push('M15')
  if (m % 15 === 0) tfs.push('M30')
  if (m === 0) {
    tfs.push('H1')
    if (h % 4 === 0) tfs.push('H4')
  }
  return tfs
}

function loadFromStorage(): AlertLog[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as AlertLog[]) : []
  } catch { return [] }
}

function saveToStorage(logs: AlertLog[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(logs)) } catch { /* quota */ }
}

export function useHmmAlertLog({
  instrument,
  enabled,
}: {
  instrument: string
  enabled: boolean
}) {
  const [logs, setLogs] = useState<AlertLog[]>(loadFromStorage)
  const [isPaused, setIsPaused] = useState(false)
  const latestRef = useRef({ instrument, enabled, isPaused })

  useEffect(() => {
    latestRef.current = { instrument, enabled, isPaused }
  })

  // Persist whenever logs change
  useEffect(() => {
    saveToStorage(logs)
  }, [logs])

  function addSystemLog(msg: string) {
    const entry: AlertLog = {
      id:         crypto.randomUUID(),
      ts:         new Date().toLocaleTimeString('id-ID', { hour12: false }),
      tf:         '--',
      tag:        'SYS',
      msg,
      severity:   'system',
      confidence: 0,
      action:     '',
    }
    setLogs(prev => [entry, ...prev].slice(0, MAX_LOGS))
  }

  function clearLogs() {
    setLogs([])
    localStorage.removeItem(STORAGE_KEY)
  }

  // Polling engine
  useEffect(() => {
    let lastEnabled = false

    async function poll() {
      const { instrument: inst, enabled: en, isPaused: paused } = latestRef.current
      if (!en || paused || !inst) {
        if (lastEnabled && !en) {
          // engine just stopped
        }
        lastEnabled = en
        return
      }

      if (!lastEnabled && en) {
        addSystemLog(`Analisis dimulai · ${inst} · 6 timeframes`)
      }
      lastEnabled = en

      const tfs = getTFsForNow(new Date())
      try {
        const items = await api.getMultiTfAnalysis(inst, tfs)
        if (items.length === 0) return
        const now = new Date().toLocaleTimeString('id-ID', { hour12: false })
        const newLogs: AlertLog[] = items.map(item => ({
          id:         crypto.randomUUID(),
          ts:         now,
          tf:         item.tf,
          tag:        item.tag,
          msg:        item.msg,
          severity:   item.severity as AlertLog['severity'],
          confidence: item.confidence ?? 0,
          action:     item.action ?? 'NEUTRAL',
        }))
        setLogs(prev => [...newLogs, ...prev].slice(0, MAX_LOGS))
      } catch {
        // silent — MT5 might be momentarily unavailable
      }
    }

    poll()
    const id = setInterval(poll, 30_000)
    return () => clearInterval(id)
  }, []) // intentionally empty — uses ref for latest values

  return { logs, isPaused, setIsPaused, clearLogs }
}
