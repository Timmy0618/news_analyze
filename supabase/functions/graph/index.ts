import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

interface GraphRequest {
  date_from?: string
  date_to?: string
  source?: string
  max_nodes?: number
  k?: number
  min_similarity?: number
  seed?: number
  restarts?: number
}

interface ArticleSummary {
  id: string
  title: string
  url: string
  publish_date: string
  reporter: string | null
}

interface GraphNode {
  id: string
  title: string
  source_site: string
  publish_date: string
  article_count: number
  articles: ArticleSummary[]
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

function normVec(v: number[]): number[] {
  const norm = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) + 1e-8
  return v.map(x => x / norm)
}

// Deterministic seeded PRNG (mulberry32) so clustering is reproducible per seed.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return function () {
    a |= 0
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function kMeansCosine(
  vectors: number[][],
  k: number,
  rng: () => number,
  maxIter = 20,
): { assignments: number[]; centroids: number[][] } {
  const n = vectors.length
  k = Math.min(k, n)
  if (k <= 1) return { assignments: new Array(n).fill(0), centroids: [normVec(vectors[0])] }

  // K-Means++ initialization: pick centroids biased toward distant points
  const chosen: number[] = [Math.floor(rng() * n)]
  for (let c = 1; c < k; c++) {
    const dists = vectors.map((v, i) => {
      if (chosen.includes(i)) return 0
      let maxSim = -Infinity
      for (const ci of chosen) maxSim = Math.max(maxSim, cosineSim(v, vectors[ci]))
      return Math.max(0, 1 - maxSim)
    })
    const total = dists.reduce((s, d) => s + d * d, 0)
    let rand = rng() * total
    let next = chosen[chosen.length - 1]
    for (let i = 0; i < n; i++) {
      rand -= dists[i] * dists[i]
      if (rand <= 0) { next = i; break }
    }
    chosen.push(next)
  }

  const centroids = chosen.map(i => [...vectors[i]])
  let assignments = new Array(n).fill(0)

  for (let iter = 0; iter < maxIter; iter++) {
    const next = vectors.map(v => {
      let bestC = 0, bestSim = -Infinity
      for (let c = 0; c < k; c++) {
        const s = cosineSim(v, centroids[c])
        if (s > bestSim) { bestSim = s; bestC = c }
      }
      return bestC
    })

    const changed = next.some((a, i) => a !== assignments[i])
    assignments = next
    if (!changed) break

    const dim = vectors[0].length
    for (let c = 0; c < k; c++) {
      const sum = new Array(dim).fill(0)
      let count = 0
      for (let i = 0; i < n; i++) {
        if (assignments[i] !== c) continue
        for (let d = 0; d < dim; d++) sum[d] += vectors[i][d]
        count++
      }
      if (count > 0) centroids[c] = normVec(sum)
    }
  }

  return { assignments, centroids }
}

// Total cosine distance of each point to its assigned centroid (lower = tighter).
function distortion(
  vectors: number[][],
  assignments: number[],
  centroids: number[][],
): number {
  let total = 0
  for (let i = 0; i < vectors.length; i++) {
    total += 1 - cosineSim(vectors[i], centroids[assignments[i]])
  }
  return total
}

