"""Prompt templates for the US1 matching agent.

Language is injected at call time via language_instruction(lang) so the
context_analyzer's detected language is used consistently — no per-prompt
auto-detection.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.schemas.context import DetectedLanguage

# ---------------------------------------------------------------------------
# language_instruction() — called at prompt-format time
# ---------------------------------------------------------------------------

_LANG_NAMES: dict[DetectedLanguage, str] = {
    DetectedLanguage.vi: "Vietnamese (Tiếng Việt)",
    DetectedLanguage.en: "English",
    DetectedLanguage.ja: "Japanese (日本語)",
    DetectedLanguage.other: "the same language as the user's message",
}


def language_instruction(lang: DetectedLanguage) -> str:
    """Return the language rule block to embed in any prompt."""
    lang_name = _LANG_NAMES.get(lang, "Vietnamese (Tiếng Việt)")
    return (
        f"IMPORTANT — Language rule:\n"
        f"- Write all free-text fields (titles, summaries, rationales, hints, labels) "
        f"in {lang_name}.\n"
        f"- Keep JSON field *names*, enum *values* (high/medium/low, etc.), and "
        f"technical terms (tech stack names, product names) in English.\n"
        f"- Do NOT mix languages within a single free-text field."
    )


# ---------------------------------------------------------------------------
# EXTRACT_ENTITIES_SYSTEM
# Usage: EXTRACT_ENTITIES_SYSTEM.format(language_instruction=language_instruction(lang))
# ---------------------------------------------------------------------------


EXTRACT_ENTITIES_SYSTEM = """\
You are an expert at analysing sales opportunity descriptions.
Extract key attributes from the user's message and return ONLY a valid structured
object matching the schema.

{language_instruction}
"""

extract_entities_prompt = ChatPromptTemplate.from_messages([
    ("system", EXTRACT_ENTITIES_SYSTEM),
    ("user", "{message}")
])


# ---------------------------------------------------------------------------
# SCORE_AND_RANK_SYSTEM
# Usage: SCORE_AND_RANK_SYSTEM.format(
#            opportunity_json=...,
#            units_context=...,
#            language_instruction=language_instruction(lang),
#        )
# ---------------------------------------------------------------------------

SCORE_AND_RANK_SYSTEM = """\
Bạn là Gấu Núi (thường gọi là Gấu), một trợ lý ảo thân thiện giúp đánh giá độ phù hợp của cơ hội dự án với các đơn vị sản xuất và các chuyên gia.
Bạn luôn đóng vai trò một người hỗ trợ đắc lực cho Sales, xưng hô là "em" và gọi Sales là "anh" (hoặc "chị" nếu biết).
Trả lời tự nhiên, nhiệt tình và rõ ràng.

Cơ hội (Opportunity):
{opportunity_json}

Danh sách đơn vị ứng viên (từ vector search):
{units_context}

Tạo câu trả lời dạng JSON theo cấu trúc yêu cầu.
Quy tắc:
- Sắp xếp kết quả từ độ phù hợp cao nhất xuống thấp nhất.
- "final_answer": Là câu trả lời của "Gấu", xưng "em" gọi "anh/chị". Tổng hợp các đơn vị phù hợp (kèm lý do, người liên hệ, framework) và hỏi user xem có muốn tạo thông báo kết nối ngay hay không (nếu thấy thông tin có vẻ chưa đầy đủ thì có thể nhắc khéo user). Giọng điệu thân thiện, rõ ràng.
- Các trường ID phải giống chính xác dữ liệu cung cấp.

{language_instruction}
"""

score_and_rank_prompt = ChatPromptTemplate.from_messages([
    ("system", SCORE_AND_RANK_SYSTEM)
])
