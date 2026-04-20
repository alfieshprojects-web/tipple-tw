"""
TIPPLE — 補抓照片 reference 腳本
=====================================
用途：為現有 bars.json 中每間酒吧補抓 Google Photos reference
執行：python3 fetch_photos.py
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

def get_photos(place_id: str) -> list:
    """只抓 photos 欄位，節省 API 費用"""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "photos",
        "key": GOOGLE_API_KEY,
        "language": "zh-TW",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        result = resp.json().get("result", {})
        photos = result.get("photos", [])
        return [p["photo_reference"] for p in photos[:3] if p.get("photo_reference")]
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

    print(f"🍸 TIPPLE 照片補抓腳本")
    print(f"   共 {total} 間酒吧，開始補抓照片...\n")

    for i, bar in enumerate(bars):
        place_id = bar.get("google_place_id", "")

        # 跳過已有照片或沒有 place_id 的
        if bar.get("photo_refs") or not place_id or "placeholder" in place_id:
            skipped += 1
            continue

        refs = get_photos(place_id)
        bar["photo_refs"] = refs

        if refs:
            updated += 1
            print(f"  ✓ [{i+1:04d}/{total}] {bar['name']} — {len(refs)} 張照片")
        else:
            print(f"  · [{i+1:04d}/{total}] {bar['name']} — 無照片")

        # 每 10 筆存一次，避免中途失敗全部遺失
        if (i + 1) % 10 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        time.sleep(0.2)  # 避免超過 rate limit

    # 最後存檔
    data["meta"]["updated"] = datetime.now().strftime("%Y-%m-%d")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！更新 {updated} 間，跳過 {skipped} 間（已有照片或無 place_id）")
    print(f"   儲存至：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
