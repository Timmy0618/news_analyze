/* The one seam between the React pages and the news backend.
 *
 * Every Edge Function / RPC / table name, every wire→domain shape fix, and the
 * egress-safe column list live here — pages import typed functions and never
 * touch the supabase client or a hardcoded backend name. Failures throw a
 * NewsApiError; the transport's { data, error } tuple never crosses the seam. */

import { supabase } from './supabase'
import type {
  SearchResult,
  GraphData,
  GraphNode,
  GraphEdge,
  BiasCluster,
  BiasSourceStat,
  NewsArticle,
  ArticleStats,
} from '../types'

export class NewsApiError extends Error {
  cause?: unknown
  constructor(message: string, cause?: unknown) {
    super(message)
    this.name = 'NewsApiError'
    this.cause = cause
  }
}

/** Extract a display string from anything thrown, for a page's error banner. */
export function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

async function invokeFn<T>(name: string, body: Record<string, unknown>): Promise<T> {
  const { data, error } = await supabase.functions.invoke<T>(name, { body })
  if (error) throw new NewsApiError(error.message, error)
  if (data == null) throw new NewsApiError(`${name} 回傳空資料`)
  return data
}

async function callRpc<T>(name: string, args: Record<string, unknown>): Promise<T> {
  const { data, error } = await supabase.rpc(name, args)
  if (error) throw new NewsApiError(error.message, error)
  return data as T
}

export interface SearchParams {
  query: string
  topK: number
  searchField: 'title' | 'summary' | 'both'
  source?: string
  dateFrom?: string
  dateTo?: string
}

async function search(p: SearchParams): Promise<SearchResult[]> {
  const data = await invokeFn<{ results: SearchResult[] }>('search', {
    query: p.query.trim(),
    top_k: p.topK,
    search_field: p.searchField,
    source: p.source || undefined,
    date_from: p.dateFrom || undefined,
    date_to: p.dateTo || undefined,
  })
  return data.results ?? []
}

export interface GraphParams {
  dateFrom?: string
  dateTo?: string
  source?: string
  maxNodes: number
  k: number
}

async function graph(p: GraphParams): Promise<GraphData> {
  // Wire returns `edges`; the app (and react-force-graph) speak `links`.
  const data = await invokeFn<{ nodes: GraphNode[]; edges: GraphEdge[] }>('graph', {
    date_from: p.dateFrom || undefined,
    date_to: p.dateTo || undefined,
    source: p.source || undefined,
    max_nodes: p.maxNodes,
    k: p.k,
  })
  return { nodes: data.nodes ?? [], links: data.edges ?? [] }
}

export interface BiasParams {
  dateFrom: string
  dateTo: string
}

export interface BiasReport {
  runDate: string | null
  clusters: BiasCluster[]
  sourceStats: BiasSourceStat[]
}

async function bias(p: BiasParams): Promise<BiasReport> {
  const [report, sourceStats] = await Promise.all([
    invokeFn<{ run_date: string | null; clusters: BiasCluster[] }>('bias', {
      date_from: p.dateFrom,
      date_to: p.dateTo,
    }),
    // Per-source stats are an auxiliary aggregate: a failure here must not blank
    // the whole page, so it degrades to [] rather than throwing past the seam.
    callRpc<BiasSourceStat[]>('get_bias_stats', {
      date_from: p.dateFrom,
      date_to: p.dateTo,
    }).catch(() => [] as BiasSourceStat[]),
  ])

  const clusters = [...(report.clusters ?? [])].sort((a, b) => {
    const byDate = (b.run_date ?? '').localeCompare(a.run_date ?? '')
    return byDate !== 0 ? byDate : b.article_count - a.article_count
  })

  return { runDate: report.run_date, clusters, sourceStats: sourceStats ?? [] }
}

export interface BrowseParams {
  dateFrom?: string
  dateTo?: string
  source?: string
  reporter?: string
  sortBy: 'publish_date' | 'source_site'
  page: number
  pageSize: number
}

async function browse(p: BrowseParams): Promise<{ articles: NewsArticle[]; total: number }> {
  // Column list deliberately excludes the 1024-dim vector columns (egress).
  let q = supabase
    .from('news_articles')
    .select('id,title,source_url,source_site,publish_date,reporter', { count: 'exact' })
    .order(p.sortBy, { ascending: false })
    .range(p.page * p.pageSize, p.page * p.pageSize + p.pageSize - 1)

  if (p.dateFrom) q = q.gte('publish_date', p.dateFrom)
  if (p.dateTo) q = q.lte('publish_date', p.dateTo)
  if (p.source) q = q.eq('source_site', p.source)
  if (p.reporter?.trim()) q = q.ilike('reporter', `%${p.reporter.trim()}%`)

  const { data, count, error } = await q
  if (error) throw new NewsApiError(error.message, error)
  return { articles: (data ?? []) as NewsArticle[], total: count ?? 0 }
}

async function sources(): Promise<string[]> {
  const data = await callRpc<string[]>('get_distinct_sources', {})
  return data ?? []
}

interface StatsWire {
  total?: number | string
  daily?: { publish_date: string; count: number | string }[]
  by_site?: { source_site: string; count: number | string }[]
}

async function stats(sinceDate: string): Promise<ArticleStats> {
  const data = await callRpc<StatsWire>('get_article_stats', { since_date: sinceDate })
  return {
    total: Number(data?.total ?? 0),
    daily: (data?.daily ?? []).map((r) => ({ publish_date: r.publish_date, count: Number(r.count) })),
    bySite: (data?.by_site ?? []).map((r) => ({ source_site: r.source_site, count: Number(r.count) })),
  }
}

export const newsApi = { search, graph, bias, browse, sources, stats }
