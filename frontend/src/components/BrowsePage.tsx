import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import type { NewsArticle } from '../types'

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
    supabase
      .from('news_articles')
      .select('source_site')
      .then(({ data }) => {
        if (data) {
          const unique = [...new Set(data.map((r) => r.source_site as string))].sort()
          setSources(unique)
        }
      })
  }, [])

  async function load(p = 0) {
    setLoading(true)
    let q = supabase
      .from('news_articles')
      .select('id,title,summary,source_url,source_site,publish_date,reporter', { count: 'exact' })
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-end bg-gray-800 p-4 rounded-lg">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">開始日期</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
            className="bg-gray-700 text-white rounded px-2 py-1 text-sm" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">結束日期</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
            className="bg-gray-700 text-white rounded px-2 py-1 text-sm" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">來源</label>
          <select value={source} onChange={(e) => setSource(e.target.value)}
            className="bg-gray-700 text-white rounded px-2 py-1 text-sm">
            <option value="">全部</option>
            {sources.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">排序</label>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="bg-gray-700 text-white rounded px-2 py-1 text-sm">
            <option value="publish_date">日期</option>
            <option value="source_site">來源</option>
          </select>
        </div>
        <button onClick={() => load(0)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded text-sm">
          套用篩選
        </button>
      </div>

      {loading && <div className="text-gray-400 text-center py-8">載入中...</div>}

      {!loading && articles.length === 0 && (
        <div className="text-gray-400 text-center py-8">按「套用篩選」開始瀏覽</div>
      )}

      {articles.length > 0 && (
        <>
          <div className="text-sm text-gray-400">共 {total} 篇文章，第 {page + 1} 頁</div>
          <div className="space-y-2">
            {articles.map((a) => (
              <div key={a.id} className="bg-gray-800 rounded-lg p-3 flex flex-col gap-1">
                <a href={a.source_url} target="_blank" rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 font-medium text-sm leading-snug">
                  {a.title}
                </a>
                <div className="flex gap-3 text-xs text-gray-400">
                  <span>{a.publish_date}</span>
                  <span>{a.source_site}</span>
                  {a.reporter && <span>{a.reporter}</span>}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2 justify-center pt-2">
            <button disabled={page === 0} onClick={() => load(page - 1)}
              className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-40">上一頁</button>
            <button disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => load(page + 1)}
              className="px-3 py-1 bg-gray-700 rounded text-sm disabled:opacity-40">下一頁</button>
          </div>
        </>
      )}
    </div>
  )
}
