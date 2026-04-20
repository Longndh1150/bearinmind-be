# LangChain & LangGraph Refactor Plan

## 1. Phân Tích Vấn Đề Hiện Tại Tự Logs

Dựa vào logs thu thập được, hệ thống đang gặp các vấn đề nghiêm trọng về hiệu suất, luồng xử lý và độ ổn định khi giao tiếp với LLM:

### 1.1. Bottleneck về thời gian và các khoản "Gap" (Delay)
- **10 giây gap giữa các DB queries (15:17:52 - 15:18:03):** Có thể do init resource, synchronous blocking IO, hoặc connection pool chưa được tối ưu trước khi tạo hội thoại.
- **Hơn 1 phút gap trước LLM call đầu tiên (15:18:04 - 15:19:06):** Giống như một dev khác đã note, hệ thống đang bị *"chậm ở đoạn bắt đầu read data chroma"*. Hiện ChromaDB có thể đang được init đồng bộ (synchronous) ngốn block event loop của FastAPI trong quá trình tải collection hoặc warm-up embedding model.
- **Tổng thời gian cực lâu:** Toàn bộ request mất ~3 phút, trong đó thời gian gọi 3 lần LLM thực tế là ~12s + ~11.1s + ~22.9s + ~10.3s + ~1.8s (tổng khoảng 60s), nhưng lại bị overhead từ I/O và unoptimized orchestration.

### 1.2. Lãng phí tài nguyên Model
- `app/ai/agents/context_analyzer.py` đang dùng mô hình `llm_model_primary` (`google/gemini-2.5-pro`) cho một tác vụ cực kỳ đơn giản là Classify Intent. Result là prompt tốn 818 tokens, run time mất gần 12s, rất lãng phí. 

### 1.3. Lỗi Schema Validation do Parsing chay
- **Error `pydantic_core._pydantic_core.ValidationError`**: LLM trả về field `requirements` là `null` trong JSON, nhưng `OpportunityExtract` yêu cầu một `valid list`. Việc fetch bằng `json.loads` thủ công hoàn toàn thiếu cơ chế tự format fallback hoặc strict structure output như LangChain (ví dụ `.with_structured_output()`).

### 1.4. Thiết Kế Kiến Trúc
- Các call LLM hiện chạy hoàn toàn **tuần tự (Sequential)**.
- Memory/Context history chưa được nạp một cách hệ thống vào prompt cho logic phân tích ngữ cảnh, hiện đang cắt nối string chay.
- Các `prompts` đang là raw python string.

---

## 2. Kế Hoạch Refactor (Roadmap)

Để giải quyết vấn đề bằng hệ sinh thái **LangChain & LangGraph**, chúng ta sẽ tiến hành các bước như sau:

### Bước 1: Cập nhật DB Models & Schemas (User Preferences)
- Thêm field `preferred_language` dạng String vào bảng `User` (mặc định `'vi'`).
- Cập nhật Pydantic Schema của User, và đưa thông số này vào context (State) truyền cho LangGraph. Language cuối cùng sẽ là sự kết hợp giữa ngôn ngữ detect được bởi Context Analyzer và `preferred_language` (ví dụ fallback luôn về preferred language).

### Bước 2: Refactor Hệ thống Prompt bằng LangChain Templates
- Cấu trúc lại folder `app/ai/prompts/` để xuất ra các object `ChatPromptTemplate` (từ `langchain_core.prompts`).
- Tận dụng `MessagesPlaceholder` cho phần history.
- Có thể dùng `partial_variables` để inject sẵn các instruction cố định, giúp code gọi agent gọn gàng hơn.

### Bước 3: Áp dụng LangChain Structured Outputs & Models
- Chuyển `_llm_client()` thành tạo các class proxy như `ChatOpenAI` từ gói `langchain_openai`.
- Áp dụng `.with_structured_output(OpportunityExtract)` tại node Entity Extraction. Điều này ép LLM tuân thủ chặt chẽ Pydantic schema, giảm tỷ lệ null cho list.
- Mọi node phân tích đơn giản (như **Classify Intent / Context Analyzer**) phải ép buộc dùng **Secondary Model** (`google/gemini-3-flash-preview` hoặc tương đương) để tiết kiệm 10x thời gian chạy và token.

### Bước 4: Refactor luồng chạy thành LangGraph (AI Router)
- **Tạo GraphState:**
  ```python
  class GraphState(TypedDict):
      messages: list[BaseMessage]
      preferred_language: str
      detected_language: str
      intent: str
      extracted_entities: OpportunityExtract
      search_results: list[VectorSearchResult]
      final_response: str
  ```
- **Tách Nodes:**
  1. `node_analyze_context`: Dùng mô hình phụ phân tích intent, trả về intent và detected_language. Có kết hợp Memory history.
  2. `node_extract_entities`: Nếu intent = `find_units`, gọi tool extract (chạy strict schema). 
  3. `node_vector_search`: Nhận entities từ (2) và truy vấn ChromaDB (Cần wrap thành callable async không block).
  4. `node_summarize`: Nhận search_results và generate answer.
- **Tối ưu Hóa Parallel (Chạy song song):**
  Trong một số nhánh, nếu người dùng hỏi intent mà yêu cầu phân tích nhiều dimension (VD: phân tích context đồng thời trích xuất các entities không liên quan nhưng cần thiết), LangGraph cho phép chạy 2 node này song song.

### Bước 5: Giải Quyết Nút Thắt Storage (ChromaDB)
- Phân tích và cô lập hàm init của Chroma. Hiện tại lúc init Chroma embedding đang dùng `OpenRouterEmbeddingFunction`, nó request LLM APIs (bị timeout hoặc chờ init lâu). 
- Chuyển call của Chroma sang dạng `async` hoặc đẩy vào `ThreadPoolExecutor` để không block toàn bộ thread chính của FastAPI.

### Bước 6: Logging Callback
- Sửa stub `LLMLangchainCallbackStub` có sẵn trong `app/core/llm_tracking.py` kế thừa từ `langchain_core.callbacks.BaseCallbackHandler`. Khai báo nó vào param `callbacks=[...]` lúc khởi tạo LLM chain để log lại toàn bộ metrics.

---
**Kết quả mong đợi:** Thời gian phản hồi giảm từ 3 phút xuống dưới 10 giây/lượt, không còn bị lỗi validation 500 do parsing chay, logic rẽ nhánh dễ scale hơn nhờ LangGraph.