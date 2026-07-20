import { useState, useEffect } from 'react'
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip,
  LineChart, Line, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Panel } from './ui'
import { supabase } from '../lib/supabase'

interface DailyCount {
  publish_date: string
  count: number
}

interface SourceCount {
  source_site: string
  count: number
}

// Signal Monitor data-viz ramp: warm family, distinct on graphite.
const COLORS = ['#f0b429', '#d9822b', '#b5533a', '#6f9188', '#a89e88', '#f8d585']

const AXIS = { fill: '#897f6b', fontSize: 11, fontFamily: 'ui-monospace, monospace' }
const TOOLTIP = {
  backgroundColor: '#1b1813',
  border: '1px solid #342f24',
  borderRadius: 2,
  fontFamily: 'ui-monospace, monospace',
  fontSize: 12,
}

const DAY_OPTIONS = [7, 14, 30, 60]

export default function TopicStats() {
  const [daily, setDaily] = useState<DailyCount[]>([])
  const [bySite, setBySite] = useState<SourceCount[]>([])
  const [totalArticles, setTotalArticles] = useState(0)
  const [dateRange, setDateRange] = useState({ min: '', max: '' })
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    async function load() {
      setLoading(true)

      const since = new Date()
      since.setDate(since.getDate() - days)
      const pad = (n: number) => String(n).padStart(2, '0')
      const sinceStr = `${since.getFullYear()}-${pad(since.getMonth() + 1)}-${pad(since.getDate())}`

      const { data, error } = await supabase.rpc('get_article_stats', { since_date: sinceStr })

      if (error || !data) { setLoading(false); return }

      const daily: { publish_date: string; count: number }[] = data.daily ?? []
      const bySite: { source_site: string; count: number }[] = data.by_site ?? []

      setTotalArticles(Number(data.total ?? 0))
      setDateRange({
        min: daily[0]?.publish_date ?? '',
        max: daily[daily.length - 1]?.publish_date ?? '',
      })
      setDaily(daily.map(r => ({ publish_date: r.publish_date, count: Number(r.count) })))
      setBySite(bySite.map(r => ({ source_site: r.source_site, count: Number(r.count) })))
      setLoading(false)
    }
    load()
  }, [days])

  if (loading) return <div className="text-gray-500 font-mono text-sm text-center py-12">載入統計中…</div>

  return (
    <div className="space-y-5">
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
            <CartesianGrid strokeDasharray="2 4" stroke="#26221a" />
            <XAxis dataKey="publish_date" tick={AXIS} stroke="#342f24" />
            <YAxis tick={AXIS} stroke="#342f24" />
            <Tooltip contentStyle={TOOLTIP} cursor={{ stroke: '#342f24' }} />
            <Line type="monotone" dataKey="count" stroke="#f0b429" dot={false} strokeWidth={2} name="篇數" />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel eyebrow="各來源文章數 / By source">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={bySite} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="2 4" stroke="#26221a" />
            <XAxis dataKey="source_site" tick={AXIS} stroke="#342f24" />
            <YAxis tick={AXIS} stroke="#342f24" />
            <Tooltip contentStyle={TOOLTIP} cursor={{ fill: 'rgba(240,180,41,0.06)' }} />
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
