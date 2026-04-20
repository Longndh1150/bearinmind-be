# Plan: Cập nhật Assistant "Gấu Núi" (Use Case 1)

## 1. Cập nhật Persona và Xưng hô (Phase 1)
- **File cần sửa**: Các file prompt hệ thống (VD: app/ai/prompts/*.py hoặc context.py).
- **Chi tiết**:
  - Thêm system instruction thiết lập danh tính: "Bạn là một trợ lý ảo tên là Gấu Núi (thường gọi là Gấu), có nhiệm vụ hỗ trợ Sales tìm kiếm và kết nối cơ hội dự án với các đơn vị sản xuất (Unit) phù hợp."
  - Cấu hình ngôn ngữ & xưng hô: Mặc định luôn xưng "em" và gọi người dùng là "anh" (hoặc "chị" nếu có context), giọng điệu thân thiện, nhiệt tình.

## 2. Cập nhật Schema để bóc tách thông tin (Phase 2)
- **File cần sửa**: app/schemas/llm.py
- **Chi tiết**: Cập nhật model OpportunityExtract để LLM có thể trích xuất thêm các trường phục vụ tạo Notification:
  - deadline (Timeline dự kiến)
  - scope (Phạm vi yêu cầu: CRM, BC, v.v.)
  - customer_stage (Giai đoạn của khách hàng)
  - requires_estimate_or_demo (Có cần estimate/demo không)

## 3. Skill: Hỏi xác thực / Thu thập thông tin (Phase 3)
- **File cần sửa**: app/ai/agents/context_analyzer.py (và flow xử lý chat chính)
- **Chi tiết**:
  - Tích hợp logic xử lý trước khi thực hiện hành động chuyển tiếp. Khi user chat yêu cầu "kết nối/thông báo tới DN1", hệ thống kiểm tra đối tượng OpportunityExtract xem đã đủ các trường bắt buộc (như deadline, scope...) chưa.
  - Nếu thiếu: LLM sẽ không gọi tool notify ngay mà sẽ gọi ToolClarify (hoặc một tool chuyên dụng như ToolRequestMissingInfo) với clarification_needed chứa danh sách các thông tin cần hỏi thêm, và prompt LLM sinh ra câu hỏi thân thiện (như bước 4 trong kịch bản).

## 4. Tích hợp tính năng tạo Notification (Phase 4)
- **File cần sửa**: app/ai/agents/context_analyzer.py và luồng agent (chat_agent.py nếu có).
- **Chi tiết**:
  - **Khai báo Tool mới**: Tạo ToolSendNotification chứa các argument mapping vào schema NotificationCreateOpportunityMatchUnitRequest.
  - **Schema mapping**: Mapping các thông tin đã trích xuất từ user (scope, timeline, note) và context (opportunity_id, unit_id của DN1) vào OpportunityMatchUnitNotificationDetails.
  - **Xử lý backend**: Khi LLM gọi ToolSendNotification, backend sẽ thực thi gọi xuống service (VD: 
otification_service.create(...)) để tạo thông báo thực sự lưu vào DB.

## 5. Quản lý Context đa lượt (Multi-turn) (Phase 5)
- **Cơ chế hoạt động**: Đảm bảo session hiện tại nhớ được danh sách các Unit đã suggest (Ví dụ: [DN1, D5]). Khi user trả lời "DN1", LLM có thể map chuỗi "DN1" sang UUID thực tế tương ứng.
- **Workflow**:
  - Lượt 1-2: Trích xuất context -> search semantic -> trả ra context chứa UUID của DN1.
  - Lượt 3-4: Bổ sung intent "Kết nối cơ hội", nhận diện đối tượng là DN1 (từ UUID đã lưu) -> Triggers check missing info -> Xin thêm info.
  - Lượt 5-6: Extract đủ info -> Triggers action gọi Notification Tạo API -> Trả lời user thành công.
