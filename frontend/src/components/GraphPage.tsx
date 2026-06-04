import { useState, useCallback, useRef } from 'react'
import { FiShare2, FiFileText } from 'react-icons/fi'
import { supabase } from '../lib/supabase'
import type { GraphData, GraphNode } from '../types'
import ForceGraph2D from 'react-force-graph-2d'

// Editorial Ink data-viz palette (warm, distinct on graphite).
const PALETTE = ['#eab308', '#dc2626', '#2563eb', '#0d9488', '#c2851a', '#ea580c', '#84cc16', '#a8a29e']

export default function GraphPage() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [source, setSource] = useState('')
  const [maxNodes, setMaxNodes] = useState(100)
  const [k, setK] = useState(10)
  const sourceColors = useRef<Record<string, string>>({})

  function colorForSource(site: string): string {
    if (!sourceColors.current[site]) {
      const idx = Object.keys(sourceColors.current).length
      sourceColors.current[site] = PALETTE[idx % PALETTE.length]
    }
    return sourceColors.current[site]
  }

  async function buildGraph() {
    setLoading(true)
    setError('')
    setSelectedNode(null)
    sourceColors.current = {}

    const { data, error: fnErr } = await supabase.functions.invoke<{
      nodes: GraphNode[]
      edges: { source: string; target: string; weight: number }[]
    }>('graph', {
      body: {
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        source: source || undefined,
        max_nodes: maxNodes,
        k,
      },
    })

    setLoading(false)
    if (fnErr) {
      setError(`建立圖譜失敗: ${fnErr.message}`)
    } else if (data) {
      setGraphData({ nodes: data.nodes, links: data.edges })
    }
  }

  const handleNodeClick = useCallback((node: object) => {
    setSelectedNode(node as GraphNode)
  }, [])

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 rounded-lg p-4 flex flex-wrap gap-3 items-end">
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
          <input type="text" value={source} onChange={(e) => setSource(e.target.value)}
            placeholder="全部" className="bg-gray-700 text-white rounded px-2 py-1 text-sm w-24" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">節點數上限 ({maxNodes})</label>
          <input type="range" min={20} max={200} step={10} value={maxNodes}
            onChange={(e) => setMaxNodes(Number(e.target.value))}
            className="w-28" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-400">主題數 K ({k})</label>
          <input type="range" min={5} max={20} step={1} value={k}
            onChange={(e) => setK(Number(e.target.value))}
            className="w-28" />
        </div>
        <button onClick={buildGraph} disabled={loading}
          className="bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white px-4 py-1.5 rounded text-sm inline-flex items-center gap-1.5">
          {loading ? '計算中...' : <><FiShare2 size={14} aria-hidden /> 建立圖譜</>}
        </button>
      </div>

      {error && <div className="text-red-400 text-sm bg-red-900/20 rounded p-3">{error}</div>}

      {graphData && (
        <div className="flex gap-4">
          <div className="flex-1 bg-gray-900 rounded-lg overflow-hidden" style={{ height: 560 }}>
            <ForceGraph2D
              graphData={graphData}
              nodeLabel={(n) => {
                const node = n as GraphNode
                return `${node.title} (${node.article_count} 篇)`
              }}
              nodeColor={(n) => colorForSource((n as GraphNode).source_site)}
              nodeVal={(n) => (n as GraphNode).article_count}
              nodeRelSize={4}
              linkColor={() => 'rgba(255,255,255,0.15)'}
              backgroundColor="#15140e"
              onNodeClick={handleNodeClick}
            />
          </div>

          {selectedNode && (
            <div className="w-72 bg-gray-800 rounded-lg p-4 text-sm space-y-3 shrink-0 overflow-y-auto" style={{ maxHeight: 560 }}>
              <div>
                <div className="font-medium text-white leading-snug">{selectedNode.title}</div>
                <div className="text-gray-400 text-xs mt-1 space-y-0.5">
                  <div>{selectedNode.publish_date}</div>
                  <div>{selectedNode.source_site}</div>
                </div>
              </div>
              <div className="text-purple-300 text-xs font-medium flex items-center gap-1.5">
                <FiFileText size={13} aria-hidden /> {selectedNode.article_count} 篇文章
              </div>
              <div className="space-y-2">
                {selectedNode.articles.map((a) => (
                  <div key={a.id} className="border-l-2 border-gray-600 pl-2">
                    <a href={a.url} target="_blank" rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 leading-snug block">
                      {a.title}
                    </a>
                    <div className="text-gray-500 text-xs mt-0.5">
                      {a.publish_date}{a.reporter ? ` · ${a.reporter}` : ''}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {graphData && (
        <div className="flex flex-wrap gap-2 text-xs">
          {[...new Set(graphData.nodes.map((n) => n.source_site))].map((site) => (
            <span key={site} className="flex items-center gap-1.5 bg-gray-800 rounded px-2 py-1">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorForSource(site) }} />
              {site}
            </span>
          ))}
        </div>
      )}

      {!graphData && !loading && (
        <div className="text-gray-400 text-center py-12">設定條件後點「建立圖譜」</div>
      )}
    </div>
  )
}
