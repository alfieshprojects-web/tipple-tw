"""
NIGHTLY — 酒吧資料爬蟲腳本
=====================================
用途：從 Google Places API 抓取台灣酒吧資料，輸出 bars.json

執行前準備：
  1. 安裝依賴：pip install requests
  2. 在下方填入你的 Google Places API Key
  3. 執行：python fetch_bars.py

取得 Google Places API Key 步驟：
  1. 前往 https://console.cloud.google.com/
  2. 建立新專案（或選現有專案）
  3. 搜尋並啟用「Places API (New)」
  4. 前往「憑證」→「建立憑證」→「API 金鑰」
  5. 複製 API Key，貼到下方 GOOGLE_API_KEY

費用提醒：
  - 每月有 $200 免費額度（約可查詢 5,000 次 Nearby Search）
  - 這支腳本一次跑完約 50 間酒吧，費用遠低於免費額度
"""

import requests
import json
import time
import os
from datetime import datetime

# ============================================================
# ★ 在這裡填入你的 API Key ★
GOOGLE_API_KEY = "YOUR_GOOGLE_PLACES_API_KEY_HERE"
# ============================================================

OUTPUT_FILE = "bars.json"

# 搜尋關鍵字與範圍（以台北市中心為圓心，半徑 8 公里）
SEARCHES = [
    {"query": "cocktail bar taipei",         "location": "25.0478,121.5319", "radius": 8000},
    {"query": "whisky bar taipei",           "location": "25.0478,121.5319", "radius": 8000},
    {"query": "sake bar taipei",             "location": "25.0478,121.5319", "radius": 8000},
    {"query": "wine bar taipei",             "location": "25.0478,121.5319", "radius": 8000},
    {"query": "speakeasy bar taipei",        "location": "25.0478,121.5319", "radius": 8000},
    {"query": "調酒吧 台北",                  "location": "25.0478,121.5319", "radius": 8000},
    {"query": "清酒吧 台北",                  "location": "25.0478,121.5319", "radius": 8000},
    {"query": "cocktail bar taichung",       "location": "24.1477,120.6736", "radius": 6000},
    {"query": "cocktail bar tainan",         "location": "22.9999,120.2270", "radius": 6000},
    {"query": "cocktail bar kaohsiung",      "location": "22.6273,120.3014", "radius": 6000},
]

# 類型與風格推斷規則（根據名稱/關鍵字猜測）
def guess_cat(name: str, types: list) -> str:
    n = name.lower()
    if any(k in n for k in ["whisky", "whiskey", "bourbon", "scotch", "威士忌"]):
        return "whisky"
    if any(k in n for k in ["sake", "清酒", "日本酒"]):
        return "sake"
    if any(k in n for k in ["wine", "葡萄酒", "紅酒", "白酒"]):
        return "wine"
    if any(k in n for k in ["craft", "beer", "brew", "精釀"]):
        return "craft"
    if any(k in n for k in ["speakeasy", "hidden", "secret", "隱藏"]):
        return "speakeasy"
    if any(k in n for k in ["bistro", "餐酒館", "dining"]):
        return "bistro"
    return "cocktail"  # 預設

def guess_style(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["speakeasy", "hidden", "secret", "basement"]):
        return "speakeasy"
    if any(k in n for k in ["rooftop", "sky", "top", "頂樓"]):
        return "rooftop"
    if any(k in n for k in ["japanese", "japan", "jp", "日式", "和風"]):
        return "japanese"
    if any(k in n for k in ["luxe", "luxury", "hotel", "grand", "palace"]):
        return "luxe"
    if any(k in n for k in ["craft", "artisan", "handcraft", "職人"]):
        return "craft"
    if any(k in n for k in ["experimental", "lab", "molecular", "實驗"]):
        return "experimental"
    if any(k in n for k in ["classic", "heritage", "traditional", "古典"]):
        return "classic"
    return "craft"

def google_score_to_nightly(google_rating: float, review_count: int) -> float:
    """
    將 Google Maps 5 分制轉換為 NIGHTLY 10 分制，
    同時用 Bayesian 平均修正低評論數的虛高問題。
    """
    if google_rating is None:
        return 7.5
    # 轉換為 10 分
    raw = google_rating * 2
    # Bayesian 平均（prior = 7.5 分，prior strength = 50 則）
    prior_mean, prior_n = 7.5, 50
    bayes = (prior_mean * prior_n + raw * review_count) / (prior_n + review_count)
    return round(min(10.0, max(6.0, bayes)), 1)

