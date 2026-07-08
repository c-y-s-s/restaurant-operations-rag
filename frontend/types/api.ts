export type BranchId = 'taipei' | 'taichung'

export interface Citation {
  citation_number: number
  source_id: number
  chunk_id: string
  statement: string
  document_title: string
  section: string
  page_number: number | null
  branch_id: BranchId | null
  excerpt: string
}

export interface ExecutionInfo {
  latency_ms: number
  retrieval_ms: number
  generation_ms: number
  input_tokens: number
  output_tokens: number
  retrieved_chunks: number
}

export interface ChatResponse {
  trace_id: string | null
  answer: string
  abstained: boolean
  reason: string | null
  citations: Citation[]
  execution: ExecutionInfo
}

export interface ConversationTurn {
  id: string
  question: string
  branchId: BranchId
  response?: ChatResponse
  error?: string
}

export interface EvaluationCaseResult {
  id: string
  question: string
  branch_id: string
  expected_documents: string[]
  retrieved_documents: string[]
  retrieval_passed: boolean | null
  should_abstain: boolean
  abstained: boolean
  abstention_passed: boolean
  citation_validity_passed: boolean
  cited_documents: string[]
  answer: string
  reason: string | null
  latency_ms: number
  overall_passed: boolean
}

export interface EvaluationSummary {
  run_id: string | null
  created_at: string | null
  cases: number
  recall_at_5: number
  correct_abstention_rate: number
  citation_validity_rate: number
  average_latency_ms: number
  results: EvaluationCaseResult[]
}
