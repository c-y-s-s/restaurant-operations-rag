# 部署操作指南

本專案建議使用：

- Supabase：PostgreSQL、pgvector 與資料紀錄
- Render：FastAPI 後端
- Vercel：Nuxt 3 前端

## 0. 部署前檢查

不要把以下內容提交到 Git：

- `.env`
- OpenAI API Key
- Supabase 資料庫密碼
- `ADMIN_SECRET`
- `node_modules`、`.venv`、`.nuxt`、`.output`

這些路徑已包含在 `.gitignore`。

## 1. 將專案放到 GitHub

在專案根目錄執行：

```bash
git init
git add .
git commit -m "Build restaurant operations RAG assistant"
git branch -M main
git remote add origin 你的_GITHUB_REPOSITORY_URL
git push -u origin main
```

執行 `git add .` 後，可以先用 `git status` 確認 `.env` 沒有出現在 staged files。

## 2. 部署 Render 後端

1. 登入 Render 並選擇 **New → Blueprint**。
2. 連接 GitHub repository。
3. Render 會讀取根目錄的 `render.yaml`，建立 `restaurant-rag-api`。
   Blueprint 已明確設定 `plan: free`。建立前請在 Estimated pricing 確認服務顯示 Free／US$0；如果畫面仍顯示 Starter US$7，先不要按 Create。
4. 設定以下環境變數：

| 名稱 | 值 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API Key |
| `DATABASE_URL` | Supabase PostgreSQL 連線字串 |
| `ADMIN_SECRET` | Render 自動產生，或自行設定長隨機字串 |
| `ALLOWED_ORIGINS` | 部署前可暫填預計的 Vercel URL，之後再修正 |
| `MAX_DAILY_REQUESTS_PER_IP` | 預設 `40` |

Docker 啟動時會先執行：

```text
python -m app.cli migrate
```

Migration runner 具有 idempotency，已執行的 migration 不會重複套用。Migration 成功後才啟動 Uvicorn，並使用 Render 提供的 `PORT`。

部署完成後確認：

```text
https://你的後端.onrender.com/health
https://你的後端.onrender.com/docs
```

`/health` 應顯示：

```json
{
  "status": "ok",
  "database": true,
  "openai_configured": true
}
```

## 3. 部署 Vercel 前端

1. 登入 Vercel，選擇 **Add New → Project**。
2. 匯入同一個 GitHub repository。
3. 將 **Root Directory** 設為 `frontend`。
4. Framework Preset 選擇 Nuxt.js；Build Command 使用 `npm run build`。
5. 設定環境變數：

```text
NUXT_PUBLIC_API_BASE=https://你的後端.onrender.com
```

6. 部署完成後取得 Vercel URL，例如：

```text
https://restaurant-rag.vercel.app
```

## 4. 回到 Render 設定 CORS

將 Render 的 `ALLOWED_ORIGINS` 更新為實際 Vercel 網址：

```text
https://restaurant-rag.vercel.app
```

不要加最後的 `/`。若需要多個來源，使用逗號分隔：

```text
https://restaurant-rag.vercel.app,http://localhost:3000
```

更新後重新部署或重新啟動 Render service。

## 5. 部署後測試

依序確認：

1. Render `/health` 回傳 `status: ok`。
2. Vercel 頁面可以載入。
3. 台北店詢問「週六最後點餐時間」。
4. 展開引用來源，確認標題、章節與原文。
5. 詢問不存在的即時庫存，確認系統拒答。
6. 在 Supabase 查看 `chat_logs` 與 `chat_citations`。

管理 API 不應放在公開前端。需要執行 evaluation 時，從自己的終端機呼叫並使用 `X-Admin-Secret`。

## 6. 常見問題

### 前端出現 CORS 錯誤

確認 Render 的 `ALLOWED_ORIGINS` 與瀏覽器網址完全相同，包含 `https`，且沒有多餘的 `/`。

### Render 啟動失敗

先看 deploy log 中的 migration 錯誤。最常見原因是 `DATABASE_URL` 錯誤、Supabase 密碼包含特殊字元但沒有 URL encode，或資料庫暫時無法連線。

### 前端仍呼叫 localhost

確認 Vercel 已設定 `NUXT_PUBLIC_API_BASE`，並在設定後重新部署。這個 public runtime config 需要進入 production build。

### Render 第一次回答較慢

免費或低用量 instance 可能有 cold start。Demo 前先開啟 `/health` 與前端頁面進行預熱。
