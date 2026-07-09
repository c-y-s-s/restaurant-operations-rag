import { describe, expect, it } from 'vitest'
import type { EvaluationSummary } from '../types/api'
import { buildScoreCards, passLabel, uniqueDocuments } from '../utils/evaluation-report'

function makeSummary(overrides: Partial<EvaluationSummary> = {}): EvaluationSummary {
  return {
    run_id: 'run-1',
    created_at: '2026-07-01T00:00:00Z',
    cases: 1,
    recall_at_5: 1,
    correct_abstention_rate: 1,
    citation_validity_rate: 1,
    answer_correctness_rate: 0.96,
    average_latency_ms: 4588.4,
    p50_latency_ms: 4300,
    p95_latency_ms: 6400,
    total_input_tokens: 12000,
    total_output_tokens: 2400,
    estimated_cost_usd: 0.0078,
    results: [],
    ...overrides
  }
}

describe('evaluation report helpers', () => {
  it('builds score cards for answer correctness, latency distribution, tokens, and cost', () => {
    const cards = buildScoreCards(makeSummary())

    expect(cards.map(card => card.label)).toContain('Answer correctness')
    expect(cards.find(card => card.label === 'Answer correctness')?.value).toBe('96%')
    expect(cards.find(card => card.label === 'P50 / P95')?.value)
      .toBe('4,300 ms / 6,400 ms')
    expect(cards.find(card => card.label === 'Tokens')?.value).toBe('12,000 / 2,400')
    expect(cards.find(card => card.label === 'Est. cost')?.value).toBe('$0.007800')
  })

  it('uses readable fallbacks for legacy evaluation rows', () => {
    const cards = buildScoreCards(makeSummary({
      answer_correctness_rate: null,
      p50_latency_ms: null,
      p95_latency_ms: null,
      total_input_tokens: null,
      total_output_tokens: null,
      estimated_cost_usd: null
    }))

    expect(cards.find(card => card.label === 'Answer correctness')?.value).toBe('N/A')
    expect(cards.find(card => card.label === 'P50 / P95')?.value).toBe('N/A / N/A')
    expect(cards.find(card => card.label === 'Tokens')?.value).toBe('N/A / N/A')
    expect(cards.find(card => card.label === 'Est. cost')?.value).toBe('N/A')
  })

  it('labels unchecked answer correctness and combines retrieved and cited documents', () => {
    expect(passLabel(null)).toBe('未檢查')
    expect(uniqueDocuments({
      id: 'case-1',
      question: '問題',
      branch_id: 'taipei',
      expected_documents: [],
      retrieved_documents: ['A', 'B'],
      retrieval_passed: true,
      should_abstain: false,
      abstained: false,
      abstention_passed: true,
      citation_validity_passed: true,
      answer_correctness_passed: false,
      matched_keywords: ['A'],
      missing_keywords: ['B'],
      cited_documents: ['B', 'C'],
      answer: '回答',
      reason: null,
      latency_ms: 100,
      overall_passed: false
    })).toEqual(['A', 'B', 'C'])
  })
})
