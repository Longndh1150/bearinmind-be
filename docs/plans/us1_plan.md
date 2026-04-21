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

## 6. Scenario Demo – US1: Sales tìm đơn vị + làm rõ cơ hội

**1. Sales chat với Gấu:**
> "Gấu ơi, tôi đang có một cơ hội ở Tokyo về Microsoft Dynamics 365, cần một Senior có thể tham gia làm proposal. Bạn giúp tôi xem đơn vị nào phù hợp không?"

**2. Gấu trả lời:**
> "Chào anh ạ, em là Gấu đây! Em đã rà soát hệ thống và tìm thấy 3 đơn vị có năng lực liên quan đến Microsoft Dynamics 365 cho cơ hội tại Tokyo lần này.
> 
> Trong đó, đơn vị **DN1** là ứng cử viên sáng giá nhất vì họ có đội ngũ Senior cực mạnh, chuyên làm presale và proposal cho thị trường Nhật (từng làm cho Fujitsu). Anh nên ưu tiên kết nối với anh **ThangLB** bên đó nhé. Các đơn vị khác như D5 và G10 cũng có kinh nghiệm nhưng mức độ chuyên sâu về D365 để viết proposal thì chưa bằng DN1.
> 
> Thông tin chi tiết em đã liệt kê bên dưới, anh xem qua nhé. Nếu anh thấy ưng ý, anh có muốn em hỗ trợ tạo thông báo kết nối ngay với các đơn vị này không ạ? (Tiện thể, nếu anh có thêm thông tin về quy mô dự án thì nhắn em để em lọc kỹ hơn cho anh nhé!)"

**3. Sales trả lời:**
> "Ok Gấu, dự án này là triển khai D365 cho mảng bán lẻ, khách hàng là AEON tại Nhật Bản nhé. Quy mô dự kiến cần khoảng 10 members trong 6 tháng, ngân sách cho Phase 1 tầm 200k USD. Gấu giúp anh tạo cơ hội và thông báo kết nối tới DN1 luôn nhé!"

**4. Gấu trả lời:**
> "Dạ vâng, em đã lưu thông tin cơ hội dự án AEON (Retail) với quy mô $200k vào hệ thống rồi ạ! Để bộ phận **DN1** có thể chuẩn bị tốt nhất và lên lịch hỗ trợ, anh bổ sung giúp em vài chi tiết cho thông báo nhé:
> - Timeline dự kiến nộp proposal (deadline khi nào?)
> - Khách hàng đang ở giai đoạn nào (đang tìm hiểu hay đã có requirement rõ ràng?)
> - Có cần DN1 làm estimate sơ bộ hoặc demo hệ thống luôn không ạ?"

**5. Sales trả lời:**
> "Deadline nộp proposal là thứ Sáu tuần sau nha. Khách hàng đã có requirement sơ bộ rồi, cần gửi estimate và chuẩn bị 1 buổi demo hệ thống."

**6. Gấu trả lời:**
> "Dạ vâng, em đã cập nhật và gửi thông báo kết nối cơ hội AEON tới DN1, đính kèm đầy đủ yêu cầu estimate và chuẩn bị demo cho deadline thứ Sáu tuần sau rồi ạ. Gấu chúc dự án thành công chốt được deal bự nha! 🐻✨"
