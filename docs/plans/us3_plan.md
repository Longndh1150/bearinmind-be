# Scenario Demo – US3: Dleader cập nhật thông tin cho đơn vị

## 1. Kịch bản (Multi-turn Chat)
1. **Dlead vào màn hình cập nhật thông tin**
   - Update xong bấm "Lưu năng lực" bình thường (Luồng CRUD / Frontend cơ bản).

2. **Dlead chat với Gấu (Turn 1)**
   - *Dlead:* "Đơn vị tôi vừa tuyển được 1 chuyên gia về Automation Test nhé"

3. **Gấu hỏi chi tiết (Turn 2)**
   - *Gấu:* "Cho em xin tên ạ, và chuyên môn ngoài Automation Test còn có gì nữa ko anh?"

4. **Dlead cung cấp thông tin (Turn 3)**
   - *Dlead:* "Tên là Lê Đức Thắng nhé, ngoài Auto ra còn có cả Performance, Security nữa"

5. **Gấu xác nhận và lưu thông tin (Turn 4)**
   - *Gấu:* "Dạ vâng, để em lưu vào Năng lực đơn vị, có bên nào cần em sẽ giới thiệu ạ."
   - **Hành động ngầm:** Background hệ thống tự động update vào bảng Năng lực (Units) của đơn vị đó:
     - Thêm `Automation Test`, `Performance`, `Security` vào mảng/cột Techstack.
     - Thêm `Lê Đức Thắng` vào mảng/cột Chuyên gia (Experts).

---

## 2. Phương án Triển khai (Đảm bảo Không Ảnh Hưởng Các Intent Khác)

Để hệ thống phân tích ngữ cảnh (LangGraph / Gemini) xử lý liền mạch mà không can thiệp (conflict) vào luồng `send_notification` hay `query_database` hiện tại, ta áp dụng mô hình **New Tool Intent + LLM Multi-Turn Context**.

### Bước 2.1. Bổ sung Intent và Schema
- **File cần chỉnh sửa:** `app/models/chat.py` (hoặc Schema quy định Intent)
- **Thích ứng:** Bổ sung `update_unit_capabilities` vào Enum `ChatIntent`.
- **File Cấu trúc Tool LLM:** `app/ai/agents/context_analyzer.py`
  Ta cho AI thêm một Tool (Pydantic Model) chuyên dụng cho việc Cập nhật. Trong Tool này khai báo rõ LLM có **2 trạng thái (action)**:
  ```python
  class ToolUpdateUnitCapabilities(BaseModel):
      """Sử dụng khi người dùng (Dlead) muốn cập nhật, thêm thông tin năng lực, chuyên gia, tech stack... cho đơn vị của họ."""
      intent: Literal["update_unit_capabilities"]
      action: Literal["ask_for_clarification", "execute_update"]
      # ask_for_clarification: Đã bắt được ý muốn update nhưng thiếu thông tin (vd: thiếu tên người, thiếu kỹ năng...)
      # execute_update: Đã gom đủ cả tên chuyên gia / stack => Gọi hành động update ngay
      missing_info_question: Optional[str] = Field(description="Câu hỏi hỏi thêm nếu action = ask_for_clarification")
      added_tech_stack: Optional[List[str]] = Field(description="Danh sách kỹ năng technical mới (nếu có)")
      added_experts: Optional[List[str]] = Field(description="Danh sách tên chuyên gia mới (nếu có)")
  ```

### Bước 2.2. Khai thác Lịch sử Hội thoại (Multi-turn)
- LLM (Gemini) trong LangGraph đã thiết kế đọc lại History list. Vì vậy, ở **Turn 1 và 2**, LLM sẽ output ra `action="ask_for_clarification"`. 
- Đến **Turn 3**, đọc được tên "Lê Đức Thắng" và "Performance, Security", nó lập tức đổi `action="execute_update"` và list ra `added_tech_stack=["Automation Test", "Performance", "Security"]`, `added_experts=["Lê Đức Thắng"]`.

### Bước 2.3. Xử lý Logic Backend tại Service
- **File cần chỉnh sửa:** `app/services/chat_service.py`
- **Luồng Code (Block `elif intent == ChatIntent.update_unit_capabilities`):**
  - Extract `action` từ LLM Payload trả ra.
  - Nếu là `ask_for_clarification`: Trả về nguyên văn câu hỏi cho frontend hiển thị (ví dụ: *"Cho em xin tên ạ..."*) -> **Kết thúc block, chưa chạm vào DB.**
  - Nếu là `execute_update`:
    - Lấy `session_meta` hoặc Dựa vào Token `user.id` (Dlead đang đăng nhập), query lên DB tìm ra `Unit` mà user này đang phụ trách.
    - Lấy list `Techstack` và `Experts` cũ trong DB.
    - **Nối (append)** mảng mới `added_tech_stack` và `added_experts` vừa parse được vào.
    - `session.commit()` để lưu dữ liệu.
    - Gán câu trả lời tĩnh mang tính confirm (ví dụ: *"Dạ vâng, để em lưu vào Mảng năng lực..."*)
    - Trả kết quả về Frontend.

### Bước 2.4. Đảm bảo Model SQL chịu được Mảng Dữ Liệu
- Cần đảm bảo model SQLAlchemy `app/models/unit.py` (hoặc bảng năng lực tương ứng) đang khai báo kiểu dữ liệu List/Array/JSONB cho Techstack và Chuyên gia.
- Cập nhật logic để hỗ trợ Update chèn mảng thay vì đè toàn bộ mảng.

### 💡 Lý do phương án này An Toàn
- **Cô lập Prompt/Tool:** Tool `ToolUpdateUnitCapabilities` có description khác biệt hoàn toàn với `ToolSendNotification`. Bằng cách quy định rõ *"Sử dụng khi user thêm/tuyển thông tin chuyên gia..."*, LLM không bao giờ bị Confuse Intent.
- Tận dụng sức mạnh LLM Pydantic Extraction giúp Backend không cần thiết lập state machine "Đang chờ update hay không" (State này sẽ tự động suy luận từ History Chat) giúp code backend rất clean và không lo lỗi đồng bộ.