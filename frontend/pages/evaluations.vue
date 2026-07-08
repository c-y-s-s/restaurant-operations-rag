<script setup lang="ts">
import type { EvaluationCaseResult, EvaluationSummary } from '~/types/api'
import { getApiErrorMessage } from '~/utils/api-error'

const config = useRuntimeConfig()
const adminSecret = ref('')
const report = ref<EvaluationSummary | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const hasLoaded = ref(false)

const STORAGE_KEY = 'restaurant-rag-admin-secret'

onMounted(() => {
  adminSecret.value = localStorage.getItem(STORAGE_KEY) ?? ''
  if (adminSecret.value) {
    void loadLatestEvaluation()
  }
})

const scoreCards = computed(() => {
  if (!report.value) return []
  return [
    {
      label: 'Recall@5',
      value: formatPercent(report.value.recall_at_5),
      helper: '預期文件是否出現在前 5 筆檢索結果'
    },
    {
      label: 'Citation validity',
      value: formatPercent(report.value.citation_validity_rate),
      helper: '引用 chunk 是否都來自本次 context'
    },
    {
      label: 'Abstention',
      value: formatPercent(report.value.correct_abstention_rate),
      helper: '該拒答與不該拒答是否判斷正確'
    },
    {
      label: 'Avg latency',
      value: `${Math.round(report.value.average_latency_ms).toLocaleString()} ms`,
      helper: '測試集平均回應時間'
    }
  ]
})

const passedCases = computed(() => report.value?.results.filter(item => item.overall_passed).length ?? 0)
const failedCases = computed(() => Math.max((report.value?.cases ?? 0) - passedCases.value, 0))

async function loadLatestEvaluation() {
  const cleanSecret = adminSecret.value.trim()
  if (!cleanSecret || loading.value) return

  loading.value = true
  errorMessage.value = ''
  hasLoaded.value = true

  try {
    report.value = await $fetch<EvaluationSummary>('/evaluations/latest', {
      baseURL: config.public.apiBase,
      headers: {
        'X-Admin-Secret': cleanSecret
      }
    })
    localStorage.setItem(STORAGE_KEY, cleanSecret)
  } catch (error) {
    report.value = null
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function clearSecret() {
  adminSecret.value = ''
  report.value = null
  errorMessage.value = ''
  hasLoaded.value = false
  localStorage.removeItem(STORAGE_KEY)
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function formatDate(value: string | null) {
  if (!value) return '尚無執行時間'
  return new Intl.DateTimeFormat('zh-TW', {
    dateStyle: 'medium',
    timeStyle: 'short',
    hour12: false
  }).format(new Date(value))
}

function branchLabel(branchId: string) {
  return {
    taipei: '台北店',
    taichung: '台中店'
  }[branchId] ?? branchId
}

function passLabel(value: boolean | null) {
  if (value === null) return '未檢查'
  return value ? '通過' : '未通過'
}

function uniqueDocuments(caseResult: EvaluationCaseResult) {
  return [...new Set([...caseResult.retrieved_documents, ...caseResult.cited_documents])]
}
</script>

<template>
  <main class="page-shell evaluation-shell">
    <header class="site-header">
      <NuxtLink class="brand-lockup evaluation-brand" to="/">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 40 40" role="presentation">
            <circle cx="20" cy="20" r="8" />
            <circle cx="20" cy="20" r="5" />
            <path d="M8 11v7m-2-7v5c0 2 1 3 2 3s2-1 2-3v-5m-2 8v10M31 11c-2 3-2 6 0 8v10" />
          </svg>
        </div>
        <h1>餐廳營運助手</h1>
      </NuxtLink>
      <NuxtLink class="header-link" to="/">回到問答</NuxtLink>
    </header>

    <section class="evaluation-page">
      <div class="evaluation-hero">
        <p class="eyebrow">Internal RAG Quality</p>
        <h2>Evaluation Report</h2>
        <p>
          Demo 用內部評估頁，只讀取最近一次測試集結果；執行 evaluation 仍透過受保護的後端 API。
        </p>
      </div>

      <form class="evaluation-auth" @submit.prevent="loadLatestEvaluation">
        <label>
          <span>Admin Secret</span>
          <input
            v-model="adminSecret"
            :disabled="loading"
            type="password"
            autocomplete="off"
            placeholder="輸入 X-Admin-Secret 後讀取報告"
          >
        </label>
        <button type="submit" :disabled="loading || !adminSecret.trim()">
          {{ loading ? '讀取中…' : '讀取最近報告' }}
        </button>
        <button v-if="adminSecret" class="ghost-button" type="button" :disabled="loading" @click="clearSecret">
          清除
        </button>
      </form>

      <p v-if="errorMessage" class="evaluation-error" role="alert">
        {{ errorMessage }}
      </p>

      <div v-else-if="loading" class="evaluation-empty" role="status">
        正在讀取最近一次 evaluation…
      </div>

      <div v-else-if="!report && hasLoaded" class="evaluation-empty">
        找不到 evaluation 紀錄，請先用後端 `/evaluations/run` 執行測試集。
      </div>

      <template v-if="report">
        <section class="evaluation-summary-card">
          <div>
            <p class="eyebrow">Last run</p>
            <h3>{{ formatDate(report.created_at) }}</h3>
            <p class="summary-meta">
              Run ID：{{ report.run_id ?? 'N/A' }} · 測試 {{ report.cases }} 題 ·
              通過 {{ passedCases }} 題 / 未通過 {{ failedCases }} 題
            </p>
          </div>
        </section>

        <section class="score-grid" aria-label="Evaluation 指標">
          <article v-for="card in scoreCards" :key="card.label" class="score-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <p>{{ card.helper }}</p>
          </article>
        </section>

        <section class="case-list" aria-label="測試題結果">
          <div class="case-list-heading">
            <div>
              <p class="eyebrow">Case Results</p>
              <h3>逐題檢查</h3>
            </div>
            <span>{{ report.results.length }} cases</span>
          </div>

          <article
            v-for="caseResult in report.results"
            :key="caseResult.id"
            class="case-card"
            :class="{ failed: !caseResult.overall_passed }"
          >
            <div class="case-title">
              <span class="case-status">{{ caseResult.overall_passed ? '✓' : '!' }}</span>
              <div>
                <strong>{{ caseResult.id }}</strong>
                <p>{{ caseResult.question }}</p>
              </div>
              <small>{{ branchLabel(caseResult.branch_id) }} · {{ caseResult.latency_ms.toLocaleString() }} ms</small>
            </div>

            <div class="case-checks">
              <span :class="{ fail: caseResult.retrieval_passed === false }">
                Retrieval：{{ passLabel(caseResult.retrieval_passed) }}
              </span>
              <span :class="{ fail: !caseResult.abstention_passed }">
                Abstention：{{ passLabel(caseResult.abstention_passed) }}
              </span>
              <span :class="{ fail: !caseResult.citation_validity_passed }">
                Citation：{{ passLabel(caseResult.citation_validity_passed) }}
              </span>
            </div>

            <details>
              <summary>查看回答與文件</summary>
              <div class="case-detail">
                <p><strong>回答</strong>{{ caseResult.answer }}</p>
                <p v-if="caseResult.reason"><strong>拒答原因</strong>{{ caseResult.reason }}</p>
                <p><strong>預期文件</strong>{{ caseResult.expected_documents.join('、') || '無' }}</p>
                <p><strong>檢索/引用文件</strong>{{ uniqueDocuments(caseResult).join('、') || '無' }}</p>
              </div>
            </details>
          </article>
        </section>
      </template>
    </section>
  </main>
</template>
