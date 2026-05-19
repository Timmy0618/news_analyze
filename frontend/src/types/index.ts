export interface NewsArticle {
  id: number
  title: string
  summary: string | null
  source_url: string
  source_site: string
  publish_date: string
  reporter: string | null
}

export interface SearchResult extends NewsArticle {
  similarity: number
}

export interface ArticleSummary {
  id: string
  title: string
  url: string
  publish_date: string
  reporter: string | null
}

export interface GraphNode {
  id: string
  title: string
  source_site: string
  publish_date: string
  article_count: number
  articles: ArticleSummary[]
}

export interface GraphEdge {
  source: string
  target: string
  weight: number
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphEdge[]
}

export interface BiasArticle {
  id: number
  title: string
  source_site: string
  source_url: string
  publish_date: string
  verdict: string
  reasoning: string | null
}

export interface BiasCluster {
  id: number
  cluster_label: string
  side_a: string | null
  side_b: string | null
  article_count: number
  articles: BiasArticle[]
}
