"""
TIPPLE — 酒吧資料爬蟲腳本 v3.0 (Places API New)
=================================================
用途：從 Google Places API (New) 抓取全台灣酒吧資料，輸出 bars.json

執行前準備：
  1. 安裝依賴：pip install requests
  2. 在 Google Cloud Console 啟用「Places API (New)」
  3. 在下方填入你的 Google Places API Key
  4. 執行：python fetch_bars.py

費用提醒：
  - 每月有 $200 免費額度
  - 此腳本一次約消耗 $5–15，遠低於免費上限
"""

import requests
import json
import time
import os
from datetime import datetime

# ============================================================
# ★ 在這裡填入你的 API Key ★
GOOGLE_API_KEY = "AIzaSyCpm-WmlRkoytWw7NLanyjWBZ82U-aUqqI"
# ============================================================

OUTPUT_FILE = "bars.json"

# ── 全台灣搜尋定點 ────────────────────────────────────────────
# 每個城市用多個關鍵字搜尋，並搭配分頁抓滿 60 筆/查詢

CITIES = [
    # 台北市各區
    {"name": "台北大安",       "loc": "25.0330,121.5490", "r": 4000},
    {"name": "台北信義",       "loc": "25.0400,121.5650", "r": 4000},
    {"name": "台北中山",       "loc": "25.0560,121.5250", "r": 4000},
    {"name": "台北松山",       "loc": "25.0560,121.5550", "r": 3500},
    {"name": "台北中正",       "loc": "25.0415,121.5100", "r": 3500},
    {"name": "台北士林",       "loc": "25.0930,121.5240", "r": 4000},
    {"name": "台北內湖",       "loc": "25.0650,121.5850", "r": 4000},
    {"name": "台北萬華",       "loc": "25.0310,121.4990", "r": 3500},
    {"name": "台北大同",       "loc": "25.0630,121.5120", "r": 3500},
    {"name": "台北文山",       "loc": "24.9980,121.5680", "r": 4000},
    # 新北市
    {"name": "新北板橋",       "loc": "25.0000,121.4600", "r": 4000},
    {"name": "新北新店",       "loc": "24.9670,121.5380", "r": 4000},
    {"name": "新北淡水",       "loc": "25.1700,121.4500", "r": 4000},
    {"name": "新北三重",       "loc": "25.0610,121.4870", "r": 3500},
    {"name": "新北中和",       "loc": "24.9980,121.4850", "r": 3500},
    {"name": "新北永和",       "loc": "25.0130,121.5140", "r": 3000},
    {"name": "新北新莊",       "loc": "25.0360,121.4490", "r": 4000},
    # 桃園
    {"name": "桃園市區",       "loc": "24.9936,121.3010", "r": 6000},
    {"name": "桃園中壢",       "loc": "24.9640,121.2250", "r": 5000},
    # 新竹
    {"name": "新竹市",         "loc": "24.8138,120.9675", "r": 5000},
    # 苗栗
    {"name": "苗栗市",         "loc": "24.5600,120.8200", "r": 5000},
    # 台中
    {"name": "台中西區",       "loc": "24.1600,120.6700", "r": 5000},
    {"name": "台中南屯",       "loc": "24.1400,120.6300", "r": 5000},
    {"name": "台中北屯",       "loc": "24.1900,120.7000", "r": 5000},
    {"name": "台中東區",       "loc": "24.1460,120.6980", "r": 4000},
    # 南投
    {"name": "南投市",         "loc": "23.9100,120.6800", "r": 5000},
    # 彰化
    {"name": "彰化市",         "loc": "24.0800,120.5400", "r": 5000},
    # 雲林
    {"name": "雲林斗六",       "loc": "23.7100,120.5400", "r": 5000},
    # 嘉義
    {"name": "嘉義市",         "loc": "23.4800,120.4490", "r": 5000},
    # 台南
    {"name": "台南中西區",     "loc": "22.9930,120.2040", "r": 5000},
    {"name": "台南安平",       "loc": "22.9900,120.1700", "r": 5000},
    {"name": "台南東區",       "loc": "22.9900,120.2300", "r": 4000},
    {"name": "台南永康",       "loc": "23.0300,120.2600", "r": 4000},
    # 高雄
    {"name": "高雄三民",       "loc": "22.6270,120.3100", "r": 5000},
    {"name": "高雄前金",       "loc": "22.6350,120.2900", "r": 4000},
    {"name": "高雄左營",       "loc": "22.6900,120.3000", "r": 5000},
    {"name": "高雄苓雅",       "loc": "22.6190,120.3120", "r": 4000},
    {"name": "高雄鹽埕",       "loc": "22.6250,120.2870", "r": 3500},
    {"name": "高雄新興",       "loc": "22.6310,120.3010", "r": 3500},
    # 屏東
    {"name": "屏東市",         "loc": "22.6700,120.4900", "r": 5000},
    # 宜蘭
    {"name": "宜蘭市",         "loc": "24.7500,121.7500", "r": 5000},
    {"name": "宜蘭羅東",       "loc": "24.6770,121.7680", "r": 4000},
    # 花蓮
    {"name": "花蓮市",         "loc": "23.9800,121.6000", "r": 5000},
    # 台東
    {"name": "台東市",         "loc": "22.7583,121.1444", "r": 5000},
]

