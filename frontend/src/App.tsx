import { useState } from 'react'
import TopicStats from './components/TopicStats'
import SearchPage from './components/SearchPage'
import BrowsePage from './components/BrowsePage'
import GraphPage from './components/GraphPage'

const TABS = [
  { id: 'stats', label: '📈 主題統計' },
  { id: 'search', label: '🔍 搜尋' },
  { id: 'browse', label: '📚 瀏覽' },
  { id: 'graph', label: '🕸️ 關聯圖譜' },
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
        {tab === 'stats' && <TopicStats />}
        {tab === 'search' && <SearchPage />}
        {tab === 'browse' && <BrowsePage />}
        {tab === 'graph' && <GraphPage />}
      </main>
    </div>
  )
}
