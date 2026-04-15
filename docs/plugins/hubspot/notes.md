## HieuNN (PM)

(Optional) Trong phần contact, nhiều khi tên contact (PIC) sẽ không được chuẩn hoá (kì vọng viết tên bằng chữ Hán Nhật nhưng thực tế lại viết bằng latin), nếu được thì mong muốn AI phát hiện và warning

--> Idea: có thể thêm hint đơn giản vào form?

## HoangVT (FE Dev), 13/04/2026 21:08

Giờ anh cần 3 APIs

https://developers.hubspot.com/docs/api-reference/legacy/crm/pipelines/v1/get-pipelines#get-all-pipelines-for-a-specified-object-type
 
https://developers.hubspot.com/docs/api-reference/legacy/crm/properties/get-properties
 
replicate 2 api ni, {objectType} là "deals" nha
 
create deal: https://developers.hubspot.com/docs/api-reference/legacy/crm/objects/deals/v1/post-deals-v1-deal#create-a-deal

```markdown
Hi [Name], can you help replicate our current direct HubSpot integration behind our backend API so frontend can switch from `direct` to `backend` mode without behavior changes?
 
## Scope
 
Please expose backend endpoints for the same data we currently read/write from HubSpot:
 
1. **Get deal pipelines**
   - HubSpot source: `GET /crm-pipelines/v1/pipelines/{objectType}?includeInactive=EXCLUDE_DELETED`
   - FE expects: list of pipelines + stages (id/label/displayOrder/archived/metadata)
 
2. **Get deal properties**
   - HubSpot source: `GET /crm/v3/properties/{objectType}?dataSensitivity=non_sensitive`
   - FE expects: `results` with property metadata (`name`, `label`, `type`, `fieldType`, `options`, `formField`, `calculated`, `modificationMetadata.readOnlyValue`, etc.)
 
3. **Get users (for owner/sub-owner fields)**
   - HubSpot source: `GET /settings/v3/users`
   - FE needs: user id, email, firstName, lastName (or normalized fullName)
 
4. **Create deal**
   - HubSpot source: `POST /deals/v1/deal/`
   - FE sends payload shaped as:
     - `properties: [{ name, value }]`
     - no associations for companies (companies sent as normal property)
   - FE expects response normalized as:
     - `{ success: boolean, message: string, hubspot_deal_id: string | null }`
 
## Important behavior to keep
 
- Date properties (like `closedate`) must be valid HubSpot long timestamps.
- Property names must come from HubSpot property metadata (source-of-truth), not hardcoded frontend assumptions.
- Please keep response shape stable for frontend switching (`VITE_HUBSPOT_SOURCE=backend`).
 
## Proposed backend routes (current FE conventions)
 
- `GET /api/v1/hubspot/pipelines`
- `GET /api/v1/hubspot/properties/deals`
- `GET /api/v1/hubspot/users`
- `POST /api/v1/hubspot/deals`
 
If you prefer different route naming, please share the final contract and I’ll align FE.
```

https://api.hubapi.com/settings/v3/users api ni để lấy users

## HoangVT (FE Dev), 14/04/2026 16:32

3 cái api để lấy user, pipeline, properties em bọc lại, khi user call "/hubspot" thì api trả về payload ..., rồi khi anh nhấn lưu thì cũng post như kiểu 1 tin nhắn thôi

## HoangVT (FE Dev), 14/04/2026 22:32

Cái Capability Form em đang tính làm cai form a?
Hình như bữa a Thắng muốn làm như chat luôn á

```
HubSpot API – Các field cần sử dụng
1. Properties API
Trả về danh sách toàn bộ properties trong dashboard.
Chỉ cần filter các property có formField = true.
Các field quan trọng:
  - name: internal name (dùng như property ID khi tạo deal)
  - label: tên hiển thị
  - options: dùng cho các field dạng dropdown. Quan tâm value (coi như item ID)

2. Pipelines API
Trả về danh sách pipelines trong dashboard.
Các field quan trọng:
  - pipelineId: ID của pipeline
  - stages: danh sách stage trong pipeline. Quan tâm stageId

3. Users API
Trả về danh sách user trong HubSpot.
Field cần dùng:
  - id: user ID
```

Về tạo deal:  thì anh đang expect payload sẽ như thế này
{
  "properties": [
    {
      "name": "dealname",
      "value": "Test with pipeline"
    },
    {
      "name": "dealsubowner",
      "value": "90821048"
    },
    {
      "name": "hubspot_owner_id",
      "value": "90617141"
    },
    {
        "name": "pipeline",
        "value": "default"
    },
    {
        "name": "dealstage",
        "value": "stage_1"
    },
    {
      "name": "tech_stack",
      "value": ["kotlin", "dot_net"]
     }
  ],
  "associations": {
    "associatedCompanyIds": [
      
    ],
    "associatedVids": [
      
    ]
  }
}

Bỏ qua cái associations đi

Nếu em muốn them thông tin anh có thể wrap cái payload này, với them field khác. Em có thể lấy nguyên cục ở trên gọi API tới hubspot là tạo được deal.
Nhưng nếu em muốn từ cái payload này, để đưa data cho AI học, thì em cần map ngược cái trường "name", thành label (từ properties của hubspot), và map "value" thành label. Ví dụ:
{
      "name": "tech_stack",
      "value": ["kotlin", "dot_net"]
     },
 
Thì em lấy cái property id là "tech_stack" tìm trong list properties ở trên để biết được với id là "tech_stack" thì label là gì - ở đây là "Tech stack for this deal", map "Kotlin" thành "Proficient in Kotlin" chẳng hạn.
Vì cái property id và option id ni nó không luôn luôn là kiểu text như này, đôi khi nó là 1 dãy số, text random chẳng hạn

---

## BE implementation pointers (2026-04-15)

- **Bootstrap (1 call):** `GET /api/v1/hubspot/bootstrap` — trả về `pipelines`, `properties` (đã lọc `formField=true`), `users`. Cần JWT như các route HubSpot khác.
- **Properties có lọc:** `GET /api/v1/hubspot/properties/deals?form_field_only=true`
- **Humanize cho AI:** `app.services.hubspot_service.humanize_deal_properties()` — map `name` → label, option `value` → option label (theo note reverse mapping ở trên).
- **Smoke test (chỉ khi `APP_ENV` ≠ production):**
  - `GET /api/v1/dev/smoke/llm` — kiểm tra `LLM_API_KEY`
  - `GET /api/v1/dev/smoke/hubspot` — kiểm tra `HUBSPOT_API_KEY` (đếm users, không lộ key)
