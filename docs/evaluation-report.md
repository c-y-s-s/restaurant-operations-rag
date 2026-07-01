# RAG 評估報告

## 正式執行結果

- 執行日期：2026-07-01
- 測試案例：31 題
- 模型：`gpt-5.4-mini`
- Embedding：`text-embedding-3-small`
- Retrieval：Hybrid Search，top 5 評估

正式結果目前寫入 Supabase 的 `evaluation_runs` 與 `evaluation_case_results`。每次執行會取得獨立 `run_id`，讓報告與原始逐題資料可以互相對照。

| 指標 | 結果 |
|---|---:|
| Recall@5 | 100% |
| 正確拒答率 | 100% |
| Citation validity | 100% |
| 自動條件整體通過 | 31 / 31 |
| 平均端到端延遲 | 4,588 ms |
| 最快案例 | 2,506 ms |
| 最慢案例 | 6,435 ms |

## 指標定義

- **Recall@5：**所有預期文件都出現在該題檢索結果前 5 名才算通過。沒有預期文件的拒答題不納入此分母。
- **正確拒答率：**實際 `abstained` 是否等於測試案例的 `should_abstain`。
- **Citation validity：**所有回傳的 citation UUID 是否都存在於該題的 top 5 檢索結果。
- **整體通過：**該題的檢索（適用時）、拒答判斷與引用驗證全部通過。

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

平均端到端延遲由 29 題探索測試的 5,551 ms 降至本次 4,588 ms，約下降 17.3%。本次最快案例為 `unknown-02`（2,506 ms），最慢為 `dish-01`（6,435 ms）。目前延遲仍主要受 OpenAI generation 與外部網路影響。

## 結果解讀限制

31/31 代表目前定義的自動工程條件全部通過，不代表答案語意正確率已達 100%。現有評估尚未逐題保存 `expected_answer` 或 `expected_keywords`，因此回答內容仍需要人工抽查。後續可增加：

- `expected_keywords` 或結構化 expected facts
- 人工標註的 answer correctness
- 多次執行以觀察模型輸出變異
- P50、P95 latency 與 Token 成本
- 隔離測試資料庫中的真實來源衝突測試

## 失敗案例

本次沒有自動條件失敗案例。歷史問題與修正過程請參考 [`experiment-log.md`](experiment-log.md)。
