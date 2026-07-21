import { useState, useEffect } from 'react'
import type { IconType } from 'react-icons'
import { FiBarChart2, FiSearch, FiBookOpen, FiShare2, FiAlertTriangle, FiSun, FiMoon } from 'react-icons/fi'
import { LuScale } from 'react-icons/lu'
import TopicStats from './components/TopicStats'
import SearchPage from './components/SearchPage'
import BrowsePage from './components/BrowsePage'
import GraphPage from './components/GraphPage'
import BiasPage from './components/BiasPage'
import { supabase, supabaseConfigured } from './lib/supabase'
import { useTheme } from './lib/theme'

type TabId = 'stats' | 'search' | 'browse' | 'graph' | 'bias'

const TABS: { id: TabId; label: string; code: string; Icon: IconType }[] = [
  { id: 'stats',  label: '主題統計', code: 'STAT', Icon: FiBarChart2 },
  { id: 'search', label: '搜尋',     code: 'SRCH', Icon: FiSearch },
  { id: 'browse', label: '瀏覽',     code: 'BRWS', Icon: FiBookOpen },
  { id: 'graph',  label: '關聯圖譜', code: 'GRPH', Icon: FiShare2 },
  { id: 'bias',   label: '偏頗分析', code: 'BIAS', Icon: LuScale },
]

// Signature: a live wire status strip reading the system's real telemetry.
function useTelemetry() {
  const [t, setT] = useState<{ sources?: number; latest?: string; total?: number }>({})
  useEffect(() => {
    if (!supabaseConfigured) return
    let alive = true
    ;(async () => {
      const [src, total, latest] = await Promise.all([
        supabase.rpc('get_distinct_sources'),
        supabase.from('news_articles').select('id', { count: 'exact', head: true }),
        supabase.from('news_articles').select('publish_date').order('publish_date', { ascending: false }).limit(1),
      ])
      if (!alive) return
      setT({
        sources: Array.isArray(src.data) ? src.data.length : undefined,
        total: total.count ?? undefined,
        latest: (latest.data?.[0] as { publish_date?: string } | undefined)?.publish_date,
      })
    })()
    return () => { alive = false }
  }, [])
  return t
}

function Reading({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="eyebrow">{label}</span>
      <span className="font-mono text-xs text-gray-200">{value}</span>
    </span>
  )
}

function StatusStrip() {
  const { sources, latest, total } = useTelemetry()
  const dash = '—'
  return (
    <div className="hidden md:flex items-center gap-4">
      <Reading label="Sources" value={sources != null ? String(sources) : dash} />
      <span className="text-gray-600">·</span>
      <Reading label="Latest" value={latest ?? dash} />
      <span className="text-gray-600">·</span>
      <Reading label="Dispatches" value={total != null ? total.toLocaleString() : dash} />
      <span className="text-gray-600">·</span>
      <span className="flex items-center gap-1.5">
        <span className="live-dot" aria-hidden />
        <span className="eyebrow text-blue-400">{supabaseConfigured ? 'Live' : 'Offline'}</span>
      </span>
    </div>
  )
}

function ThemeToggle({ theme, onToggle }: { theme: 'light' | 'dark'; onToggle: () => void }) {
  const toDark = theme === 'light'
  return (
    <button
      onClick={onToggle}
      aria-label={toDark ? '切換為暗色模式' : '切換為亮色模式'}
      title={toDark ? '暗色模式' : '亮色模式'}
      className="p-1.5 rounded-sm text-gray-400 hover:text-gray-50 hover:bg-gray-700 transition-colors"
    >
      {toDark ? <FiMoon size={16} aria-hidden /> : <FiSun size={16} aria-hidden />}
    </button>
  )
}

export default function App() {
  const [tab, setTab] = useState<TabId>('stats')
  const { theme, toggle } = useTheme()

  return (
    <div className="min-h-screen bg-gray-900 text-gray-300 font-sans">
      <header>
        <div className="max-w-6xl mx-auto px-5 pt-4 pb-3 flex items-baseline justify-between gap-4">
          <div className="flex items-baseline gap-3">
            <h1 className="text-lg font-semibold tracking-tight text-gray-50">新聞分析</h1>
            <span className="eyebrow">Signal · Monitor</span>
          </div>
          <div className="flex items-center gap-4">
            <StatusStrip />
            <ThemeToggle theme={theme} onToggle={toggle} />
          </div>
        </div>
        {/* signal rule */}
        <div className="h-px bg-blue-500/50" />
        <nav className="max-w-6xl mx-auto px-3 flex gap-1 overflow-x-auto border-b border-gray-700">
          {TABS.map((t) => {
            const active = tab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                aria-current={active ? 'page' : undefined}
                className={`group px-3 py-2.5 text-sm inline-flex items-center gap-2 border-b-2 -mb-px transition-colors whitespace-nowrap ${
                  active
                    ? 'border-blue-500 text-gray-50'
                    : 'border-transparent text-gray-500 hover:text-gray-200'
                }`}
              >
                <t.Icon size={14} aria-hidden className={active ? 'text-blue-400' : ''} />
                <span>{t.label}</span>
                <span className={`eyebrow ${active ? 'text-blue-400/70' : 'text-gray-600 group-hover:text-gray-500'}`}>{t.code}</span>
              </button>
            )
          })}
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-5 py-6">
        {!supabaseConfigured && (
          <div className="mb-5 bg-yellow-900/40 border border-yellow-600/60 rounded-sm p-4 text-sm text-yellow-300">
            <div className="font-semibold mb-1 flex items-center gap-1.5"><FiAlertTriangle size={16} aria-hidden /> 尚未設定 Supabase 憑證</div>
            <div>在 <code className="font-mono bg-yellow-900/60 px-1 rounded-sm">.env</code> 加入以下變數後重建 container：</div>
            <pre className="mt-2 font-mono bg-yellow-900/60 rounded-sm p-2 text-xs text-yellow-200">
{`VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key`}
            </pre>
            <div className="mt-2 text-xs text-yellow-400">然後執行：<code className="font-mono bg-yellow-900/60 px-1 rounded-sm">docker compose build frontend &amp;&amp; docker compose up -d frontend</code></div>
          </div>
        )}
        {tab === 'stats' && <TopicStats />}
        {tab === 'search' && <SearchPage />}
        {tab === 'browse' && <BrowsePage />}
        {tab === 'graph' && <GraphPage />}
        {tab === 'bias' && <BiasPage />}
      </main>
    </div>
  )
}
