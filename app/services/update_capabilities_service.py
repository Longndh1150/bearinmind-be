import logging
from uuid import UUID

from app.schemas.chat import ChatResponse
from app.schemas.context import ConversationContext, DetectedLanguage
from app.ai.agents.update_capabilities_agent import parse_and_validate_capabilities_request

logger = logging.getLogger(__name__)

async def handle_update_capabilities(ctx: ConversationContext, conv_id: UUID, message: str) -> ChatResponse:
    """Isolated Chat Handler for the update_capabilities context intent (US3)."""
    # Parse request and validate target unit via US3 isolated flow
    parsed_req = parse_and_validate_capabilities_request(message, ctx.language)
    
    logger.info(f"Parsed US3 capability request successfully for conversation: {conv_id}")
    
    # Structured standard LLM handler string responses based on intent locale
    if ctx.language == DetectedLanguage.vi:
        answer = "Đã tiếp nhận yêu cầu cập nhật năng lực đơn vị. Đang tiến hành xử lý."
    elif ctx.language == DetectedLanguage.ja:
        answer = "ユニットのケイパビリティ更新リクエストを受け付けました。処理中です。"
    else:
        answer = "Received unit capabilities update request. Processing..."
        
    return ChatResponse(
        conversation_id=conv_id,
        answer=answer,
        suggested_actions=[],
    )
