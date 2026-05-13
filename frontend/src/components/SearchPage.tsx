import { useState } from 'react'
import { supabase } from '../lib/supabase'
import type { SearchResult } from '../types'

type SearchField = 'title' | 'summary' | 'both'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(10)
  const [searchField, setSearchField] = useState<SearchField>('both')
  const [source, setSource] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function search() {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setResults([])

    const { data, error: fnErr } = await supabase.functions.invoke<{ results: SearchResult[] }>('search', {
      body: {
        query: query.trim(),
        top_k: topK,
        search_field: searchField,
        source: source || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      },
    })

    setLoading(false)
    if (fnErr) {
      setError(`搜尋失敗: ${fnErr.message}`)
    } else if (data?.results) {
      setResults(data.results)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
            placeholder="輸入搜尋關鍵字..."
            className="flex-1 bg-gray-700 text-white rounded px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button onClick={search} disabled={loading || !query.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-4 py-2 rounded text-sm">
            {loading ? '搜尋中...' : '搜尋'}
          </button>
        </div>

        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">搜尋欄位</label>
            <select value={searchField} onChange={(e) => setSearchField(e.target.value as SearchField)}
              className="bg-gray-700 text-white rounded px-2 py-1 text-sm">
              <option value="both">標題 + 摘要</option>
              <option value="title">標題</option>
              <option value="summary">摘要</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">結果數 ({topK})</label>
            <input type="range" min={5} max={50} step={5} value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-24" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">來源</label>
            <input type="text" value={source} onChange={(e) => setSource(e.target.value)}
              placeholder="全部"
              className="bg-gray-700 text-white rounded px-2 py-1 text-sm w-24" />
          </div>
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
        </div>
      </div>

      {error && <div className="text-red-400 text-sm bg-red-900/20 rounded p-3">{error}</div>}

      {results.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm text-gray-400">找到 {results.length} 篇相關文章</div>
          {results.map((r, i) => (
            <div key={r.id} className="bg-gray-800 rounded-lg p-3 flex gap-3">
              <div className="text-gray-500 text-xs pt-0.5 w-5 shrink-0">{i + 1}</div>
              <div className="flex-1 space-y-1">
                <a href={r.source_url} target="_blank" rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 font-medium text-sm leading-snug block">
                  {r.title}
                </a>
                <div className="flex gap-3 text-xs text-gray-400 flex-wrap">
                  <span>{r.publish_date}</span>
                  <span>{r.source_site}</span>
                  {r.reporter && <span>{r.reporter}</span>}
                  <span className="text-green-400">相似度 {(r.similarity * 100).toFixed(1)}%</span>
                </div>
                {r.summary && (
                  <p className="text-gray-300 text-xs leading-relaxed line-clamp-2">{r.summary}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
