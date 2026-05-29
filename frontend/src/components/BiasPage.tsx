import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../lib/supabase'
import type { BiasCluster, BiasSourceStat } from '../types'

const VERDICTS = ['side_a', 'neutral', 'side_b'] as const
type Verdict = typeof VERDICTS[number]

const VERDICT: Record<Verdict, { label: string; bar: string; text: string }> = {
  side_a:  { label: '偏A方', bar: 'bg-blue-500',   text: 'text-blue-400' },
  neutral: { label: '中立',  bar: 'bg-gray-400',   text: 'text-gray-400' },
  side_b:  { label: '偏B方', bar: 'bg-orange-500', text: 'text-orange-400' },
}

const DAY_OPTIONS = [3, 7, 14, 30]

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function todayIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function BiasBar({ articles }: { articles: BiasCluster['articles'] }) {
  const total = articles.length
  if (total === 0) return null

  const counts = { side_a: 0, neutral: 0, side_b: 0 }
  for (const a of articles) {
    if (a.verdict in counts) counts[a.verdict as Verdict]++
  }

  return (
    <div className="space-y-1">
      <div className="flex rounded overflow-hidden h-3">
        {VERDICTS.map((v) =>
          counts[v] > 0 ? (
            <div
              key={v}
              className={VERDICT[v].bar}
              style={{ width: `${(counts[v] / total) * 100}%` }}
              title={`${VERDICT[v].label}: ${counts[v]}`}
            />
          ) : null
        )}
      </div>
      <div className="flex gap-4 text-xs">
        {VERDICTS.map((v) => (
          <span key={v} className={`flex items-center gap-1 ${VERDICT[v].text}`}>
            <span className={`w-2 h-2 rounded-full ${VERDICT[v].bar} inline-block`} />
            {VERDICT[v].label} {counts[v]}
          </span>
        ))}
      </div>
    </div>
  )
}

function SourceBiasPanel({ stats }: { stats: BiasSourceStat[] }) {
  if (stats.length === 0) return null
  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <div className="text-sm font-medium text-gray-300">媒體黨派率（被判定為偏向某方的比例）</div>
      <div className="space-y-2">
        {stats.map((s) => {
          const pct = Math.round((s.partisan_rate ?? 0) * 100)
          return (
            <div key={s.source_site} className="flex items-center gap-3">
              <div className="w-24 shrink-0 text-xs text-gray-400 truncate" title={s.source_site}>
                {s.source_site}
              </div>
              <div className="flex-1 bg-gray-700 rounded h-3 overflow-hidden">
                <div className="bg-orange-500 h-full" style={{ width: `${pct}%` }} />
              </div>
              <div className="w-20 shrink-0 text-right text-xs text-gray-400">
                {pct}%（{s.partisan}/{s.total}）
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ClusterCard({ cluster }: { cluster: BiasCluster }) {
  const [expanded, setExpanded] = useState(false)

  const grouped = {
    side_a: cluster.articles.filter((a) => a.verdict === 'side_a'),
    neutral: cluster.articles.filter((a) => a.verdict === 'neutral'),
    side_b: cluster.articles.filter((a) => a.verdict === 'side_b'),
  }

  const hasSides = !!(cluster.side_a || cluster.side_b)

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium text-white">{cluster.cluster_label}</div>
          {hasSides ? (
            <div className="text-xs text-gray-400 mt-0.5">
              A方：<span className="text-blue-400">{cluster.side_a}</span>
              {' '}｜{' '}
              B方：<span className="text-orange-400">{cluster.side_b}</span>
            </div>
          ) : (
            <div className="text-xs text-gray-500 mt-0.5">資訊型主題（無對立立場）</div>
          )}
        </div>
        <div className="flex flex-col items-end shrink-0">
          <span className="text-xs text-gray-500">{cluster.article_count} 篇</span>
          {cluster.run_date && (
            <span className="text-[10px] text-gray-600 mt-0.5">{cluster.run_date}</span>
          )}
        </div>
      </div>

      <BiasBar articles={cluster.articles} />

      <button
        onClick={() => setExpanded((e) => !e)}
        className="text-xs text-gray-400 hover:text-white transition-colors"
      >
        {expanded ? '▲ 收合' : '▼ 展開文章'}
      </button>

      {expanded && (
        <div className="space-y-3 pt-1">
          {VERDICTS.map((v) =>
            grouped[v].length > 0 ? (
              <div key={v}>
                <div className={`text-xs font-semibold mb-1.5 ${VERDICT[v].text}`}>
                  {VERDICT[v].label}（{grouped[v].length}）
                </div>
                <div className="space-y-2">
                  {grouped[v].map((a) => (
                    <div key={a.id} className="border-l-2 border-gray-600 pl-3 space-y-0.5">
                      <a
                        href={a.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-400 hover:text-blue-300 leading-snug block"
                      >
                        {a.title}
                      </a>
                      <div className="text-xs text-gray-500">
                        {a.source_site}
                        {a.publish_date ? ` · ${a.publish_date}` : ''}
                      </div>
                      {a.reasoning && (
                        <div className="text-xs text-gray-400 italic">{a.reasoning}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : null
          )}
        </div>
      )}
    </div>
  )
}

export default function BiasPage() {
  const [clusters, setClusters] = useState<BiasCluster[]>([])
  const [sourceStats, setSourceStats] = useState<BiasSourceStat[]>([])
  const [runDate, setRunDate] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')
  const [days, setDays] = useState(7)

  const load = useCallback(async (d: number) => {
    setLoading(true)
    setError('')

    const dateFrom = isoDaysAgo(d)
    const dateTo = todayIso()

    const [fn, rpc] = await Promise.all([
      supabase.functions.invoke<{
        run_date: string | null
        clusters: BiasCluster[]
      }>('bias', { body: { date_from: dateFrom, date_to: dateTo } }),
      supabase.rpc('get_bias_stats', { date_from: dateFrom, date_to: dateTo }),
    ])

    setLoading(false)
    setLoaded(true)
    if (fn.error) {
      setError(`載入失敗: ${fn.error.message}`)
      return
    }
    if (fn.data) {
      setRunDate(fn.data.run_date)
      setClusters(fn.data.clusters ?? [])
    }
    setSourceStats(rpc.error || !rpc.data ? [] : (rpc.data as BiasSourceStat[]))
  }, [])

  useEffect(() => {
    load(days)
  }, [days, load])

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 rounded-lg p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              disabled={loading}
              className={`px-3 py-1 rounded text-sm disabled:opacity-40 ${
                days === d ? 'bg-indigo-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              近 {d} 天
            </button>
          ))}
        </div>
        <span className="text-xs text-gray-400">
          {loading ? '載入中...' : runDate ? `最新分析日期：${runDate}` : ''}
        </span>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-900/20 rounded p-3">{error}</div>
      )}

      <SourceBiasPanel stats={sourceStats} />

      {!loading && loaded && clusters.length === 0 && (
        <div className="text-gray-400 text-center py-12">此區間尚無分析資料</div>
      )}

      <div className="space-y-3">
        {clusters.map((c) => (
          <ClusterCard key={`${c.run_date}-${c.id}`} cluster={c} />
        ))}
      </div>
    </div>
  )
}
