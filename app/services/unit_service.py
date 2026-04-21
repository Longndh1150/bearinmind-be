import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unit import Unit, UnitExpert
from app.models.user import User
from app.schemas.chat import ChatResponse
from app.schemas.context import ConversationContext, DetectedLanguage

logger = logging.getLogger(__name__)

class UnitService:
    @staticmethod
    async def handle_update_capabilities(
        session: AsyncSession, 
        ctx: ConversationContext, 
        conv_id: UUID, 
        message: str, 
        user: User
    ) -> ChatResponse:
        """Isolated Chat Handler for the update_capabilities context intent (US3)."""
        
        # 1. Action = ask_for_clarification
        if ctx.clarification_needed:
            logger.info(f"Asking clarification for US3 capability update in conversation: {conv_id}")
            answer = ctx.clarification_needed
            return ChatResponse(
                conversation_id=conv_id,
                answer=answer,
                suggested_actions=[]
            )
            
        # 2. Action = execute_update
        payload = {}
        try:
            if ctx.opportunity_hint:
                payload = json.loads(ctx.opportunity_hint)
        except Exception as e:
            logger.warning(f"Could not parse opportunity_hint payload: {e}")

        added_tech_stack = payload.get("added_tech_stack") or []
        added_experts = payload.get("added_experts") or []

        if not added_tech_stack and not added_experts:
            answer = "Em không tìm thấy thông tin mới nào để thêm vào Dữ liệu năng lực ạ." if ctx.language == DetectedLanguage.vi else "No new capabilities provided to update."
            return ChatResponse(conversation_id=conv_id, answer=answer, suggested_actions=[])

        # Query DB to find the Unit corresponding to the user 
        user_email = user.email.lower() if user.email else ""
        unit_rs = await session.execute(select(Unit).where(Unit.contact_email == user_email))
        db_unit = unit_rs.scalars().first()

        if not db_unit:
            answer = "Xin lỗi, em không tìm thấy đơn vị nào mà anh đang quản lý (contact_email không khớp)." if ctx.language == DetectedLanguage.vi else "Sorry, I could not find a unit associated with your account."
            return ChatResponse(conversation_id=conv_id, answer=answer, suggested_actions=[])

        # Append tech stack
        if added_tech_stack:
            current_tech = list(db_unit.tech_stack) if db_unit.tech_stack else []
            for tech in added_tech_stack:
                if tech not in current_tech:
                    current_tech.append(tech)
            db_unit.tech_stack = current_tech
            
        # Append experts
        if added_experts:
            for exp_name in added_experts:
                new_expert = UnitExpert(
                    unit_id=db_unit.id,
                    name=exp_name,
                    focus_areas=added_tech_stack
                )
                session.add(new_expert)
                
        await session.commit()
        logger.info(f"Updated unit '{db_unit.name}' with techs: {added_tech_stack} and experts: {added_experts}")

        if ctx.language == DetectedLanguage.vi:
            tech_str = ", ".join(added_tech_stack) if added_tech_stack else "Không có"
            exp_str = ", ".join(added_experts) if added_experts else "Không có"
            answer = (
                f"Dạ vâng, em đã lưu thông tin vào Năng lực của đơn vị **{db_unit.name}** thành công rồi ạ!\n\n"
                f"- **Kỹ năng mới:** {tech_str}\n"
                f"- **Chuyên gia mới:** {exp_str}\n\n"
                f"Có dự án nào cần em sẽ chủ động giới thiệu nhé! 🐻✨"
            )
        else:
            answer = f"I've successfully updated your unit {db_unit.name} with the new capabilities!"
            
        return ChatResponse(
            conversation_id=conv_id,
            answer=answer,
            suggested_actions=[],
        )