// Run k-means several times from different seeds and keep the lowest-distortion result.
function kMeansBestOf(
  vectors: number[][],
  k: number,
  seed: number,
  restarts: number,
): { assignments: number[]; centroids: number[][] } {
  let best: { assignments: number[]; centroids: number[][] } | null = null
  let bestDist = Infinity
  const runs = Math.max(1, restarts)
  for (let r = 0; r < runs; r++) {
    const rng = mulberry32(seed + r * 0x9E3779B1)
    const res = kMeansCosine(vectors, k, rng)
    const dist = distortion(vectors, res.assignments, res.centroids)
    if (dist < bestDist) { bestDist = dist; best = res }
  }
  return best!
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const body: GraphRequest = await req.json().catch(() => ({}))
    const { date_from, date_to, source, max_nodes = 50, k: kParam = 10, min_similarity = 0, seed = 42, restarts = 5 } = body

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
    )

    let q = supabase
      .from('news_articles')
      .select('id,title,source_url,source_site,publish_date,reporter,title_embedding')
      .not('title_embedding', 'is', null)
      .order('publish_date', { ascending: false })
      .limit(Math.min(max_nodes, 300))

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

    const parseEmb = (emb: unknown): number[] | null => {
      if (!emb) return null
      try {
        const arr = typeof emb === 'string' ? JSON.parse(emb) : emb
        return Array.isArray(arr) ? arr : null
      } catch { return null }
    }

    const valid = data
      .map(row => ({
        id: String(row.id),
        title: row.title as string,
        source_site: row.source_site as string,
        publish_date: row.publish_date as string,
        url: row.source_url as string,
        reporter: row.reporter as string | null,
        emb: parseEmb(row.title_embedding),
      }))
      .filter((x): x is typeof x & { emb: number[] } => x.emb !== null)

    const k = Math.min(kParam, valid.length)
    const { assignments, centroids } = kMeansBestOf(valid.map(x => x.emb), k, seed, restarts)

    // Group articles into clusters
    const clusters = new Map<number, typeof valid>()
    for (let i = 0; i < valid.length; i++) {
      const c = assignments[i]
      if (!clusters.has(c)) clusters.set(c, [])
      clusters.get(c)!.push(valid[i])
    }

    // Filter: remove articles below min_similarity to their centroid, drop clusters < 2
    if (min_similarity > 0) {
      for (const [c, members] of clusters) {
        const filtered = members.filter(m => cosineSim(m.emb, centroids[c]) >= min_similarity)
        if (filtered.length < 2) {
          clusters.delete(c)
        } else {
          clusters.set(c, filtered)
        }
      }
    }

    // Build topic nodes
    const nodes: GraphNode[] = []
    for (const [c, members] of clusters) {
      const centroid = centroids[c]

      // Representative = article closest to centroid
      let bestIdx = 0, bestSim = -Infinity
      for (let i = 0; i < members.length; i++) {
        const s = cosineSim(members[i].emb, centroid)
        if (s > bestSim) { bestSim = s; bestIdx = i }
      }

      // Dominant source_site
      const siteCounts: Record<string, number> = {}
      for (const m of members) siteCounts[m.source_site] = (siteCounts[m.source_site] ?? 0) + 1
      const dominantSite = Object.entries(siteCounts).sort((a, b) => b[1] - a[1])[0][0]

      const latestDate = members.reduce(
        (best, m) => (m.publish_date > best ? m.publish_date : best),
        members[0].publish_date,
      )

      nodes.push({
        id: `cluster-${c}`,
        title: members[bestIdx].title,
        source_site: dominantSite,
        publish_date: latestDate,
        article_count: members.length,
        articles: members.map(m => ({
          id: m.id,
          title: m.title,
          url: m.url,
          publish_date: m.publish_date,
          reporter: m.reporter,
        })),
      })
    }

    // Build inter-cluster edges from cross-cluster article pairs with similarity >= 0.7
    // Only consider articles belonging to surviving clusters (after min_similarity filter)
    const survivingClusters = new Set(clusters.keys())
    const THRESHOLD = 0.7
    const edgeSims = new Map<string, number[]>()

    for (let i = 0; i < valid.length; i++) {
      for (let j = i + 1; j < valid.length; j++) {
        const ci = assignments[i], cj = assignments[j]
        if (ci === cj) continue
        if (!survivingClusters.has(ci) || !survivingClusters.has(cj)) continue
        const sim = cosineSim(valid[i].emb, valid[j].emb)
        if (sim < THRESHOLD) continue
        const key = ci < cj ? `cluster-${ci}|cluster-${cj}` : `cluster-${cj}|cluster-${ci}`
        if (!edgeSims.has(key)) edgeSims.set(key, [])
        edgeSims.get(key)!.push(sim)
      }
    }

    const edges: GraphEdge[] = []
    for (const [key, sims] of edgeSims) {
      const [src, tgt] = key.split('|')
      edges.push({ source: src, target: tgt, weight: sims.reduce((s, x) => s + x, 0) / sims.length })
    }

    return new Response(JSON.stringify({ nodes, edges }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})
