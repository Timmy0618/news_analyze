import { useState, useCallback, useRef, useMemo, useEffect } from 'react'
import { FiShare2, FiChevronRight } from 'react-icons/fi'
import { supabase } from '../lib/supabase'
import type { GraphData, GraphNode } from '../types'
import ForceGraph2D from 'react-force-graph-2d'
import { Field, inputCls, btnPrimary } from './ui'

interface GraphPalette {
  nodes: string[]
  bg: string
  focusStroke: string
  labelFocus: string
  labelDim: string
  linkBase: string
  linkActive: string
  linkDim: string
}

const GRAPH_DARK: GraphPalette = {
  nodes: ['#f0b429', '#d9822b', '#b5533a', '#6f9188', '#a89e88', '#f8d585', '#c19a3e', '#8f6f52'],
  bg: '#141310',
  focusStroke: '#f5c451',
  labelFocus: '#f5c451',
  labelDim: '#a89e88',
  linkBase: 'rgba(240,180,41,0.12)',
  linkActive: 'rgba(245,196,81,0.55)',
  linkDim: 'rgba(240,180,41,0.04)',
}

const GRAPH_LIGHT: GraphPalette = {
  nodes: ['#c77f0a', '#b5533a', '#4f7168', '#8a6d3b', '#9c5a2a', '#6e4a06', '#7a6a2e', '#5f4a38'],
  bg: '#f4efe3',
  focusStroke: '#b7860b',
  labelFocus: '#8a5e08',
  labelDim: '#6b6250',
  linkBase: 'rgba(183,134,11,0.16)',
  linkActive: 'rgba(138,94,8,0.55)',
  linkDim: 'rgba(183,134,11,0.05)',
}

// Node radius (graph units) from article_count — sqrt so big clusters don't dwarf small.
function nodeRadius(count: number): number {
  return Math.sqrt(count) * 2.2 + 3
}