KEYWORDS = [
    "cocktail bar",
    "調酒吧",
    "whisky bar 威士忌",
    "sake bar 清酒",
    "wine bar 葡萄酒",
    "speakeasy bar",
    "craft beer bar 精釀",
    "餐酒館 bistro bar",
    "gin bar 琴酒",
    "highball bar",
    "beer bar 啤酒吧",
]

# 展開成完整搜尋清單
SEARCHES = [
    {"query": f"{kw} {city['name']}", "location": city["loc"], "radius": city["r"]}
    for city in CITIES
    for kw in KEYWORDS
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
    if any(k in n for k in ["gin", "琴酒", "juniper"]):
        return "gin"
    if any(k in n for k in ["highball", "ハイボール", "high ball"]):
        return "highball"
    if any(k in n for k in ["craft", "brew", "精釀"]):
        return "craft"
    if any(k in n for k in ["beer", "pub", "啤酒", "酒館"]) and not any(k in n for k in ["cocktail", "調酒"]):
        return "beer"
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
    Google Maps 5 分制 × 2 = TIPPLE 10 分制
    直接對應，透明易懂。
    """
    if google_rating is None:
        return 0.0
    return round(google_rating * 2, 1)

def district_from_address(address: str) -> dict:
    """從地址猜測行政區"""
    area_map = {
        # 台北市
        "大安": ("Da'an", "taipei"), "信義": ("Xinyi", "taipei"),
        "中山": ("Zhongshan", "taipei"), "松山": ("Songshan", "taipei"),
        "內湖": ("Neihu", "taipei"), "南港": ("Nangang", "taipei"),
        "士林": ("Shilin", "taipei"), "北投": ("Beitou", "taipei"),
        "中正": ("Zhongzheng", "taipei"), "萬華": ("Wanhua", "taipei"),
        "文山": ("Wenshan", "taipei"), "大同": ("Datong", "taipei"),
        # 新北市
        "板橋": ("Banqiao", "newtaipei"), "新店": ("Xindian", "newtaipei"),
        "中和": ("Zhonghe", "newtaipei"), "永和": ("Yonghe", "newtaipei"),
        "三重": ("Sanchong", "newtaipei"), "新莊": ("Xinzhuang", "newtaipei"),
        "淡水": ("Tamsui", "newtaipei"), "汐止": ("Xizhi", "newtaipei"),
        # 桃園市
        "桃園": ("Taoyuan", "taoyuan"), "中壢": ("Zhongli", "taoyuan"),
        # 新竹
        "新竹": ("Hsinchu", "hsinchu"),
        # 台中市
        "西區": ("West Dist.", "taichung"), "北區": ("North Dist.", "taichung"),
        "南屯": ("Nantun", "taichung"), "西屯": ("Xitun", "taichung"),
        "北屯": ("Beitun", "taichung"), "豐原": ("Fengyuan", "taichung"),
        "台中市": ("Taichung", "taichung"),
        # 彰化
        "彰化": ("Changhua", "changhua"),
        # 嘉義
        "嘉義": ("Chiayi", "chiayi"),
        # 台南市
        "中西區": ("West Central", "tainan"), "東區": ("East Dist.", "tainan"),
        "安平": ("Anping", "tainan"), "永康": ("Yongkang", "tainan"),
        "台南市": ("Tainan", "tainan"),
        # 高雄市
        "三民": ("Sanmin", "kaohsiung"), "苓雅": ("Lingya", "kaohsiung"),
        "前金": ("Qianjin", "kaohsiung"), "新興": ("Xinxing", "kaohsiung"),
        "左營": ("Zuoying", "kaohsiung"), "楠梓": ("Nanzih", "kaohsiung"),
        "鹽埕": ("Yancheng", "kaohsiung"), "前鎮": ("Qianzhen", "kaohsiung"),
        "高雄市": ("Kaohsiung", "kaohsiung"),
        # 屏東
        "屏東": ("Pingtung", "pingtung"),
        # 宜蘭
        "宜蘭": ("Yilan", "yilan"),
        # 花蓮
        "花蓮": ("Hualien", "hualien"),
        # 台東
        "台東": ("Taitung", "taitung"),
    }
    for zh, (en, area) in area_map.items():
        if zh in address:
            return {"zh": zh, "en": en, "area": area}
    # 預設
    if "台北" in address:
        return {"zh": "台北", "en": "Taipei", "area": "taipei"}
    if "新北" in address:
        return {"zh": "新北", "en": "New Taipei", "area": "newtaipei"}
    if "桃園" in address:
        return {"zh": "桃園", "en": "Taoyuan", "area": "taoyuan"}
    if "新竹" in address:
        return {"zh": "新竹", "en": "Hsinchu", "area": "hsinchu"}
    if "台中" in address:
        return {"zh": "台中", "en": "Taichung", "area": "taichung"}
    if "彰化" in address:
        return {"zh": "彰化", "en": "Changhua", "area": "changhua"}
    if "嘉義" in address:
        return {"zh": "嘉義", "en": "Chiayi", "area": "chiayi"}
    if "台南" in address:
        return {"zh": "台南", "en": "Tainan", "area": "tainan"}
    if "高雄" in address:
        return {"zh": "高雄", "en": "Kaohsiung", "area": "kaohsiung"}
    if "屏東" in address:
        return {"zh": "屏東", "en": "Pingtung", "area": "pingtung"}
    if "宜蘭" in address:
        return {"zh": "宜蘭", "en": "Yilan", "area": "yilan"}
    if "花蓮" in address:
        return {"zh": "花蓮", "en": "Hualien", "area": "hualien"}
    if "台東" in address:
        return {"zh": "台東", "en": "Taitung", "area": "taitung"}
    return {"zh": "台灣", "en": "Taiwan", "area": "taipei"}

def search_places(query: str, location: str, radius: int) -> list:
    """
    Places API (New) Text Search — POST 請求，含分頁，最多抓 3 頁（60 筆）
    回傳格式：每筆包含 id, displayName, rating, userRatingCount, formattedAddress, location
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.rating,"
            "places.userRatingCount,places.formattedAddress,places.location,"
            "places.types,nextPageToken"
        ),
        "Content-Type": "application/json",
    }
    lat, lng = location.split(",")
    body = {
        "textQuery": query,
        "maxResultCount": 20,
        "languageCode": "zh-TW",
        "locationBias": {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": float(radius),
            }
        },
    }
    all_results = []
    for page in range(3):  # 最多翻 3 頁（60 筆）
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        places = data.get("places", [])
        if not places:
            break
        all_results.extend(places)
        next_token = data.get("nextPageToken")
        if not next_token:
            break
        time.sleep(2)  # 新版 API 也需要等待
        body["pageToken"] = next_token
    return all_results


