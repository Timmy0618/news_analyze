import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

interface BiasRequest {
  run_date?: string
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
  articles: BiasArticle[]
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

    // Determine target run_date
    let targetDate = body.run_date
    if (!targetDate) {
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
      targetDate = latest.run_date
    }

    // Fetch clusters with nested bias + article data
    const { data: clusters, error } = await supabase
      .from('topic_clusters')
      .select(`
        id,
        cluster_label,
        side_a,
        side_b,
        article_count,
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
      .eq('run_date', targetDate)
      .order('article_count', { ascending: false })

    if (error) throw new Error(error.message)

    // Reshape nested data into flat article list per cluster
    const result: BiasCluster[] = (clusters ?? []).map((c) => ({
      id: c.id,
      cluster_label: c.cluster_label,
      side_a: c.side_a,
      side_b: c.side_b,
      article_count: c.article_count,
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

    return new Response(JSON.stringify({ run_date: targetDate, clusters: result }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})
