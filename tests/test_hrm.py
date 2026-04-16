import asyncio
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uuid

import requests

from app.db.session import AsyncSessionLocal
from app.models.unit import Unit

BASE_URL = "http://localhost:8000/api/v1"
TEST_UNIT_ID = "c5b2c3d4-9999-9999-9999-999999999999"  # ID hoàn toàn độc lập cho test

async def setup_mock_unit():
    async with AsyncSessionLocal() as session:
        u = await session.get(Unit, TEST_UNIT_ID)
        if not u:
            new_u = Unit(
                id=TEST_UNIT_ID,
                code="TEST_D365",
                name="Rikkei Test Automation Division",
                status="active",
                contact_name="Test Bot"
            )
            session.add(new_u)
            await session.commit()
            print(f"🔧 Đã chèn mock Unit test ({TEST_UNIT_ID}) vào Database thành công!")

async def teardown_mock_unit():
    async with AsyncSessionLocal() as session:
        u = await session.get(Unit, TEST_UNIT_ID)
        if u:
            await session.delete(u)
            await session.commit()
            print(f"♻️ Đã Rollback: Xóa hoàn toàn Unit test ({TEST_UNIT_ID}) khỏi Database để dọn dẹp!")

def run_test():
    print("================== BẮT ĐẦU TEST FLOW ==================")
    # 1. Đăng ký & Đăng nhập để lấy Token
    creds = {"email": f"test_{uuid.uuid4().hex[:6]}@rikkeisoft.com", "password": "password123", "full_name": "Test User"}
    requests.post(f"{BASE_URL}/auth/register", json=creds)
    
    login_res = requests.post(f"{BASE_URL}/auth/login", json={"email": creds["email"], "password": creds["password"]})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    print("✅ B1: Đã lấy được Bearer Token!")

    # 2. Test API 1: Kiểm tra Unit (TRƯỚC khi cập nhật)
    print(f"\n🔍 B2: Đang gọi GET /units/{TEST_UNIT_ID} (Trước khi cập nhật)...")
    get_before_res = requests.get(f"{BASE_URL}/units/{TEST_UNIT_ID}", headers=headers)
    if get_before_res.status_code == 200:
        print("✅ Current Capabilities:", get_before_res.json()["capabilities"].get("tech_stack"))
    else:
        print("❌ Lỗi GET:", get_before_res.status_code, get_before_res.text)

    # 3. PUT /units/{id}/capabilities (Cập nhật năng lực)
    capabilities_payload = {
        "tech_stack": ["Java", "Spring Boot", "AWS"],
        "experts": [{"name": "Nguyen Van A", "focus_areas": ["Cloud Architecture"]}],
        "case_studies": [{"title": "Hệ thống Ecommerce", "tech_stack": ["Java"]}],
        "notes": "Đã cập nhật sau quý 1"
    }

    print(f"\n🚀 B3: Đang gọi PUT /units/{TEST_UNIT_ID}/capabilities...")
    put_res = requests.put(f"{BASE_URL}/units/{TEST_UNIT_ID}/capabilities", json=capabilities_payload, headers=headers)
    
    if put_res.status_code == 200:
        print("✅ PUT Capabilities thành công! Response:", put_res.json()["capabilities"]["tech_stack"])
    else:
        print("❌ Lỗi PUT Capabilities:", put_res.status_code, put_res.text)

    # 4. Kiểm tra Unit (SAU khi cập nhật)
    print(f"\n🔍 B4: Đang gọi GET /units/{TEST_UNIT_ID} (Sau khi nạp thêm)...")
    get_after_res = requests.get(f"{BASE_URL}/units/{TEST_UNIT_ID}", headers=headers)
    if get_after_res.status_code == 200:
        print("✅ Ký hiệu APPEND đã thành công. Tech stack mới:", get_after_res.json()["capabilities"]["tech_stack"])
    else:
        print("❌ Lỗi GET:", get_after_res.status_code, get_after_res.text)

    # 5. Xoá 1 capability
    print("\n🗑️ B5: Đang gọi DELETE 1 tech cụ thể (?tech_to_remove=AWS)...")
    del_one_res = requests.delete(f"{BASE_URL}/units/{TEST_UNIT_ID}/capabilities", params={"tech_to_remove": "AWS"}, headers=headers)
    if del_one_res.status_code == 200:
        print("✅ Xóa lẻ công nghệ thành công. Response:", del_one_res.json())
        get_check = requests.get(f"{BASE_URL}/units/{TEST_UNIT_ID}", headers=headers).json()
        print("   -> Tech_stack còn lại (Mất chữ AWS):", get_check["capabilities"].get("tech_stack"))
    
    # 6. Xoá TOÀN BỘ capability
    print("\n💥 B6: Đang gọi lệnh DELETE toàn bộ năng lực...")
    del_all_res = requests.delete(f"{BASE_URL}/units/{TEST_UNIT_ID}/capabilities", headers=headers)
    if del_all_res.status_code == 200:
        print("✅ Đã xóa toàn bộ năng lực (bao gồm expert, case study).")
        get_check = requests.get(f"{BASE_URL}/units/{TEST_UNIT_ID}", headers=headers).json()
        print("   -> Tech_stack sau khi dọn sạch hoàn toàn:", get_check["capabilities"].get("tech_stack"))

    # 7. Test lệnh Chat AI cập nhật năng lực
    chat_payload = {
        "message": "Tôi muốn cập nhật năng lực bổ sung công nghệ AI."
    }

    print("\n🚀 B7: Đang test Agent độc lập (POST /chat) Context update_capabilities...")
    chat_res = requests.post(f"{BASE_URL}/chat", json=chat_payload, headers=headers)
    
    if chat_res.status_code == 200:
        chat_data = chat_res.json()
        print("✅ POST Chat thành công! Lời AI:", chat_data['answer'])

async def main():
    try:
        # Bước 1: Setup Môi trường Dữ Liệu
        await setup_mock_unit()
        # Bước 2: Chạy Core Test logic
        run_test()
    finally:
        # Bước 3: Dọn dẹp Dữ liệu vĩnh viễn (Rollback cứng)
        await teardown_mock_unit()
        print("================== KẾT THÚC ==================")

if __name__ == "__main__":
    asyncio.run(main())
