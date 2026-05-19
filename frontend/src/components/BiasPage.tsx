import { useState } from 'react'
import { supabase } from '../lib/supabase'
import type { BiasCluster } from '../types'

const VERDICTS = ['side_a', 'neutral', 'side_b'] as const
type Verdict = typeof VERDICTS[number]

const VERDICT: Record<Verdict, { label: string; bar: string; text: string }> = {
  side_a:  { label: '偏A方', bar: 'bg-blue-500',   text: 'text-blue-400' },
  neutral: { label: '中立',  bar: 'bg-gray-400',   text: 'text-gray-400' },
  side_b:  { label: '偏B方', bar: 'bg-orange-500', text: 'text-orange-400' },
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

function ClusterCard({ cluster }: { cluster: BiasCluster }) {
  const [expanded, setExpanded] = useState(false)

  const grouped = {
    side_a: cluster.articles.filter((a) => a.verdict === 'side_a'),
    neutral: cluster.articles.filter((a) => a.verdict === 'neutral'),
    side_b: cluster.articles.filter((a) => a.verdict === 'side_b'),
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium text-white">{cluster.cluster_label}</div>
          <div className="text-xs text-gray-400 mt-0.5">
            A方：<span className="text-blue-400">{cluster.side_a}</span>
            {' '}｜{' '}
            B方：<span className="text-orange-400">{cluster.side_b}</span>
          </div>
        </div>
        <span className="text-xs text-gray-500 shrink-0">{cluster.article_count} 篇</span>
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
  const [runDate, setRunDate] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')

    const { data, error: fnErr } = await supabase.functions.invoke<{
      run_date: string | null
      clusters: BiasCluster[]
    }>('bias', { body: {} })

    setLoading(false)
    if (fnErr) {
      setError(`載入失敗: ${fnErr.message}`)
    } else if (data) {
      setRunDate(data.run_date)
      setClusters(data.clusters ?? [])
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 rounded-lg p-4 flex items-center gap-4">
        <button
          onClick={load}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white px-4 py-1.5 rounded text-sm"
        >
          {loading ? '載入中...' : '⚖️ 載入偏頗分析'}
        </button>
        {runDate && (
          <span className="text-xs text-gray-400">最新分析日期：{runDate}</span>
        )}
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-900/20 rounded p-3">{error}</div>
      )}

      {!loading && clusters.length === 0 && runDate === null && (
        <div className="text-gray-400 text-center py-12">點「載入偏頗分析」查看最新結果</div>
      )}

      {!loading && clusters.length === 0 && runDate !== null && (
        <div className="text-gray-400 text-center py-12">尚無分析資料</div>
      )}

      <div className="space-y-3">
        {clusters.map((c) => (
          <ClusterCard key={c.id} cluster={c} />
        ))}
      </div>
    </div>
  )
}
