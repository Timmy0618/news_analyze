import { useState } from 'react'
import type { IconType } from 'react-icons'
import { FiBarChart2, FiSearch, FiBookOpen, FiShare2, FiAlertTriangle } from 'react-icons/fi'
import { LuScale } from 'react-icons/lu'
import TopicStats from './components/TopicStats'
import SearchPage from './components/SearchPage'
import BrowsePage from './components/BrowsePage'
import GraphPage from './components/GraphPage'
import BiasPage from './components/BiasPage'
import { supabaseConfigured } from './lib/supabase'

type TabId = 'stats' | 'search' | 'browse' | 'graph' | 'bias'

const TABS: { id: TabId; label: string; Icon: IconType }[] = [
  { id: 'stats', label: '主題統計', Icon: FiBarChart2 },
  { id: 'search', label: '搜尋', Icon: FiSearch },
  { id: 'browse', label: '瀏覽', Icon: FiBookOpen },
  { id: 'graph', label: '關聯圖譜', Icon: FiShare2 },
  { id: 'bias', label: '偏頗分析', Icon: LuScale },
]

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
              className={`px-3 py-1.5 rounded text-sm transition-colors inline-flex items-center gap-1.5 ${
                tab === t.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
            >
              <t.Icon size={15} aria-hidden />
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-6">
        {!supabaseConfigured && (
          <div className="mb-4 bg-yellow-900/40 border border-yellow-600 rounded-lg p-4 text-sm text-yellow-300">
            <div className="font-semibold mb-1 flex items-center gap-1.5"><FiAlertTriangle size={16} aria-hidden /> 尚未設定 Supabase 憑證</div>
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
