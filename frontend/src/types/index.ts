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
