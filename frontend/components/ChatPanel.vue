<script setup lang="ts">
import type { BranchId, ChatResponse, ConversationTurn } from '~/types/api'
import { getApiErrorMessage } from '~/utils/api-error'

const config = useRuntimeConfig()
const branchId = ref<BranchId>('taipei')
const question = ref('')
const loading = ref(false)
const turns = ref<ConversationTurn[]>([])
const input = useTemplateRef<HTMLInputElement>('questionInput')
const serviceStatus = ref<'checking' | 'online' | 'offline'>('checking')

const branches: Array<{ id: BranchId, label: string }> = [
  { id: 'taipei', label: '台北店' },
  { id: 'taichung', label: '台中店' }
]

const examples = [
  '花生過敏可以吃哪些餐點？',
  '炸爐每天打烊後怎麼清潔？',
  '星期六最後點餐是幾點？',
  '洗碗機沖洗溫度不足怎麼辦？',
  'POS 離線時如何記錄訂單？',
  '客人疑似嚴重過敏要怎麼處理？'
]

const serviceLabel = computed(() => ({
  checking: '正在確認服務',
  online: '知識庫已連線',
  offline: '知識庫未連線'
}[serviceStatus.value]))

onMounted(async () => {
  try {
    const health = await $fetch<{ status: 'ok' | 'degraded' }>('/health', {
      baseURL: config.public.apiBase
    })
    serviceStatus.value = health.status === 'ok' ? 'online' : 'offline'
  } catch {
    serviceStatus.value = 'offline'
  }
})

async function submit(value = question.value) {
  const cleanQuestion = value.trim()
  if (!cleanQuestion || loading.value) return

  const turn: ConversationTurn = {
    id: crypto.randomUUID(),
    question: cleanQuestion,
    branchId: branchId.value
  }
  turns.value.push(turn)
  question.value = ''
  loading.value = true

  try {
    turn.response = await $fetch<ChatResponse>('/chat', {
      baseURL: config.public.apiBase,
      method: 'POST',
      body: {
        question: cleanQuestion,
        branch_id: turn.branchId
      }
    })
  } catch (error) {
    turn.error = getApiErrorMessage(error)
  } finally {
    loading.value = false
    await nextTick()
    input.value?.focus()
  }
}

function branchLabel(id: BranchId) {
  return branches.find(branch => branch.id === id)?.label ?? id
}

function citationSourceIds(response: ChatResponse) {
  return [...new Set(response.citations.map(citation => citation.source_id))]
}
</script>

<template>
  <main class="page-shell">
    <header class="site-header">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 40 40" role="presentation">
            <circle cx="20" cy="20" r="8" />
            <circle cx="20" cy="20" r="5" />
            <path d="M8 11v7m-2-7v5c0 2 1 3 2 3s2-1 2-3v-5m-2 8v10M31 11c-2 3-2 6 0 8v10" />
          </svg>
        </div>
        <h1>餐廳營運助手</h1>
      </div>
      <span class="status-pill" :class="serviceStatus"><span /> {{ serviceLabel }}</span>
    </header>

    <section class="workspace" aria-label="餐廳營運問答">
      <div v-if="turns.length === 0" class="welcome">
        <div class="welcome-intro">
          <div class="restaurant-motif" aria-hidden="true">
            <span />
            <svg viewBox="0 0 64 34" role="presentation">
              <path d="M10 27h44M15 25c1-11 7-17 17-17s16 6 17 17M28 7c0-2 1-3 4-3s4 1 4 3" />
            </svg>
            <span />
          </div>
          <h2>餐廳營運查詢</h2>
          <p>詢問菜單過敏原、設備操作或分店流程，回答會附上內部文件來源。</p>
        </div>

        <div class="prompt-board">
          <div class="prompt-board-heading">
            <span>常用問題</span>
          </div>
          <div class="example-grid" aria-label="範例問題">
            <button
              v-for="example in examples"
              :key="example"
              type="button"
              @click="submit(example)"
            >
              <span>{{ example }}</span>
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>

      <div v-else class="conversation" aria-live="polite">
        <article v-for="turn in turns" :key="turn.id" class="turn">
          <div class="question-row">
            <span>{{ branchLabel(turn.branchId) }}</span>
            <p>{{ turn.question }}</p>
          </div>

          <div v-if="turn.error" class="error-card" role="alert">
            <strong>暫時無法取得回答</strong>
            <p>{{ turn.error }}</p>
          </div>

          <div v-else-if="turn.response" class="answer-card" :class="{ abstained: turn.response.abstained }">
            <div class="answer-heading">
              <span class="answer-icon" aria-hidden="true">{{ turn.response.abstained ? '!' : '✓' }}</span>
              <span>{{ turn.response.abstained ? '資料不足' : '根據內部文件' }}</span>
            </div>
            <p class="answer-copy">
              {{ turn.response.answer }}<template v-for="sourceId in citationSourceIds(turn.response)" :key="sourceId"><span class="inline-citation">[{{ sourceId }}]</span></template>
            </p>
            <p v-if="turn.response.reason" class="reason">{{ turn.response.reason }}</p>

            <div v-if="turn.response.citations.length" class="citations">
              <p class="citation-label">文件依據 · {{ turn.response.citations.length }} 筆</p>
              <details v-for="(citation, index) in turn.response.citations" :key="citation.chunk_id">
                <summary>
                  <span class="citation-number">{{ index + 1 }}</span>
                  <span>
                    <strong>{{ citation.document_title }}</strong>
                    <small>{{ citation.section }}<template v-if="citation.page_number"> · 第 {{ citation.page_number }} 頁</template></small>
                  </span>
                  <span class="chevron" aria-hidden="true">⌄</span>
                </summary>
                <div class="citation-body">
                  <p>{{ citation.excerpt }}</p>
                  <small>支持結論：{{ citation.statement }}</small>
                </div>
              </details>
            </div>

            <div class="execution">
              {{ turn.response.execution.latency_ms.toLocaleString() }} ms
              <span>·</span>
              檢索 {{ turn.response.execution.retrieved_chunks }} 段
            </div>
          </div>
        </article>

        <div v-if="loading" class="loading-row" role="status">
          <span /><span /><span /> 正在查閱營運文件
        </div>
      </div>

      <form class="composer" @submit.prevent="submit()">
        <label class="branch-select">
          <span class="sr-only">選擇分店</span>
          <select v-model="branchId" :disabled="loading">
            <option v-for="branch in branches" :key="branch.id" :value="branch.id">
              {{ branch.label }}
            </option>
          </select>
        </label>
        <label class="question-input">
          <span class="sr-only">輸入營運問題</span>
          <input
            ref="questionInput"
            v-model="question"
            :disabled="loading"
            maxlength="500"
            autocomplete="off"
            placeholder="輸入營運問題…"
          >
        </label>
        <button class="send-button" type="submit" :disabled="loading || question.trim().length < 2">
          <span class="sr-only">送出問題</span>
          <span aria-hidden="true">→</span>
        </button>
      </form>
      <p class="disclaimer">內容依內部文件檢索生成；涉及食安或緊急事件時，仍以原始 SOP 與值班主管指示為準。</p>
    </section>
  </main>
</template>
