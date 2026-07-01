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
