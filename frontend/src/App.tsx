import { useState } from 'react'
import TopicStats from './components/TopicStats'
import SearchPage from './components/SearchPage'
import BrowsePage from './components/BrowsePage'
import GraphPage from './components/GraphPage'
import BiasPage from './components/BiasPage'
import { supabaseConfigured } from './lib/supabase'

const TABS = [
  { id: 'stats', label: '📈 主題統計' },
  { id: 'search', label: '🔍 搜尋' },
  { id: 'browse', label: '📚 瀏覽' },
  { id: 'graph', label: '🕸️ 關聯圖譜' },
  { id: 'bias', label: '⚖️ 偏頗分析' },
] as const

type TabId = typeof TABS[number]['id']

export default function App() {
  const [tab, setTab] = useState<TabId>('stats')

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="border-b border-gray-700 px-6 py-3 flex items-center gap-6">
        <h1 className="text-lg font-semibold text-white">新聞分析</h1>
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                tab === t.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-6">
        {!supabaseConfigured && (
          <div className="mb-4 bg-yellow-900/40 border border-yellow-600 rounded-lg p-4 text-sm text-yellow-300">
            <div className="font-semibold mb-1">⚠️ 尚未設定 Supabase 憑證</div>
            <div>在 <code className="bg-yellow-900/60 px-1 rounded">.env</code> 加入以下變數後重建 container：</div>
            <pre className="mt-2 bg-yellow-900/60 rounded p-2 text-xs text-yellow-200">
{`VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key`}
            </pre>
            <div className="mt-2 text-xs text-yellow-400">然後執行：<code className="bg-yellow-900/60 px-1 rounded">docker compose build frontend && docker compose up -d frontend</code></div>
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
