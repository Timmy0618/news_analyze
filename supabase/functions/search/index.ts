import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

interface SearchRequest {
  query: string
  top_k?: number
  search_field?: 'title' | 'summary' | 'both'
  source?: string
  date_from?: string
  date_to?: string
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
    const body: SearchRequest = await req.json()
    const { query, top_k = 10, search_field = 'both', source, date_from, date_to } = body

    if (!query?.trim()) {
      return new Response(JSON.stringify({ error: 'query is required' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      })
    }

    const jinaKey = Deno.env.get('JINA_API_KEY')
    if (!jinaKey) throw new Error('JINA_API_KEY not configured')

    // Generate query embedding via Jina AI
    const jinaRes = await fetch('https://api.jina.ai/v1/embeddings', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jinaKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'jina-embeddings-v3',
        input: [query],
        task: 'retrieval.query',
      }),
    })
    if (!jinaRes.ok) throw new Error(`Jina API error: ${jinaRes.status}`)
    const jinaData = await jinaRes.json()
    const embedding: number[] = jinaData.data[0].embedding

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
    )

    const { data, error } = await supabase.rpc('match_articles', {
      query_embedding: embedding,
      match_count: Math.min(top_k, 100),
      search_field,
      filter_source: source ?? null,
      filter_date_from: date_from ?? null,
      filter_date_to: date_to ?? null,
    })

    if (error) throw new Error(error.message)

    return new Response(JSON.stringify({ results: data }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})
