import type { EvaluationCaseResult, EvaluationSummary } from '~/types/api'

export interface ScoreCard {
  label: string
  value: string
  helper: string
}

export function buildScoreCards(report: EvaluationSummary): ScoreCard[] {
  return [
    {
      label: 'Recall@5',
      value: formatPercent(report.recall_at_5),
      helper: '預期文件是否出現在前 5 筆檢索結果'
    },
    {
      label: 'Citation validity',
      value: formatPercent(report.citation_validity_rate),
      helper: '引用 chunk 是否都來自本次 context'
    },
    {
      label: 'Answer correctness',
      value: formatNullablePercent(report.answer_correctness_rate),
      helper: '回答是否包含預期關鍵事實'
    },
    {
      label: 'Abstention',
      value: formatPercent(report.correct_abstention_rate),
      helper: '該拒答與不該拒答是否判斷正確'
    },
    {
      label: 'Avg latency',
      value: `${Math.round(report.average_latency_ms).toLocaleString()} ms`,
      helper: '測試集平均回應時間'
    },
    {
      label: 'P50 / P95',
      value: `${formatLatency(report.p50_latency_ms)} / ${formatLatency(report.p95_latency_ms)}`,
      helper: '逐題端到端延遲分布'
    },
    {
      label: 'Tokens',
      value: `${formatNumber(report.total_input_tokens)} / ${formatNumber(report.total_output_tokens)}`,
      helper: '輸入 / 輸出 tokens'
    },
    {
      label: 'Est. cost',
      value: formatCost(report.estimated_cost_usd),
      helper: '依設定單價估算，非帳單金額'
    }
  ]
}

export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

export function formatNullablePercent(value: number | null) {
  return value === null ? 'N/A' : formatPercent(value)
}

export function formatLatency(value: number | null) {
  return value === null ? 'N/A' : `${Math.round(value).toLocaleString()} ms`
}

export function formatNumber(value: number | null) {
  return value === null ? 'N/A' : value.toLocaleString()
}

export function formatCost(value: number | null) {
  if (value === null) return 'N/A'
  if (value === 0) return '$0.00'
  return `$${value.toFixed(6)}`
}

export function passLabel(value: boolean | null) {
  if (value === null) return '未檢查'
  return value ? '通過' : '未通過'
}

export function uniqueDocuments(caseResult: EvaluationCaseResult) {
  return [...new Set([...caseResult.retrieved_documents, ...caseResult.cited_documents])]
}
