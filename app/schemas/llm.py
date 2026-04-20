from __future__ import annotations

from pydantic import BaseModel, Field


class LLMJsonParseError(BaseModel):
    """Use as a structured error when LLM output isn't valid JSON for a target schema."""

    message: str
    raw_output: str


class OpportunityExtract(BaseModel):
    """Example schema for parsing structured JSON from an LLM."""

    title: str | None = None
    client: str | None = None
    market: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    notes: str | None = None
    
    # Thêm các field cho Notification/Kết nối (US1)
    deadline: str | None = Field(default=None, description="Timeline hoặc deadline của dự án/proposal, ví dụ: '1 tuần', '15/10', v.v.")
    scope: str | None = Field(default=None, description="Phạm vi công việc hoặc yêu cầu vụ thể, ví dụ: 'CRM', 'BC', 'Mobile app'")
    customer_stage: str | None = Field(default=None, description="Khách hàng đang ở giai đoạn nào, ví dụ: 'Đang tìm hiểu', 'Đã có requirement rõ'")
    requires_estimate_or_demo: bool | None = Field(default=None, description="Có cần estimate sơ bộ hoặc demo không")
    
    # Thêm các field cho Opportunity Creation
    description: str | None = Field(default=None, description="Mô tả chi tiết về cơ hội (do AI tự sinh dựa trên ngữ cảnh nếu chưa có)")

