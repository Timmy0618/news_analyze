import { describe, test, expect, vi, beforeEach } from 'vitest'
import type { Mock } from 'vitest'

vi.mock('./supabase', () => ({
  supabase: {
    functions: { invoke: vi.fn() },
    rpc: vi.fn(),
    from: vi.fn(),
  },
}))

import { supabase } from './supabase'
import { newsApi, NewsApiError, errorMessage } from './newsApi'

const invoke = supabase.functions.invoke as unknown as Mock
const rpc = supabase.rpc as unknown as Mock

beforeEach(() => {
  vi.clearAllMocks()
})

describe('newsApi.graph', () => {
  test('remaps wire `edges` to `links`', async () => {
    invoke.mockResolvedValue({
      data: { nodes: [{ id: 'a' }], edges: [{ source: 'a', target: 'b', weight: 1 }] },
      error: null,
    })
    const g = await newsApi.graph({ maxNodes: 50, k: 10 })
    expect(g.links).toEqual([{ source: 'a', target: 'b', weight: 1 }])
    expect(g.nodes).toHaveLength(1)
  })
})

describe('error contract', () => {
  test('throws NewsApiError when an edge function errors', async () => {
    invoke.mockResolvedValue({ data: null, error: { message: 'boom' } })
    await expect(
      newsApi.search({ query: 'x', topK: 10, searchField: 'both' }),
    ).rejects.toBeInstanceOf(NewsApiError)
  })
})

describe('newsApi.stats', () => {
  test('coerces string counts to numbers', async () => {
    rpc.mockResolvedValue({
      data: {
        total: '42',
        daily: [{ publish_date: '2026-01-01', count: '7' }],
        by_site: [{ source_site: 'X', count: '3' }],
      },
      error: null,
    })
    const s = await newsApi.stats('2026-01-01')
    expect(s.total).toBe(42)
    expect(s.daily[0].count).toBe(7)
    expect(s.bySite[0]).toEqual({ source_site: 'X', count: 3 })
  })
})

describe('errorMessage', () => {
  test('reads a NewsApiError message', () => {
    expect(errorMessage(new NewsApiError('nope'))).toBe('nope')
  })
})
