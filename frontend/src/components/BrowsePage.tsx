import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import type { NewsArticle } from '../types'
import { Field, selectCls, btnPrimary, btnGhost } from './ui'

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
          <div className="space-y-2">
            {articles.map((a) => (
              <div key={a.id} className="bg-gray-800 border border-gray-700 rounded-sm p-3 flex flex-col gap-1.5 hover:border-gray-600 transition-colors">
                <a href={a.source_url} target="_blank" rel="noopener noreferrer"
                  className="text-gray-100 hover:text-blue-400 font-medium text-sm leading-snug transition-colors">
                  {a.title}
                </a>
                <div className="flex gap-3 font-mono text-xs text-gray-500">
                  <span className="text-gray-400">{a.publish_date}</span>
                  <span className="text-gray-600">·</span>
                  <span>{a.source_site}</span>
                  {a.reporter && <><span className="text-gray-600">·</span><span>{a.reporter}</span></>}
                </div>
              </div>
            ))}
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
