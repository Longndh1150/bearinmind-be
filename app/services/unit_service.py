import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unit import Unit, UnitExpert
from app.models.user import User
from app.schemas.chat import ChatResponse
from app.schemas.context import ConversationContext, DetectedLanguage

logger = logging.getLogger(__name__)


def _normalize_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        val = (raw or "").strip()
        if not val:
            continue
        key = val.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(val)
    return out


def _coerce_text_list(value: list[str] | str | None, *, split_csv: bool) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _normalize_text_list(value)
    raw = str(value).strip()
    if not raw:
        return []
    if split_csv:
        parts = [p.strip() for p in raw.split(",")]
        return _normalize_text_list(parts)
    return _normalize_text_list([raw])


def _extract_unit_codes(text: str | None) -> list[str]:
    if not text:
        return []
    # Supports patterns like DN1, D5, G10, HU1, HM1.
    return list({m.upper() for m in re.findall(r"\b(?:DN|D|G|HU|HM)\d+\b", text, flags=re.IGNORECASE)})


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

        added_tech_stack = _coerce_text_list(
            payload.get("added_tech_stack"),
            split_csv=True,
        )
        added_experts = _coerce_text_list(
            payload.get("added_experts"),
            split_csv=True,
        )

        if not added_tech_stack and not added_experts:
            answer = "Em không tìm thấy thông tin mới nào để thêm vào Dữ liệu năng lực ạ." if ctx.language == DetectedLanguage.vi else "No new capabilities provided to update."
            return ChatResponse(conversation_id=conv_id, answer=answer, suggested_actions=[])

        # Query DB to find the Unit corresponding to the user 
        user_email = (user.email or "").strip().lower()
        unit_rs = await session.execute(
            select(Unit).where(func.lower(Unit.contact_email) == user_email)
        )
        db_unit = unit_rs.scalars().first()

        if not db_unit:
            candidate_codes = _extract_unit_codes(message) + _extract_unit_codes(ctx.raw_message)
            for code in dict.fromkeys(candidate_codes):
                unit_by_code_rs = await session.execute(
                    select(Unit).where(
                        func.upper(Unit.code) == code
                    )
                )
                db_unit = unit_by_code_rs.scalars().first()
                if db_unit:
                    break

        if not db_unit:
            if ctx.language == DetectedLanguage.vi:
                answer = (
                    "Dạ em chưa xác định được đơn vị anh đang phụ trách từ tài khoản hiện tại. "
                    "Anh cho em xin mã đơn vị (ví dụ: DN1, D5, G10) để em cập nhật năng lực chính xác nhé."
                )
            else:
                answer = (
                    "I could not determine your unit from the current account. "
                    "Please provide your unit code (e.g. DN1, D5, G10) so I can update capabilities accurately."
                )
            return ChatResponse(conversation_id=conv_id, answer=answer, suggested_actions=[])

        # Append tech stack (case-insensitive de-dup)
        if added_tech_stack:
            current_tech = _normalize_text_list(list(db_unit.tech_stack) if db_unit.tech_stack else [])
            existing_tech_keys = {tech.casefold() for tech in current_tech}
            for tech in added_tech_stack:
                key = tech.casefold()
                if key not in existing_tech_keys:
                    current_tech.append(tech)
                    existing_tech_keys.add(key)
            db_unit.tech_stack = current_tech
            
        # Append experts: avoid duplicate names and merge focus areas when expert already exists.
        if added_experts:
            expert_rs = await session.execute(
                select(UnitExpert).where(UnitExpert.unit_id == db_unit.id)
            )
            existing_experts = list(expert_rs.scalars().all())
            existing_by_name = {
                (exp.name or "").strip().casefold(): exp for exp in existing_experts if exp.name
            }

            for exp_name in added_experts:
                key = exp_name.casefold()
                matched = existing_by_name.get(key)
                if matched:
                    merged_focus = _normalize_text_list(
                        list(matched.focus_areas) if matched.focus_areas else []
                    )
                    focus_keys = {tech.casefold() for tech in merged_focus}
                    for tech in added_tech_stack:
                        if tech.casefold() not in focus_keys:
                            merged_focus.append(tech)
                            focus_keys.add(tech.casefold())
                    matched.focus_areas = merged_focus
                    continue

                new_expert = UnitExpert(
                    unit_id=db_unit.id,
                    name=exp_name,
                    focus_areas=added_tech_stack or None,
                )
                session.add(new_expert)
                existing_by_name[key] = new_expert

        db_unit.capabilities_updated_at = datetime.now(UTC)
                
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