def district_from_address(address: str) -> dict:
    """從地址猜測行政區"""
    area_map = {
        "大安": ("Da'an", "taipei"), "信義": ("Xinyi", "taipei"),
        "中山": ("Zhongshan", "taipei"), "松山": ("Songshan", "taipei"),
        "內湖": ("Neihu", "taipei"), "南港": ("Nangang", "taipei"),
        "士林": ("Shilin", "taipei"), "北投": ("Beitou", "taipei"),
        "中正": ("Zhongzheng", "taipei"), "萬華": ("Wanhua", "taipei"),
        "文山": ("Wenshan", "taipei"), "大同": ("Datong", "taipei"),
        "台中市": ("Taichung City", "taichung"), "台南市": ("Tainan City", "tainan"),
        "高雄市": ("Kaohsiung City", "kaohsiung"),
    }
    for zh, (en, area) in area_map.items():
        if zh in address:
            return {"zh": zh, "en": en, "area": area}
    # 預設
    if "台北" in address:
        return {"zh": "台北", "en": "Taipei", "area": "taipei"}
    if "台中" in address:
        return {"zh": "台中", "en": "Taichung", "area": "taichung"}
    if "台南" in address:
        return {"zh": "台南", "en": "Tainan", "area": "tainan"}
    if "高雄" in address:
        return {"zh": "高雄", "en": "Kaohsiung", "area": "kaohsiung"}
    return {"zh": "台灣", "en": "Taiwan", "area": "taipei"}

def search_places(query: str, location: str, radius: int) -> list:
    """Google Places Text Search API"""
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "location": location,
        "radius": radius,
        "type": "bar",
        "key": GOOGLE_API_KEY,
        "language": "zh-TW",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        print(f"  ⚠ API error: {data.get('status')} — {data.get('error_message','')}")
        return []
    return data.get("results", [])

def get_place_details(place_id: str) -> dict:
    """Google Places Details API — 取得詳細資料"""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,geometry,rating,user_ratings_total,"
                  "opening_hours,price_level,website,international_phone_number,"
                  "reviews,photos,types",
        "key": GOOGLE_API_KEY,
        "language": "zh-TW",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {})

def format_open_hours(opening_hours: dict) -> list:
    """將 Google 開放時間轉換為 [[start_h, end_h], ...] 格式"""
    if not opening_hours:
        return [[18, 26]]  # 預設晚上 6 點到凌晨 2 點
    periods = opening_hours.get("periods", [])
    result = []
    for p in periods:
        o = p.get("open", {})
        c = p.get("close", {})
        if o and c:
            open_h = int(o.get("time", "1800")[:2]) + int(o.get("time", "1800")[2:]) / 60
            close_h = int(c.get("time", "0200")[:2]) + int(c.get("time", "0200")[2:]) / 60
            if close_h < open_h:
                close_h += 24  # 跨午夜
            result.append([open_h, close_h])
    return result if result else [[18, 26]]