def get_place_details(place_id: str) -> dict:
    """
    Places API (New) Place Details — 取得詳細資料 + 最多 10 張照片
    """
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "id,displayName,formattedAddress,location,rating,userRatingCount,"
            "regularOpeningHours,priceLevel,websiteUri,internationalPhoneNumber,"
            "photos,types"
        ),
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def format_open_hours(opening_hours: dict) -> list:
    """
    將 Google 開放時間轉換為 [[start_h, end_h], ...] 格式
    相容新版 API（regularOpeningHours）與舊版 API（opening_hours）
    """
    if not opening_hours:
        return [[18, 26]]  # 預設晚上 6 點到凌晨 2 點
    periods = opening_hours.get("periods", [])
    result = []
    for p in periods:
        o = p.get("open", {})
        c = p.get("close", {})
        if o and c:
            # 新版 API：{"hour": 18, "minute": 0}；舊版：{"time": "1800"}
            if "hour" in o:
                open_h = o.get("hour", 18) + o.get("minute", 0) / 60
                close_h = c.get("hour", 2) + c.get("minute", 0) / 60
            else:
                t_open = o.get("time", "1800")
                t_close = c.get("time", "0200")
                open_h = int(t_open[:2]) + int(t_open[2:]) / 60
                close_h = int(t_close[:2]) + int(t_close[2:]) / 60
            if close_h < open_h:
                close_h += 24  # 跨午夜
            result.append([open_h, close_h])
    return result if result else [[18, 26]]

