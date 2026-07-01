from openai import AsyncOpenAI

from app.models import AnswerDraft, RetrievedChunk

SYSTEM_PROMPT = """你是餐廳內部營運知識助手。你的唯一事實來源是使用者訊息中的 CONTEXT。

規則：
1. 只能回答 CONTEXT 明確支持的內容，不得使用模型既有知識補充。
2. 每個重要結論都要在 citations 欄位引用支持它的 chunk_id。
3. 如果內容不足、互相衝突，或問題與餐廳營運無關，設定 abstained=true。
4. 拒答時，answer 要簡短說明目前資料不足，reason 要指出缺少什麼資料，citations 可為空。
5. answer 欄位不得出現 chunk_id、UUID、括號內來源代碼、[1] 這類引用標記；引用只放在 citations 欄位。
6. 使用繁體中文，回答簡潔、具體，避免推測。
"""


class OpenAIService:
    def __init__(self, api_key: str, chat_model: str, embedding_model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.chat_model = chat_model
        self.embedding_model = embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
            encoding_format="float",
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]

    async def answer(
        self, question: str, branch_id: str, chunks: list[RetrievedChunk]
    ) -> tuple[AnswerDraft, int, int]:
        context = "\n\n".join(
            (
                f'<chunk id="{chunk.id}" title="{chunk.document_title}" '
                f'section="{chunk.section}" branch="{chunk.branch_id or "global"}">\n'
                f"{chunk.content}\n</chunk>"
            )
            for chunk in chunks
        )
        prompt = (
            f"分店：{branch_id}\n問題：{question}\n\n"
            f"CONTEXT：\n{context}\n\n"
            "請依規則產生結構化回答。"
        )

        response = await self.client.responses.parse(
            model=self.chat_model,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            text_format=AnswerDraft,
            text={"verbosity": "low"},
            reasoning={"effort": "low"},
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI response did not contain a parsed answer")
        usage = response.usage
        return parsed, usage.input_tokens if usage else 0, usage.output_tokens if usage else 0
