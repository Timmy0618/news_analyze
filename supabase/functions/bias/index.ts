import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

interface BiasRequest {
  run_date?: string
  date_from?: string
  date_to?: string
}

interface BiasArticle {
  id: number
  title: string
  source_site: string
  source_url: string
  publish_date: string
  verdict: string
  reasoning: string | null
}

interface BiasCluster {
  id: number
  cluster_label: string
  side_a: string | null
  side_b: string | null
  article_count: number
  run_date: string
  articles: BiasArticle[]
}

// Merge clusters across run_dates when their article sets overlap > 50%,
// keeping the latest run_date and the union of articles (deduped by id).
// Greedy first-match: an incoming cluster joins the first merged group it overlaps,
// so merging is not transitive. Acceptable for high-overlap daily windows.
function mergeClusters(clusters: BiasCluster[]): BiasCluster[] {
  // Process latest run_date first so the representative keeps the freshest metadata.
  const sorted = [...clusters].sort((a, b) => (a.run_date < b.run_date ? 1 : -1))
  const merged: BiasCluster[] = []
  const mergedIdSets: Set<number>[] = []

  for (const c of sorted) {
    const ids = new Set(c.articles.map((a) => a.id))
    if (ids.size === 0) continue

    let target = -1
    for (let i = 0; i < mergedIdSets.length; i++) {
      let common = 0
      for (const id of ids) if (mergedIdSets[i].has(id)) common++
      if (common / ids.size > 0.5) { target = i; break }
    }

    if (target === -1) {
      merged.push({ ...c, articles: [...c.articles] })
      mergedIdSets.push(new Set(ids))
    } else {
      const grp = merged[target]
      const seen = mergedIdSets[target]
      for (const a of c.articles) {
        if (!seen.has(a.id)) { grp.articles.push(a); seen.add(a.id) }
      }
      grp.article_count = grp.articles.length
    }
  }

  return merged.sort((a, b) => b.article_count - a.article_count)
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const body: BiasRequest = await req.json().catch(() => ({}))

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
    )

    // Resolve the run_date window.
    // Priority: explicit run_date (single day, back-compat) > date_from/date_to range > latest day.
    let dateFrom: string
    let dateTo: string
    if (body.run_date) {
      dateFrom = body.run_date
      dateTo = body.run_date
    } else if (body.date_from || body.date_to) {
      dateFrom = body.date_from ?? '1970-01-01'
      dateTo = body.date_to ?? '9999-12-31'
    } else {
      const { data: latest, error: latestErr } = await supabase
        .from('topic_clusters')
        .select('run_date')
        .order('run_date', { ascending: false })
        .limit(1)
        .single()

      if (latestErr || !latest) {
        return new Response(JSON.stringify({ clusters: [], run_date: null }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        })
      }
      dateFrom = latest.run_date
      dateTo = latest.run_date
    }

    // Fetch clusters with nested bias + article data across the window
    const { data: clusters, error } = await supabase
      .from('topic_clusters')
      .select(`
        id,
        cluster_label,
        side_a,
        side_b,
        article_count,
        run_date,
        article_bias (
          verdict,
          reasoning,
          news_articles (
            id,
            title,
            source_site,
            source_url,
            publish_date
          )
        )
      `)
      .gte('run_date', dateFrom)
      .lte('run_date', dateTo)
      .order('run_date', { ascending: false })

    if (error) throw new Error(error.message)

    // Reshape nested data into flat article list per cluster
    const reshaped: BiasCluster[] = (clusters ?? []).map((c) => ({
      id: c.id,
      cluster_label: c.cluster_label,
      side_a: c.side_a,
      side_b: c.side_b,
      article_count: c.article_count,
      run_date: c.run_date,
      articles: (c.article_bias ?? [])
        .filter((b: any) => b.news_articles)
        .map((b: any) => ({
          id: b.news_articles.id,
          title: b.news_articles.title,
          source_site: b.news_articles.source_site,
          source_url: b.news_articles.source_url,
          publish_date: b.news_articles.publish_date,
          verdict: b.verdict,
          reasoning: b.reasoning,
        })),
    }))

    // Merge same topic across run_dates by article overlap
    const result = mergeClusters(reshaped)
    const latestRunDate = result.reduce(
      (best, c) => (c.run_date > best ? c.run_date : best),
      result[0]?.run_date ?? dateTo,
    )

    return new Response(
      JSON.stringify({ run_date: latestRunDate, date_from: dateFrom, date_to: dateTo, clusters: result }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } },
    )
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})
