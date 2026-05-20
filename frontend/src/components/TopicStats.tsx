import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip,
  LineChart, Line, CartesianGrid, ResponsiveContainer,
} from 'recharts'

interface DailyCount {
  publish_date: string
  count: number
}

interface SourceCount {
  source_site: string
  count: number
}

const COLORS = ['#60a5fa', '#34d399', '#f87171', '#fbbf24', '#a78bfa', '#f472b6']

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

      const [{ data: dailyData }, { data: siteData }] = await Promise.all([
        supabase
          .from('news_articles')
          .select('publish_date, count:id.count()')
          .gte('publish_date', sinceStr)
          .order('publish_date', { ascending: true }),
        supabase
          .from('news_articles')
          .select('source_site, count:id.count()')
          .gte('publish_date', sinceStr),
      ])

      if (!dailyData || !siteData) { setLoading(false); return }

      const daily = (dailyData as { publish_date: string; count: number }[])
      const bysite = (siteData as { source_site: string; count: number }[])
        .sort((a, b) => b.count - a.count)

      const total = daily.reduce((s, r) => s + Number(r.count), 0)
      const minDate = daily[0]?.publish_date ?? ''
      const maxDate = daily[daily.length - 1]?.publish_date ?? ''

      setTotalArticles(total)
      setDateRange({ min: minDate, max: maxDate })
      setDaily(daily.map(r => ({ publish_date: r.publish_date, count: Number(r.count) })))
      setBySite(bysite.map(r => ({ source_site: r.source_site, count: Number(r.count) })))
      setLoading(false)
    }
    load()
  }, [days])

  if (loading) return <div className="text-gray-400 text-center py-12">載入統計中...</div>

  return (
    <div className="space-y-8">
      <div className="flex justify-end gap-2">
        {DAY_OPTIONS.map(d => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1 rounded text-sm ${days === d ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
          >
            近 {d} 天
          </button>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-blue-400">{totalArticles.toLocaleString()}</div>
          <div className="text-sm text-gray-400 mt-1">總文章數</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-green-400">{bySite.length}</div>
          <div className="text-sm text-gray-400 mt-1">來源數量</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 text-center">
          <div className="text-lg font-bold text-yellow-400">{dateRange.min}</div>
          <div className="text-xs text-gray-400">至</div>
          <div className="text-lg font-bold text-yellow-400">{dateRange.max}</div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">每日文章數量</h3>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={daily}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="publish_date" tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
            <Line type="monotone" dataKey="count" stroke="#60a5fa" dot={false} strokeWidth={2} name="篇數" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">各來源文章數</h3>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={bySite}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="source_site" tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
            <Bar dataKey="count" name="篇數">
              {bySite.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