def main():
    if GOOGLE_API_KEY == "YOUR_GOOGLE_PLACES_API_KEY_HERE":
        print("❌ 請先在腳本頂部填入 GOOGLE_API_KEY！")
        print("   取得方式：https://console.cloud.google.com/")
        return

    print("🍸 NIGHTLY 酒吧資料爬蟲")
    print(f"   輸出檔案：{OUTPUT_FILE}")
    print(f"   開始時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    seen_place_ids = set()
    bars = []
    bar_id = 1

    for search in SEARCHES:
        print(f"🔍 搜尋：{search['query']}")
        try:
            results = search_places(search["query"], search["location"], search["radius"])
        except Exception as e:
            print(f"  ❌ 搜尋失敗：{e}")
            continue

        print(f"  → 找到 {len(results)} 筆，過濾後處理...")

        for place in results:
            place_id = place.get("place_id")
            if not place_id or place_id in seen_place_ids:
                continue
            # 基本篩選：評分 >= 4.0，評論數 >= 30
            rating = place.get("rating", 0)
            review_count = place.get("user_ratings_total", 0)
            if rating < 4.0 or review_count < 30:
                continue

            seen_place_ids.add(place_id)

            # 取得詳細資料
            try:
                details = get_place_details(place_id)
                time.sleep(0.3)  # 避免超過 API rate limit
            except Exception as e:
                print(f"  ⚠ 詳細資料失敗 ({place.get('name')}): {e}")
                details = place

            name = details.get("name", place.get("name", ""))
            address = details.get("formatted_address", place.get("formatted_address", ""))
            geometry = details.get("geometry", place.get("geometry", {}))
            loc = geometry.get("location", {})
            rating = details.get("rating", rating)
            review_count = details.get("user_ratings_total", review_count)
            price_level = details.get("price_level", 2)
            opening_hours = details.get("opening_hours", {})
            website = details.get("website", "")
            phone = details.get("international_phone_number", "")

            district = district_from_address(address)
            cat = guess_cat(name, details.get("types", []))
            style = guess_style(name)
            nightly_score = google_score_to_nightly(rating, review_count)
            open_hours = format_open_hours(opening_hours)

            # 價格標示
            price_map = {1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}
            price_str = price_map.get(price_level, "$$")

            # 類別中英文
            cat_labels = {
                "cocktail": ("調酒吧", "Cocktail Bar"),
                "bistro":   ("餐酒館", "Bistro Bar"),
                "whisky":   ("威士忌吧", "Whisky Bar"),
                "sake":     ("清酒吧", "Sake Bar"),
                "wine":     ("紅酒吧", "Wine Bar"),
                "craft":    ("精釀啤酒吧", "Craft Beer Bar"),
                "speakeasy":("Speakeasy", "Speakeasy"),
            }
            style_labels = {
                "experimental": ("實驗派", "Experimental"),
                "japanese":     ("日式", "Japanese"),
                "luxe":         ("奢華", "Luxe"),
                "casual":       ("輕鬆", "Casual"),
                "rooftop":      ("頂樓", "Rooftop"),
                "classic":      ("古典", "Classic"),
                "craft":        ("職人手作", "Craft"),
                "speakeasy":    ("隱藏感", "Speakeasy"),
            }

            bar = {
                "id": bar_id,
                "name": name,
                "zh": name,  # 之後可以手動補中文名稱
                "google_place_id": place_id,
                "google_rating": rating,
                "google_review_count": review_count,
                "cat": cat,
                "style": style,
                "area": district["area"],
                "district_zh": district["zh"],
                "district_en": district["en"],
                "score": nightly_score,
                "reviews": review_count,
                "open_hours": open_hours,
                "addr_zh": address,
                "addr_en": address,
                "hours_zh": opening_hours.get("weekday_text", [""])[0] if opening_hours.get("weekday_text") else "",
                "hours_en": opening_hours.get("weekday_text", [""])[0] if opening_hours.get("weekday_text") else "",
                "price": price_level or 2,
                "price_zh": price_str,
                "price_en": price_str,
                "cat_zh": cat_labels.get(cat, ("調酒吧","Cocktail Bar"))[0],
                "cat_en": cat_labels.get(cat, ("調酒吧","Cocktail Bar"))[1],
                "style_zh": style_labels.get(style, ("職人手作","Craft"))[0],
                "style_en": style_labels.get(style, ("職人手作","Craft"))[1],
                "img": f"v{(bar_id % 4) + 1}",
                "tags": [],
                "website": website,
                "phone": phone,
                "lat": loc.get("lat", 0),
                "lng": loc.get("lng", 0),
            }
            bars.append(bar)
            bar_id += 1
            print(f"  ✓ [{bar_id-1:03d}] {name} ({district['en']}) — {rating}★ → NIGHTLY {nightly_score}")

    # 依 NIGHTLY Index 排序
    bars.sort(key=lambda b: b["score"], reverse=True)

    # 輸出 bars.json
    output = {
        "meta": {
            "version": "1.0",
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "total": len(bars),
            "sources": ["google_maps"],
            "note": "Generated by fetch_bars.py — NIGHTLY score is weighted from Google Maps rating"
        },
        "bars": bars
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！共抓取 {len(bars)} 間酒吧")
    print(f"   儲存至：{OUTPUT_FILE}")
    print("\n後續步驟：")
    print("  1. 用瀏覽器開啟 index.html（需透過 HTTP server，不能直接雙擊）")
    print("  2. 執行：python -m http.server 8080")
    print("  3. 開啟：http://localhost:8080")
    print("  4. 確認酒吧資料正確後，部署到 Netlify")

if __name__ == "__main__":
    main()