export default function GraphPage({ theme }: { theme: 'light' | 'dark' }) {
  const gviz = theme === 'dark' ? GRAPH_DARK : GRAPH_LIGHT
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [source, setSource] = useState('')
  const [maxNodes, setMaxNodes] = useState(100)
  const [k, setK] = useState(10)
  const rowRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null)
  // Explicit canvas size — react-force-graph measures the window, not the flex
  // child, so without this the graph renders far wider than its container.
  const wrapRef = useRef<HTMLDivElement>(null)
  const [dims, setDims] = useState({ w: 0, h: 560 })

  async function buildGraph() {
    setLoading(true)
    setError('')
    setSelectedId(null)
    setHoverId(null)

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

  // Stable source→colour map, assigned in node order (deterministic per build).
  const sourceColorMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const n of graphData?.nodes ?? []) {
      if (!(n.source_site in m)) m[n.source_site] = gviz.nodes[Object.keys(m).length % gviz.nodes.length]
    }
    return m
  }, [graphData, gviz])
  const colorForSource = useCallback((site: string) => sourceColorMap[site] ?? gviz.nodes[0], [sourceColorMap, gviz])

  // Adjacency (topic id → connected topic ids). Built from links while they're
  // still raw {source,target} strings; the force-graph mutates them in place
  // later but this memo has already captured the string form.
  const neighbors = useMemo(() => {
    const adj = new Map<string, Set<string>>()
    for (const l of graphData?.links ?? []) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const s = ((l.source as any)?.id ?? l.source) as string
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const t = ((l.target as any)?.id ?? l.target) as string
      if (!adj.has(s)) adj.set(s, new Set())
      if (!adj.has(t)) adj.set(t, new Set())
      adj.get(s)!.add(t)
      adj.get(t)!.add(s)
    }
    return adj
  }, [graphData])

  // The topic currently in focus — hover wins over selection.
  const activeId = hoverId ?? selectedId

  const isLit = useCallback(
    (id: string) => !activeId || id === activeId || (neighbors.get(activeId)?.has(id) ?? false),
    [activeId, neighbors],
  )

  // Ledger rows: topics ranked by article count.
  const ranked = useMemo(
    () => (graphData ? [...graphData.nodes].sort((a, b) => b.article_count - a.article_count) : []),
    [graphData],
  )
  const maxCount = ranked.length ? ranked[0].article_count : 1
  const nodeById = useMemo(
    () => new Map((graphData?.nodes ?? []).map((n) => [n.id, n])),
    [graphData],
  )

  // When focus comes from the graph, bring its ledger row into view.
  useEffect(() => {
    if (activeId) rowRefs.current[activeId]?.scrollIntoView({ block: 'nearest' })
  }, [activeId])

  // Track the graph container's real size; refit when it changes.
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      setDims({ w: el.clientWidth, h: el.clientHeight })
      fgRef.current?.zoomToFit(300, 40)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [graphData])

  const drawNode = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (n: any, ctx: CanvasRenderingContext2D, scale: number) => {
      const node = n as GraphNode & { x: number; y: number }
      const r = nodeRadius(node.article_count)
      const lit = isLit(node.id)
      const focused = node.id === activeId
      const color = colorForSource(node.source_site)

      ctx.globalAlpha = lit ? 1 : 0.18
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()
      if (focused) {
        ctx.lineWidth = 2 / scale
        ctx.strokeStyle = gviz.focusStroke
        ctx.stroke()
      }

      // Label only for the focused topic + its neighbours — the ledger carries
      // the rest, so the canvas stays readable instead of a wall of text.
      if (activeId && lit) {
        const label = node.title.length > 18 ? node.title.slice(0, 18) + '…' : node.title
        ctx.font = `${12 / scale}px ui-monospace, monospace`
        ctx.textAlign = 'left'
        ctx.textBaseline = 'middle'
        ctx.fillStyle = focused ? gviz.labelFocus : gviz.labelDim
        ctx.fillText(label, node.x + r + 3 / scale, node.y)
      }
      ctx.globalAlpha = 1
    },
    [activeId, isLit, colorForSource, gviz],
  )

  const paintPointerArea = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (n: any, color: string, ctx: CanvasRenderingContext2D) => {
      const node = n as GraphNode & { x: number; y: number }
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(node.x, node.y, nodeRadius(node.article_count), 0, 2 * Math.PI)
      ctx.fill()
    },
    [],
  )

  const selectedNode = selectedId ? nodeById.get(selectedId) ?? null : null

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
        <div className="flex gap-4 items-stretch">
          <div ref={wrapRef} className="flex-1 bg-gray-900 border border-gray-700 rounded-sm overflow-hidden" style={{ height: 560 }}>
            <ForceGraph2D
              ref={fgRef}
              width={dims.w || undefined}
              height={dims.h}
              graphData={graphData}
              nodeCanvasObject={drawNode}
              nodeCanvasObjectMode={() => 'replace'}
              nodePointerAreaPaint={paintPointerArea}
              linkColor={(l) => {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const s = (l.source as any)?.id ?? l.source, t = (l.target as any)?.id ?? l.target
                if (!activeId) return gviz.linkBase
                return s === activeId || t === activeId ? gviz.linkActive : gviz.linkDim
              }}
              linkWidth={(l) => {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const s = (l.source as any)?.id ?? l.source, t = (l.target as any)?.id ?? l.target
                return activeId && (s === activeId || t === activeId) ? 1.5 : 0.5
              }}
              backgroundColor={gviz.bg}
              cooldownTicks={100}
              onEngineStop={() => fgRef.current?.zoomToFit(400, 40)}
              onNodeHover={(n) => setHoverId(n ? (n as GraphNode).id : null)}
              onNodeClick={(n) => setSelectedId((n as GraphNode).id)}
            />
          </div>

          {/* Topic ledger — always readable; no hover required. */}
          <div className="w-96 shrink-0 bg-gray-800 border border-gray-700 rounded-sm flex flex-col" style={{ height: 560 }}>
            <div className="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
              <span className="eyebrow">主題總表</span>
              <span className="eyebrow tabular-nums">{ranked.length} 主題</span>
            </div>
            <div className="overflow-y-auto flex-1">
              {ranked.map((node, i) => {
                const lit = isLit(node.id)
                const isSel = node.id === selectedId
                return (
                  <div key={node.id} className="border-b border-gray-700/60 last:border-0">
                    <button
                      ref={(el) => { rowRefs.current[node.id] = el }}
                      onMouseEnter={() => setHoverId(node.id)}
                      onMouseLeave={() => setHoverId(null)}
                      onClick={() => setSelectedId(isSel ? null : node.id)}
                      className={`w-full text-left px-3 py-2.5 flex flex-col gap-1 transition-colors
                        ${isSel ? 'bg-gray-700' : 'hover:bg-gray-700/50'}
                        ${!lit && activeId ? 'opacity-40' : ''}`}
                    >
                      {/* Title line — gets nearly the full panel width. */}
                      <span className="flex items-start gap-2.5">
                        <span className="font-mono text-xs text-gray-500 tabular-nums w-5 shrink-0 mt-0.5">
                          {String(i + 1).padStart(2, '0')}
                        </span>
                        <span className="w-2.5 h-2.5 rounded-full shrink-0 mt-1" style={{ backgroundColor: colorForSource(node.source_site) }} />
                        <span className={`flex-1 text-sm leading-snug line-clamp-3 ${isSel ? 'text-blue-400' : 'text-gray-200'}`}>
                          {node.title}
                        </span>
                        <FiChevronRight
                          size={13} aria-hidden
                          className={`text-gray-500 shrink-0 mt-0.5 transition-transform ${isSel ? 'rotate-90' : ''}`}
                        />
                      </span>
                      {/* Meta line — count bar, article count, source. */}
                      <span className="flex items-center gap-2 pl-[1.9375rem] font-mono text-xs text-gray-400">
                        <span className="h-1.5 rounded-full bg-blue-500/70" style={{ width: `${Math.max(6, (node.article_count / maxCount) * 44)}px` }} />
                        <span className="tabular-nums">{node.article_count}篇</span>
                        <span className="text-gray-500">·</span>
                        <span className="truncate">{node.source_site}</span>
                      </span>
                    </button>

                    {isSel && selectedNode && (
                      <div className="px-3 pb-3 pt-1 space-y-2 bg-gray-900/40">
                        <div className="font-mono text-gray-500 text-xs">
                          {selectedNode.publish_date} · {selectedNode.source_site}
                        </div>
                        {selectedNode.articles.map((a) => (
                          <div key={a.id} className="border-l-2 border-gray-600 pl-2.5">
                            <a href={a.url} target="_blank" rel="noopener noreferrer"
                              className="text-gray-200 hover:text-blue-400 text-sm leading-snug block transition-colors">
                              {a.title}
                            </a>
                            <div className="font-mono text-gray-500 text-xs mt-0.5">
                              {a.publish_date}{a.reporter ? ` · ${a.reporter}` : ''}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
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
