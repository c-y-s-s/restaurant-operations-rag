# RAG 評估報告

## 正式執行結果

- 執行日期：2026-07-08
- 測試案例：25 題核心案例
- 模型：`gpt-5.4-mini`
- Embedding：`text-embedding-3-small`
- Retrieval：Hybrid Search，top 5 評估

正式結果目前寫入 Supabase 的 `evaluation_runs` 與 `evaluation_case_results`。每次執行會取得獨立 `run_id`，讓報告與原始逐題資料可以互相對照。

| 指標 | 結果 |
|---|---:|
| Recall@5 | 100% |
| 正確拒答率 | 100% |
| Citation validity | 100% |
| Keyword answer correctness | 100% |
| 自動條件整體通過 | 25 / 25 |
| 平均端到端延遲 | 5,756 ms |
| P50 端到端延遲 | 4,994 ms |
| P95 端到端延遲 | 8,287 ms |
| Input / Output tokens | 34,664 / 4,581 |
| Estimated cost | US$0.017828 |

## 指標定義

- **Recall@5：**所有預期文件都出現在該題檢索結果前 5 名才算通過。沒有預期文件的拒答題不納入此分母。
- **正確拒答率：**實際 `abstained` 是否等於測試案例的 `should_abstain`。
- **Citation validity：**所有回傳的 citation UUID 是否都存在於該題的 top 5 檢索結果。
- **Keyword answer correctness：**非拒答案例的回答必須包含該案例標註的所有 `expected_keywords`。拒答案例不納入此分母。
- **P50 / P95 latency：**依逐題端到端延遲計算，用來觀察平均值以外的分布。
- **Estimated cost：**依設定的每百萬 input/output token 單價估算模型成本，作為作品集觀測值，不代表 OpenAI 帳單。
- **整體通過：**該題的檢索（適用時）、拒答判斷、引用驗證與 keyword answer correctness 全部通過。

## 類別覆蓋

評估集涵蓋：

- 過敏原與菜單資訊
- 食譜、溫度及食品安全
- 設備清潔與操作
- 客訴、退款與緊急應變
- 開店、打烊與分店專屬流程
- POS、員工衛生與訂位
- 需要兩份文件的複合問題
- 文件未提供答案、應該拒答的問題

## 延遲觀察

25 題核心評估的平均端到端延遲為 5,756 ms，P50 為 4,994 ms，P95 為 8,287 ms。延遲仍主要受 OpenAI generation、外部網路與 Supabase 連線狀態影響；因此報告同時呈現平均值與 P95，避免只看平均值而忽略尾端慢請求。

## 結果解讀限制

25/25 代表目前定義的自動工程條件全部通過。Keyword correctness 能檢查預期事實是否出現在回答中，但不代表完整語意正確率已達 100%。後續可增加：

- 結構化 expected facts
- 人工標註的 answer correctness
- 多次執行以觀察模型輸出變異
- 隔離測試資料庫中的真實來源衝突測試

## 失敗案例

本次沒有自動條件失敗案例。歷史問題與修正過程請參考 [`experiment-log.md`](experiment-log.md)。
