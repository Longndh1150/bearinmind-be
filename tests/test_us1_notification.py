from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.context import ChatIntent, ConversationContext, DetectedLanguage, SessionMeta
from app.schemas.llm import OpportunityExtract
from app.services.chat_service import ChatService

# Giả lập môi trường Test Unit nhỏ cho handle notification

@pytest.mark.asyncio
async def test_handle_send_notification_success():
    session = AsyncMock()
    user = MagicMock()
    user.email = "test.sales@rikkeisoft.com"
    
    # Fake session_meta
    session_meta = SessionMeta(
        suggested_units=[{
            "id": str(uuid4()),
            "name": "DN1",
            "code": "DN1-01",
            "head_id": str(uuid4())
        }]
    )
    
    # Fake opportunity extract with full required info
    extract = OpportunityExtract(
        title="D365 Project",
        deadline="1 week",
        scope="CRM",
        market="Japan",
        requires_estimate_or_demo=True
    )
    
    # Fake context
    ctx = ConversationContext(
        intent=ChatIntent.send_notification,
        language=DetectedLanguage.vi,
        confidence=1.0,
        opportunity_hint="DN1",
        raw_message="Thông báo tới DN1 hộ tôi"
    )
    
    with patch('app.services.notification_service.create_opportunity_match_unit_notification', new_callable=AsyncMock) as mock_create:
        res = await ChatService._handle_send_notification(
            session=session,
            ctx=ctx,
            extracted=extract,
            conv_id=uuid4(),
            session_meta=session_meta,
            user=user
        )
        
        # Check success
        assert mock_create.called
        assert "thành công" in res.answer.lower()
        
@pytest.mark.asyncio
async def test_handle_send_notification_missing_unit():
    session = AsyncMock()
    user = MagicMock()
    
    session_meta = SessionMeta(
        suggested_units=[{
            "id": str(uuid4()),
            "name": "DN2", # Only DN2 is in list
            "code": "DN2",
            "head_id": str(uuid4())
        }]
    )
    extract = OpportunityExtract()
    ctx = ConversationContext(
        intent=ChatIntent.send_notification,
        language=DetectedLanguage.vi,
        confidence=1.0,
        opportunity_hint="DN1", # User wants DN1
        raw_message="Gửi DN1"
    )
    
    res = await ChatService._handle_send_notification(session, ctx, extract, uuid4(), session_meta, user)
    
    # Unit missing, so shouldn't create
    assert "không tìm thấy" in res.answer.lower()
