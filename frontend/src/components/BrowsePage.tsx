import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import type { NewsArticle } from '../types'
import { Field, selectCls, inputCls, btnPrimary, btnGhost } from './ui'

const PAGE_SIZE = 50

export default function BrowsePage() {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [sources, setSources] = useState<string[]>([])

  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [source, setSource] = useState('')
  const [reporter, setReporter] = useState('')
  const [sortBy, setSortBy] = useState<'publish_date' | 'source_site'>('publish_date')

  useEffect(() => {
    // 用伺服器端 RPC 取得不重複來源，避免把全表的 source_site 拉到前端（省 egress）
    supabase
      .rpc('get_distinct_sources')
      .then(({ data }) => {
        if (data) setSources(data as string[])
      })
  }, [])

  async function load(p = 0) {
    setLoading(true)
    let q = supabase
      .from('news_articles')
      .select('id,title,source_url,source_site,publish_date,reporter', { count: 'exact' })
      .order(sortBy, { ascending: false })
      .range(p * PAGE_SIZE, p * PAGE_SIZE + PAGE_SIZE - 1)

    if (dateFrom) q = q.gte('publish_date', dateFrom)
    if (dateTo) q = q.lte('publish_date', dateTo)
    if (source) q = q.eq('source_site', source)
    if (reporter.trim()) q = q.ilike('reporter', `%${reporter.trim()}%`)

    const { data, count, error } = await q
    setLoading(false)
    if (!error && data) {
      setArticles(data as NewsArticle[])
      setTotal(count ?? 0)
      setPage(p)
    }
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4 items-end bg-gray-800 border border-gray-700 rounded-sm p-4">
        <Field label="From">
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={selectCls} />
        </Field>
        <Field label="To">
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={selectCls} />
        </Field>
        <Field label="Source">
          <select value={source} onChange={(e) => setSource(e.target.value)} className={selectCls}>
            <option value="">全部</option>
            {sources.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Reporter">
          <input
            type="search"
            value={reporter}
            onChange={(e) => setReporter(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load(0)}
            placeholder="記者名字"
            className={inputCls}
          />
        </Field>
        <Field label="Sort">
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} className={selectCls}>
            <option value="publish_date">日期</option>
            <option value="source_site">來源</option>
          </select>
        </Field>
        <button onClick={() => load(0)} className={btnPrimary}>套用篩選</button>
      </div>

      {loading && <div className="text-gray-500 font-mono text-sm text-center py-8">載入中…</div>}

      {!loading && articles.length === 0 && (
        <div className="text-gray-500 font-mono text-sm text-center py-8">按「套用篩選」開始瀏覽</div>
      )}

      {articles.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <span className="eyebrow">{total.toLocaleString()} dispatches</span>
            <span className="eyebrow">page {page + 1} / {pages}</span>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-sm overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-gray-600">
                  <th className="text-left px-4 py-2.5"><span className="eyebrow">標題</span></th>
                  <th className="text-left px-4 py-2.5 whitespace-nowrap"><span className="eyebrow">來源</span></th>
                  <th className="text-left px-4 py-2.5 whitespace-nowrap"><span className="eyebrow">記者</span></th>
                  <th className="text-right px-4 py-2.5 whitespace-nowrap"><span className="eyebrow">日期</span></th>
                </tr>
              </thead>
              <tbody>
                {articles.map((a) => (
                  <tr key={a.id} className="border-b border-gray-700 last:border-0 hover:bg-gray-700/60 transition-colors">
                    <td className="px-4 py-2.5">
                      <a href={a.source_url} target="_blank" rel="noopener noreferrer"
                        className="text-gray-100 hover:text-blue-400 font-medium leading-snug transition-colors">
                        {a.title}
                      </a>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-400 whitespace-nowrap">{a.source_site}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-400 whitespace-nowrap">{a.reporter || '—'}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-500 text-right whitespace-nowrap">{a.publish_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2 justify-center pt-2">
            <button disabled={page === 0} onClick={() => load(page - 1)} className={btnGhost}>上一頁</button>
            <button disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => load(page + 1)} className={btnGhost}>下一頁</button>
          </div>
        </>
      )}
    </div>
  )
}
