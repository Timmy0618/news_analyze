import { useState, useEffect } from 'react'
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip,
  LineChart, Line, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Panel, ErrorBanner } from './ui'
import { newsApi, errorMessage } from '../lib/newsApi'
import type { DailyCount, SourceCount } from '../types'

// Data-viz palettes per theme. Recharts/canvas need concrete color
// strings, so we pick by theme rather than via CSS vars.
interface VizPalette {
  colors: string[]
  axisFill: string
  axisStroke: string
  grid: string
  cursorStroke: string
  cursorFill: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
  line: string
}

const VIZ_DARK: VizPalette = {
  colors: ['#f0b429', '#d9822b', '#b5533a', '#6f9188', '#a89e88', '#f8d585'],
  axisFill: '#897f6b',
  axisStroke: '#342f24',
  grid: '#26221a',
  cursorStroke: '#342f24',
  cursorFill: 'rgba(240,180,41,0.06)',
  tooltipBg: '#1b1813',
  tooltipBorder: '#342f24',
  tooltipText: '#c9c0ad',
  line: '#f0b429',
}

const VIZ_LIGHT: VizPalette = {
  colors: ['#c77f0a', '#b5533a', '#4f7168', '#8a6d3b', '#9c5a2a', '#6e4a06'],
  axisFill: '#6b6250',
  axisStroke: '#d3cbb6',
  grid: '#e2dccb',
  cursorStroke: '#d3cbb6',
  cursorFill: 'rgba(183,134,11,0.10)',
  tooltipBg: '#ffffff',
  tooltipBorder: '#d3cbb6',
  tooltipText: '#141310',
  line: '#b7860b',
}

const DAY_OPTIONS = [7, 14, 30, 60]

export default function TopicStats({ theme }: { theme: 'light' | 'dark' }) {
  const viz = theme === 'dark' ? VIZ_DARK : VIZ_LIGHT
  const COLORS = viz.colors
  const AXIS = { fill: viz.axisFill, fontSize: 11, fontFamily: 'ui-monospace, monospace' }
  const TOOLTIP = {
    backgroundColor: viz.tooltipBg,
    border: `1px solid ${viz.tooltipBorder}`,
    color: viz.tooltipText,
    borderRadius: 2,
    fontFamily: 'ui-monospace, monospace',
    fontSize: 12,
  }
  const [daily, setDaily] = useState<DailyCount[]>([])
  const [bySite, setBySite] = useState<SourceCount[]>([])
  const [totalArticles, setTotalArticles] = useState(0)
  const [dateRange, setDateRange] = useState({ min: '', max: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')

      const since = new Date()
      since.setDate(since.getDate() - days)
      const pad = (n: number) => String(n).padStart(2, '0')
      const sinceStr = `${since.getFullYear()}-${pad(since.getMonth() + 1)}-${pad(since.getDate())}`

      try {
        const s = await newsApi.stats(sinceStr)
        setTotalArticles(s.total)
        setDaily(s.daily)
        setBySite(s.bySite)
        setDateRange({
          min: s.daily[0]?.publish_date ?? '',
          max: s.daily[s.daily.length - 1]?.publish_date ?? '',
        })
      } catch (e) {
        setError(errorMessage(e))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [days])

  if (loading) return <div className="text-gray-500 font-mono text-sm text-center py-12">載入統計中…</div>

  return (
    <div className="space-y-5">
      <ErrorBanner msg={error} />
      {/* window selector — segmented mono control */}
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow">Window</span>
        <div className="inline-flex rounded-sm border border-gray-700 overflow-hidden">
          {DAY_OPTIONS.map((d, i) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 text-xs font-mono transition-colors ${i > 0 ? 'border-l border-gray-700' : ''} ${
                days === d ? 'bg-blue-500/15 text-blue-400' : 'text-gray-500 hover:text-gray-200 hover:bg-gray-700/60'
              }`}
            >
              {d}D
            </button>
          ))}
        </div>
      </div>

      {/* readouts */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-gray-800 border border-gray-700 rounded-sm p-4">
          <div className="eyebrow">Dispatches</div>
          <div className="mt-2 text-3xl font-mono font-semibold text-blue-400 tabular-nums">{totalArticles.toLocaleString()}</div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded-sm p-4">
          <div className="eyebrow">Sources</div>
          <div className="mt-2 text-3xl font-mono font-semibold text-gray-100 tabular-nums">{bySite.length}</div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded-sm p-4">
          <div className="eyebrow">Range</div>
          <div className="mt-2 font-mono text-blue-400 text-sm tabular-nums">
            {dateRange.min || '—'} <span className="text-gray-600">→</span> {dateRange.max || '—'}
          </div>
        </div>
      </div>

      <Panel eyebrow="每日文章數量 / Daily volume">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={daily} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke={viz.grid} />
            <XAxis dataKey="publish_date" tick={AXIS} stroke={viz.axisStroke} />
            <YAxis tick={AXIS} stroke={viz.axisStroke} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ stroke: viz.cursorStroke }} />
            <Line type="monotone" dataKey="count" stroke={viz.line} dot={false} strokeWidth={2} name="篇數" />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel eyebrow="各來源文章數 / By source">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={bySite} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke={viz.grid} />
            <XAxis dataKey="source_site" tick={AXIS} stroke={viz.axisStroke} />
            <YAxis tick={AXIS} stroke={viz.axisStroke} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ fill: viz.cursorFill }} />
            <Bar dataKey="count" name="篇數" radius={[2, 2, 0, 0]}>
              {bySite.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  )
}
