"""
TIPPLE — 補抓照片腳本 v2.0 (Places API New)
=============================================
用途：為現有 bars.json 中每間酒吧補抓 Google Photos（新版 API，最多 10 張）
執行：python3 fetch_photos.py

改用 Places API (New) 的好處：
  - 照片選取演算法更新，環境照/酒飲照比例更高
  - 支援最多 10 張
  - 更高解析度（maxWidthPx 可達 4800px）

需要在 Google Cloud Console 啟用：「Places API (New)」
"""

import requests
import json
import time
from datetime import datetime

# ============================================================
# ★ 填入你的 Google Places API Key ★
GOOGLE_API_KEY = "AIzaSyCpm-WmlRkoytWw7NLanyjWBZ82U-aUqqI"
# ============================================================

INPUT_FILE  = "bars.json"
OUTPUT_FILE = "bars.json"
MAX_PHOTOS  = 10  # Places API (New) 最多回傳 10 張


def get_photos_new(place_id: str) -> list:
    """
    Places API (New) — 取得照片 name 清單
    回傳格式：["places/ChIJ.../photos/AXCi...", ...]
    對應 photoUrl() 中的新版 URL：
      https://places.googleapis.com/v1/{name}/media?maxWidthPx=1200&key=KEY
    """
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "photos",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        photos = data.get("photos", [])
        return [p["name"] for p in photos[:MAX_PHOTOS] if p.get("name")]
    except Exception as e:
        print(f"  ⚠ 失敗：{e}")
        return []


def main():
    if GOOGLE_API_KEY == "YOUR_GOOGLE_PLACES_API_KEY_HERE":
        print("❌ 請先填入 GOOGLE_API_KEY！")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    bars = data["bars"]
    total = len(bars)
    updated = 0
    skipped = 0
    failed = 0

    print(f"🍸 TIPPLE 照片補抓腳本 v2.0 (Places API New)")
    print(f"   共 {total} 間酒吧，每間最多抓 {MAX_PHOTOS} 張，開始補抓...\n")

    for i, bar in enumerate(bars):
        place_id = bar.get("google_place_id", "")

        # 跳過沒有合法 place_id 的
        if not place_id or "placeholder" in place_id:
            skipped += 1
            continue

        # 強制更新：即使已有舊版 photo_refs 也重新抓（換成新格式）
        refs = get_photos_new(place_id)
        bar["photo_refs"] = refs

        if refs:
            updated += 1
            print(f"  ✓ [{i+1:04d}/{total}] {bar['name']} — {len(refs)} 張")
        else:
            failed += 1
            print(f"  · [{i+1:04d}/{total}] {bar['name']} — 無照片")

        # 每 10 筆存一次，避免中途失敗全部遺失
        if (i + 1) % 10 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  💾 進度儲存（{i+1}/{total}）")

        time.sleep(0.15)  # 約 6-7 req/sec，安全範圍內

    # 最後存檔
    data["meta"]["updated"] = datetime.now().strftime("%Y-%m-%d")
    data["meta"]["photos_api"] = "places_new_v1"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！")
    print(f"   更新：{updated} 間")
    print(f"   無照片：{failed} 間")
    print(f"   跳過（無 place_id）：{skipped} 間")
    print(f"   儲存至：{OUTPUT_FILE}")
    print(f"\n下一步：git add bars.json && git commit -m 'data: refresh photos (Places API New, up to 10)' && git push")


if __name__ == "__main__":
    main()
