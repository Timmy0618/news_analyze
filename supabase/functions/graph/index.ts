import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

interface GraphRequest {
  date_from?: string
  date_to?: string
  source?: string
  max_nodes?: number
}

interface GraphNode {
  id: string
  title: string
  source_site: string
  publish_date: string
  url: string
  reporter: string | null
}

interface GraphEdge {
  source: string
  target: string
  weight: number
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

function cosineSim(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    na += a[i] * a[i]
    nb += b[i] * b[i]
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-8)
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const body: GraphRequest = await req.json().catch(() => ({}))
    const { date_from, date_to, source, max_nodes = 50 } = body

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
    )

    let q = supabase
      .from('news_articles')
      .select('id,title,source_url,source_site,publish_date,reporter,title_embedding')
      .not('title_embedding', 'is', null)
      .order('publish_date', { ascending: false })
      .limit(Math.min(max_nodes, 80))

    if (date_from) q = q.gte('publish_date', date_from)
    if (date_to) q = q.lte('publish_date', date_to)
    if (source) q = q.eq('source_site', source)

    const { data, error } = await q
    if (error) throw new Error(error.message)
    if (!data || data.length === 0) {
      return new Response(JSON.stringify({ nodes: [], edges: [] }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      })
    }

    const nodes: GraphNode[] = data.map((row) => ({
      id: String(row.id),
      title: row.title as string,
      source_site: row.source_site as string,
      publish_date: row.publish_date as string,
      url: row.source_url as string,
      reporter: row.reporter as string | null,
    }))

    // pgvector returns as string "[0.1,0.2,...]" via REST API — parse if needed
    const parseEmb = (emb: unknown): number[] | null => {
      if (!emb) return null
      try {
        const arr = typeof emb === 'string' ? JSON.parse(emb) : emb
        return Array.isArray(arr) ? arr : null
      } catch { return null }
    }

    // Filter out rows with unparseable embeddings
    const valid = data
      .map((row, i) => ({ node: nodes[i], emb: parseEmb(row.title_embedding) }))
      .filter((x): x is { node: GraphNode; emb: number[] } => x.emb !== null)

    const THRESHOLD = 0.7
    const TOP_K = 3
    const edgeSet = new Set<string>()
    const edges: GraphEdge[] = []

    for (let i = 0; i < valid.length; i++) {
      const sims: { j: number; sim: number }[] = []
      for (let j = 0; j < valid.length; j++) {
        if (i === j) continue
        const sim = cosineSim(valid[i].emb, valid[j].emb)
        if (sim >= THRESHOLD) sims.push({ j, sim })
      }
      sims.sort((a, b) => b.sim - a.sim)
      for (const { j, sim } of sims.slice(0, TOP_K)) {
        const key = i < j ? `${i}-${j}` : `${j}-${i}`
        if (!edgeSet.has(key)) {
          edgeSet.add(key)
          edges.push({ source: valid[i].node.id, target: valid[j].node.id, weight: sim })
        }
      }
    }

    return new Response(JSON.stringify({ nodes: valid.map(x => x.node), edges }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})
