import { useState } from 'react'
import { FiSearch } from 'react-icons/fi'
import { supabase } from '../lib/supabase'
import type { SearchResult } from '../types'
import { Field, inputCls, selectCls, btnPrimary } from './ui'

type SearchField = 'title' | 'summary' | 'both'

// Similarity as a signal-strength readout — bars fill with match strength.
function SignalMeter({ value }: { value: number }) {
  const bars = 5
  const on = Math.max(0, Math.min(bars, Math.round(value * bars)))
  return (
    <span className="inline-flex items-center gap-1.5" title={`相似度 ${(value * 100).toFixed(1)}%`}>
      <span className="inline-flex items-end gap-px h-3" aria-hidden>
        {Array.from({ length: bars }, (_, i) => (
          <span
            key={i}
            className={`w-1 rounded-[1px] ${i < on ? 'bg-blue-400' : 'bg-gray-600'}`}
            style={{ height: `${((i + 1) / bars) * 100}%` }}
          />
        ))}
      </span>
      <span className="font-mono text-xs text-blue-400 tabular-nums">{(value * 100).toFixed(1)}%</span>
    </span>
  )
}

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
      <div className="bg-gray-800 border border-gray-700 rounded-sm p-4 space-y-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <FiSearch size={15} aria-hidden className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && search()}
              placeholder="語意搜尋關鍵字…"
              className={inputCls + ' w-full pl-9'}
            />
          </div>
          <button onClick={search} disabled={loading || !query.trim()} className={btnPrimary}>
            {loading ? '搜尋中…' : '搜尋'}
          </button>
        </div>

        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Field">
            <select value={searchField} onChange={(e) => setSearchField(e.target.value as SearchField)} className={selectCls}>
              <option value="both">標題 + 摘要</option>
              <option value="title">標題</option>
              <option value="summary">摘要</option>
            </select>
          </Field>
          <Field label={`Top K · ${topK}`}>
            <input type="range" min={5} max={50} step={5} value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-28 accent-blue-500 h-8" />
          </Field>
          <Field label="Source">
            <input type="text" value={source} onChange={(e) => setSource(e.target.value)}
              placeholder="全部" className={inputCls + ' w-28'} />
          </Field>
          <Field label="From">
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={selectCls} />
          </Field>
          <Field label="To">
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={selectCls} />
          </Field>
        </div>
      </div>

      {error && <div className="text-red-400 text-sm font-mono bg-red-900/20 border border-red-900/50 rounded-sm p-3">{error}</div>}

      {results.length > 0 && (
        <div className="space-y-2">
          <div className="eyebrow">{results.length} results</div>
          {results.map((r, i) => (
            <div key={r.id} className="bg-gray-800 border border-gray-700 rounded-sm p-3 flex gap-3 hover:border-gray-600 transition-colors">
              <div className="font-mono text-gray-600 text-xs pt-0.5 w-6 shrink-0 tabular-nums text-right">{String(i + 1).padStart(2, '0')}</div>
              <div className="flex-1 min-w-0 space-y-1.5">
                <a href={r.source_url} target="_blank" rel="noopener noreferrer"
                  className="text-gray-100 hover:text-blue-400 font-medium text-sm leading-snug block transition-colors">
                  {r.title}
                </a>
                <div className="flex gap-3 items-center font-mono text-xs text-gray-500 flex-wrap">
                  <span className="text-gray-400">{r.publish_date}</span>
                  <span className="text-gray-600">·</span>
                  <span>{r.source_site}</span>
                  {r.reporter && <><span className="text-gray-600">·</span><span>{r.reporter}</span></>}
                  <span className="ml-auto"><SignalMeter value={r.similarity} /></span>
                </div>
                {r.summary && (
                  <p className="text-gray-400 text-xs leading-relaxed line-clamp-2">{r.summary}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
