import { useState, useEffect } from 'react'
import { FiChevronUp, FiChevronDown } from 'react-icons/fi'
import { newsApi, errorMessage } from '../lib/newsApi'
import type { BiasCluster, BiasSourceStat, BiasReporterStat } from '../types'
import { ErrorBanner } from './ui'

const VERDICTS = ['side_a', 'neutral', 'side_b'] as const
type Verdict = typeof VERDICTS[number]

// Bias sides are pinned blue/red (independent of the amber Signal Monitor
// accent) but adapt to light/dark via the --bias-* vars in index.css.
const BIAS_A = 'var(--bias-a-ink)'
const BIAS_A_TEXT = 'text-[var(--bias-a-text)]'
const BIAS_B = 'var(--bias-b-ink)'
const BIAS_B_TEXT = 'text-[var(--bias-b-text)]'

const VERDICT: Record<Verdict, { label: string; bar: string; text: string }> = {
  side_a:  { label: '偏A方', bar: 'bg-[#3b82f6]', text: BIAS_A_TEXT },
  neutral: { label: '中立',  bar: 'bg-[#6b6250]', text: 'text-[var(--bias-neutral-text)]' },
  side_b:  { label: '偏B方', bar: 'bg-[#e5484d]', text: BIAS_B_TEXT },
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
    <div className="space-y-1.5">
      <div className="flex rounded-sm overflow-hidden h-2.5">
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
      <div className="flex gap-4 font-mono text-xs">
        {VERDICTS.map((v) => (
          <span key={v} className={`flex items-center gap-1 ${VERDICT[v].text}`}>
            <span className={`w-2 h-2 rounded-full ${VERDICT[v].bar} inline-block`} />
            {VERDICT[v].label} <span className="tabular-nums">{counts[v]}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

interface RateRow {
  label: string
  partisan: number
  total: number
  partisan_rate: number
}

function PartisanRatePanel({ title, rows }: { title: string; rows: RateRow[] }) {
  if (rows.length === 0) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-sm">
      <div className="px-4 py-2 border-b border-gray-700 eyebrow">{title}</div>
      <div className="p-4 space-y-2">
        {rows.map((r) => {
          const pct = Math.round((r.partisan_rate ?? 0) * 100)
          return (
            <div key={r.label} className="flex items-center gap-3">
              <div className="w-24 shrink-0 font-mono text-xs text-gray-400 truncate" title={r.label}>
                {r.label}
              </div>
              <div className="flex-1 bg-gray-900 border border-gray-700 rounded-sm h-2.5 overflow-hidden">
                <div className="bg-orange-500 h-full" style={{ width: `${pct}%` }} />
              </div>
              <div className="w-24 shrink-0 text-right font-mono text-xs text-gray-400 tabular-nums">
                {pct}% ({r.partisan}/{r.total})
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const toRows = (stats: (BiasSourceStat | BiasReporterStat)[]): RateRow[] =>
  stats.map((s) => ({
    label: 'reporter' in s ? s.reporter : s.source_site,
    partisan: s.partisan,
    total: s.total,
    partisan_rate: s.partisan_rate,
  }))

function MediaCounts({ articles }: { articles: BiasCluster['articles'] }) {
  const counts = new Map<string, { total: number; side_a: number; neutral: number; side_b: number }>()
  for (const a of articles) {
    let c = counts.get(a.source_site)
    if (!c) {
      c = { total: 0, side_a: 0, neutral: 0, side_b: 0 }
      counts.set(a.source_site, c)
    }
    c.total++
    if (a.verdict in c) c[a.verdict as Verdict]++
  }
  const sorted = [...counts.entries()].sort((a, b) => b[1].total - a[1].total)
  if (sorted.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5">
      {sorted.map(([site, c]) => (
        <span
          key={site}
          className="font-mono text-xs bg-gray-700 text-gray-300 rounded-sm px-2 py-0.5 flex items-center gap-1.5"
          title={`${site}：偏A方 ${c.side_a}、中立 ${c.neutral}、偏B方 ${c.side_b}`}
        >
          <span>{site}</span>
          <span className="text-gray-50 font-medium tabular-nums">{c.total}</span>
          <span className="flex items-center gap-1 text-[10px]">
            {VERDICTS.map((v) =>
              c[v] > 0 ? (
                <span key={v} className={VERDICT[v].text}>
                  {VERDICT[v].label.replace('方', '')}{c[v]}
                </span>
              ) : null
            )}
          </span>
        </span>
      ))}
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
    <div className="bg-gray-800 border border-gray-700 rounded-sm p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-gray-50 leading-snug">{cluster.cluster_label}</div>
          {hasSides ? (
            <div className="font-mono text-xs text-gray-500 mt-1">
              A：<span style={{ color: BIAS_A }}>{cluster.side_a}</span>
              {'  ｜  '}
              B：<span style={{ color: BIAS_B }}>{cluster.side_b}</span>
            </div>
          ) : (
            <div className="font-mono text-xs text-gray-600 mt-1">資訊型主題（無對立立場）</div>
          )}
        </div>
        <div className="flex flex-col items-end shrink-0 font-mono">
          <span className="text-xs text-gray-500 tabular-nums">{cluster.article_count} 篇</span>
          {cluster.run_date && (
            <span className="text-[10px] text-gray-600 mt-0.5 tabular-nums">{cluster.run_date}</span>
          )}
        </div>
      </div>

      <BiasBar articles={cluster.articles} />

      <div className="space-y-1.5">
        <div className="eyebrow">各媒體報導數</div>
        <MediaCounts articles={cluster.articles} />
      </div>

      <button
        onClick={() => setExpanded((e) => !e)}
        className="font-mono text-xs text-gray-500 hover:text-gray-200 transition-colors inline-flex items-center gap-1"
      >
        {expanded ? <><FiChevronUp aria-hidden /> 收合</> : <><FiChevronDown aria-hidden /> 展開文章</>}
      </button>

      {expanded && (
        <div className="space-y-3 pt-1">
          {VERDICTS.map((v) =>
            grouped[v].length > 0 ? (
              <div key={v}>
                <div className={`font-mono text-xs font-semibold mb-1.5 ${VERDICT[v].text}`}>
                  {VERDICT[v].label}（{grouped[v].length}）
                </div>
                <div className="space-y-2">
                  {grouped[v].map((a) => (
                    <div key={a.id} className="border-l-2 border-gray-600 pl-3 space-y-0.5">
                      <a
                        href={a.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-gray-200 hover:text-blue-400 leading-snug block transition-colors"
                      >
                        {a.title}
                      </a>
                      <div className="font-mono text-xs text-gray-500">
                        {a.source_site}
                        {a.publish_date ? ` · ${a.publish_date}` : ''}
                      </div>
                      {a.reasoning && (
                        <div className="text-xs text-gray-400 italic leading-relaxed">{a.reasoning}</div>
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
  const [reporterStats, setReporterStats] = useState<BiasReporterStat[]>([])
  const [runDate, setRunDate] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')
  const [days, setDays] = useState(7)

  // Fetch lives inside the effect (same shape as TopicStats): a useCallback
  // called straight from the effect body trips react-hooks/set-state-in-effect.
  // `stale` drops a slow response whose window the user already moved past.
  useEffect(() => {
    let stale = false

    async function load() {
      setLoading(true)
      setError('')
      try {
        const report = await newsApi.bias({ dateFrom: isoDaysAgo(days), dateTo: todayIso() })
        if (stale) return
        setRunDate(report.runDate)
        setClusters(report.clusters)
        setSourceStats(report.sourceStats)
        setReporterStats(report.reporterStats)
      } catch (e) {
        if (stale) return
        setError(`載入失敗: ${errorMessage(e)}`)
      } finally {
        if (!stale) {
          setLoading(false)
          setLoaded(true)
        }
      }
    }

    load()
    return () => {
      stale = true
    }
  }, [days])

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 border border-gray-700 rounded-sm p-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="eyebrow">Window</span>
          <div className="inline-flex rounded-sm border border-gray-700 overflow-hidden">
            {DAY_OPTIONS.map((d, i) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                disabled={loading}
                className={`px-3 py-1 text-xs font-mono transition-colors disabled:opacity-40 ${i > 0 ? 'border-l border-gray-700' : ''} ${
                  days === d ? 'bg-blue-500/15 text-blue-400' : 'text-gray-500 hover:text-gray-200 hover:bg-gray-700/60'
                }`}
              >
                {d}D
              </button>
            ))}
          </div>
        </div>
        <span className="font-mono text-xs text-gray-500">
          {loading ? '載入中…' : runDate ? `latest ${runDate}` : ''}
        </span>
      </div>

      <ErrorBanner msg={error} />

      <PartisanRatePanel title="媒體黨派率 / Partisan rate" rows={toRows(sourceStats)} />

      <PartisanRatePanel title="記者黨派率 / Reporter partisan rate" rows={toRows(reporterStats)} />

      {!loading && loaded && clusters.length === 0 && (
        <div className="text-gray-500 font-mono text-sm text-center py-12">此區間尚無分析資料</div>
      )}

      <div className="space-y-3">
        {clusters.map((c) => (
          <ClusterCard key={`${c.run_date}-${c.id}`} cluster={c} />
        ))}
      </div>
    </div>
  )
}
