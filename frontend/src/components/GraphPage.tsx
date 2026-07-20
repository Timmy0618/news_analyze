import { useState, useCallback, useRef } from 'react'
import { FiShare2, FiFileText } from 'react-icons/fi'
import { supabase } from '../lib/supabase'
import type { GraphData, GraphNode } from '../types'
import ForceGraph2D from 'react-force-graph-2d'
import { Field, inputCls, btnPrimary } from './ui'

// Signal Monitor node palette: warm family, distinct on graphite.
const PALETTE = ['#f0b429', '#d9822b', '#b5533a', '#6f9188', '#a89e88', '#f8d585', '#c19a3e', '#8f6f52']

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
      <div className="bg-gray-800 border border-gray-700 rounded-sm p-4 flex flex-wrap gap-4 items-end">
        <Field label="From">
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={inputCls + ' font-mono'} />
        </Field>
        <Field label="To">
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={inputCls + ' font-mono'} />
        </Field>
        <Field label="Source">
          <input type="text" value={source} onChange={(e) => setSource(e.target.value)}
            placeholder="全部" className={inputCls + ' w-28'} />
        </Field>
        <Field label={`Max nodes · ${maxNodes}`}>
          <input type="range" min={20} max={200} step={10} value={maxNodes}
            onChange={(e) => setMaxNodes(Number(e.target.value))}
            className="w-28 accent-blue-500 h-8" />
        </Field>
        <Field label={`Topics K · ${k}`}>
          <input type="range" min={5} max={20} step={1} value={k}
            onChange={(e) => setK(Number(e.target.value))}
            className="w-28 accent-blue-500 h-8" />
        </Field>
        <button onClick={buildGraph} disabled={loading} className={btnPrimary}>
          {loading ? '計算中…' : <><FiShare2 size={14} aria-hidden /> 建立圖譜</>}
        </button>
      </div>

      {error && <div className="text-red-400 text-sm font-mono bg-red-900/20 border border-red-900/50 rounded-sm p-3">{error}</div>}

      {graphData && (
        <div className="flex gap-4">
          <div className="flex-1 bg-gray-900 border border-gray-700 rounded-sm overflow-hidden" style={{ height: 560 }}>
            <ForceGraph2D
              graphData={graphData}
              nodeLabel={(n) => {
                const node = n as GraphNode
                return `${node.title} (${node.article_count} 篇)`
              }}
              nodeColor={(n) => colorForSource((n as GraphNode).source_site)}
              nodeVal={(n) => (n as GraphNode).article_count}
              nodeRelSize={4}
              linkColor={() => 'rgba(240,180,41,0.12)'}
              backgroundColor="#141310"
              onNodeClick={handleNodeClick}
            />
          </div>

          {selectedNode && (
            <div className="w-72 bg-gray-800 border border-gray-700 rounded-sm text-sm shrink-0 overflow-y-auto" style={{ maxHeight: 560 }}>
              <div className="px-4 py-2 border-b border-gray-700 flex items-center gap-1.5 text-blue-400">
                <FiFileText size={13} aria-hidden />
                <span className="font-mono text-xs tabular-nums">{selectedNode.article_count} 篇文章</span>
              </div>
              <div className="p-4 space-y-3">
                <div>
                  <div className="font-medium text-gray-100 leading-snug">{selectedNode.title}</div>
                  <div className="font-mono text-gray-500 text-xs mt-1.5 space-y-0.5">
                    <div className="text-gray-400">{selectedNode.publish_date}</div>
                    <div>{selectedNode.source_site}</div>
                  </div>
                </div>
                <div className="space-y-2">
                  {selectedNode.articles.map((a) => (
                    <div key={a.id} className="border-l-2 border-gray-600 pl-2.5">
                      <a href={a.url} target="_blank" rel="noopener noreferrer"
                        className="text-gray-200 hover:text-blue-400 leading-snug block transition-colors">
                        {a.title}
                      </a>
                      <div className="font-mono text-gray-500 text-xs mt-0.5">
                        {a.publish_date}{a.reporter ? ` · ${a.reporter}` : ''}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {graphData && (
        <div className="flex flex-wrap gap-2">
          {[...new Set(graphData.nodes.map((n) => n.source_site))].map((site) => (
            <span key={site} className="flex items-center gap-1.5 bg-gray-800 border border-gray-700 rounded-sm px-2 py-1 font-mono text-xs text-gray-400">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorForSource(site) }} />
              {site}
            </span>
          ))}
        </div>
      )}

      {!graphData && !loading && (
        <div className="text-gray-500 font-mono text-sm text-center py-12">設定條件後點「建立圖譜」</div>
      )}
    </div>
  )
}