def main():
    if GOOGLE_API_KEY == "YOUR_GOOGLE_PLACES_API_KEY_HERE":
        print("❌ 請先在腳本頂部填入 GOOGLE_API_KEY！")
        print("   取得方式：https://console.cloud.google.com/")
        return

    print("🍸 TIPPLE 酒吧資料爬蟲 v2.0")
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
            # Places API (New) 使用 "id" 而不是 "place_id"
            place_id = place.get("id")
            if not place_id or place_id in seen_place_ids:
                continue
            # 基本篩選：評分 >= 3.8，評論數 >= 20（放寬以涵蓋二三線城市酒吧）
            rating = place.get("rating", 0)
            review_count = place.get("userRatingCount", 0)
            if rating < 3.8 or review_count < 20:
                continue

            seen_place_ids.add(place_id)

            # 取得詳細資料
            place_name = place.get("displayName", {}).get("text", "")
            try:
                details = get_place_details(place_id)
                time.sleep(0.3)
            except Exception as e:
                print(f"  ⚠ 詳細資料失敗 ({place_name}): {e}")
                details = place

            # 新版 API 欄位名稱
            name = details.get("displayName", {}).get("text", place_name)
            address = details.get("formattedAddress", place.get("formattedAddress", ""))
            loc_obj = details.get("location", place.get("location", {}))
            rating = details.get("rating", rating)
            review_count = details.get("userRatingCount", review_count)
            # priceLevel: "PRICE_LEVEL_INEXPENSIVE"=1, "MODERATE"=2, "EXPENSIVE"=3, "VERY_EXPENSIVE"=4
            price_raw = details.get("priceLevel", "PRICE_LEVEL_MODERATE")
            price_level_map = {
                "PRICE_LEVEL_FREE": 1, "PRICE_LEVEL_INEXPENSIVE": 1,
                "PRICE_LEVEL_MODERATE": 2, "PRICE_LEVEL_EXPENSIVE": 3,
                "PRICE_LEVEL_VERY_EXPENSIVE": 4,
            }
            price_level = price_level_map.get(price_raw, 2) if isinstance(price_raw, str) else (price_raw or 2)
            opening_hours = details.get("regularOpeningHours", {})
            website = details.get("websiteUri", "")
            phone = details.get("internationalPhoneNumber", "")
            # 新版照片：name = "places/ChIJ.../photos/AXCi..."
            photos = details.get("photos", [])
            photo_refs = [p["name"] for p in photos[:10] if p.get("name")]

            district = district_from_address(address)
            cat = guess_cat(name, details.get("types", []))
            style = guess_style(name)
            nightly_score = google_score_to_nightly(rating, review_count)
            # 新版 opening_hours 格式相容處理
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
                "gin":      ("琴酒吧", "Gin Bar"),
                "highball": ("Highball Bar", "Highball Bar"),
                "beer":     ("啤酒吧", "Beer Bar"),
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
                # 新版 API 用 weekdayDescriptions，舊版用 weekday_text
                "hours_zh": (opening_hours.get("weekdayDescriptions") or opening_hours.get("weekday_text") or [""])[0],
                "hours_en": (opening_hours.get("weekdayDescriptions") or opening_hours.get("weekday_text") or [""])[0],
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
                "photo_refs": photo_refs,
                "lat": loc_obj.get("latitude", loc_obj.get("lat", 0)),
                "lng": loc_obj.get("longitude", loc_obj.get("lng", 0)),
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
