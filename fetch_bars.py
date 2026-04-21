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
    "rum bar 蘭姆",
    "tequila bar 龍舌蘭",
    "jazz bar 爵士",
    "lounge bar",
]

# 展開成完整搜尋清單
SEARCHES = [
    {"query": f"{kw} {city['name']}", "location": city["loc"], "radius": city["r"]}
    for city in CITIES
    for kw in KEYWORDS
]

# 類型與風格推斷規則（根據名稱/關鍵字猜測）
def guess_cat(name: str, types: list) -> str:
    """
    主類型判斷（依飲品種類，8大核心 + bistro）
    優先順序：特定烈酒 > 精釀 > Speakeasy > 餐酒館 > 調酒吧
    """
    n = name.lower()
    # 威士忌（含 Highball 風格）
    if any(k in n for k in ["whisky", "whiskey", "bourbon", "scotch", "威士忌", "highball", "ハイボール"]):
        return "whisky"
    # 清酒
    if any(k in n for k in ["sake", "清酒", "日本酒", "izakaya", "居酒屋"]):
        return "sake"
    # 葡萄酒
    if any(k in n for k in ["wine", "葡萄酒", "紅酒", "白酒", "champagne", "prosecco", "bubbles"]):
        return "wine"
    # 琴酒
    if any(k in n for k in ["gin", "琴酒", "genever", "juniper"]):
        return "gin"
    # 蘭姆 / 龍舌蘭
    if any(k in n for k in ["rum", "rhum", "ron", "蘭姆", "tequila", "mezcal", "agave", "龍舌蘭", "sotol"]):
        return "rum_agave"
    # 精釀啤酒（craft 優先於一般 beer）
    if any(k in n for k in ["craft", "brew", "精釀", "taproom"]):
        return "craft"
    # 一般啤酒吧（pub style）
    if any(k in n for k in ["beer", "pub", "啤酒", "pint", "ale", "lager", "stout"]) \
            and not any(k in n for k in ["cocktail", "調酒", "bar"]):
        return "craft"
    # Speakeasy
    if any(k in n for k in ["speakeasy", "hidden", "secret", "basement", "underground"]):
        return "speakeasy"
    # 餐酒館
    if any(k in n for k in ["bistro", "餐酒館", "brasserie", "tavern", "gastropub"]):
        return "bistro"
    return "cocktail"  # 預設


def guess_vibes(name: str, types: list, address: str = "") -> list:
    """
    氛圍 / 體驗標籤（多選，存入 tags 欄位）
    涵蓋：音樂型、社交型、環境型、概念型
    """
    n = name.lower()
    vibes = []

    # ── 音樂 & 表演 ──
    if any(k in n for k in ["jazz", "爵士"]):
        vibes.append("jazz")
    if any(k in n for k in ["dj", "club", "電音", "electronic", "rave", "techno", "house"]):
        vibes.append("dj")
    if any(k in n for k in ["live", "band", "concert", "vinyl", "record", "黑膠", "現場", "hifi", "hi-fi"]):
        vibes.append("listen")

    # ── 環境 & 空間 ──
    if any(k in n for k in ["rooftop", "sky", "roof", "頂樓", "空中", "terrasse", "terrace", "天台"]):
        vibes.append("rooftop")
    if any(k in n for k in ["hotel", "grand", "palace", "resort", "飯店", "酒店", "旅館", "inn"]) \
            or "lodging" in types:
        vibes.append("hotel")
    if any(k in n for k in ["lounge", "沙發", "relax", "chill", "comfort"]):
        vibes.append("lounge")
    if any(k in n for k in ["dive", "老", "old school", "classic pub", "traditional", "老派"]):
        vibes.append("dive")
    if any(k in n for k in ["theme", "主題", "昭和", "showa", "retro", "復古", "film", "電影", "anime"]):
        vibes.append("theme")
    if any(k in n for k in ["speakeasy", "hidden", "secret", "basement", "underground", "隱藏", "地下"]):
        vibes.append("hidden")

    # ── 社交行為 ──
    if any(k in n for k in ["date", "romantic", "couple", "約會", "candlelight"]):
        vibes.append("date")
    if any(k in n for k in ["party", "派對", "celebration", "fiesta", "banquet"]):
        vibes.append("party")
    if any(k in n for k in ["solo", "bar seat", "counter", "吧台", "一人"]):
        vibes.append("solo")
    if any(k in n for k in ["afterwork", "after work", "下班", "happy hour"]):
        vibes.append("afterwork")

    # ── 概念 & 體驗 ──
    if any(k in n for k in ["experimental", "lab", "molecular", "實驗", "avant"]):
        vibes.append("experimental")
    if any(k in n for k in ["tasting", "omakase", "品飲", "flight", "pairing"]):
        vibes.append("tasting")
    if any(k in n for k in ["zero", "無酒精", "sober", "mocktail", "alcohol-free", "0%"]):
        vibes.append("zero_abv")
    if any(k in n for k in ["low abv", "低酒精", "spritz", "low alcohol"]):
        vibes.append("low_abv")
    if any(k in n for k in ["sustainable", "local", "organic", "farm", "永續", "在地", "natural"]):
        vibes.append("sustainable")
    if any(k in n for k in ["chef", "kitchen", "dining", "food", "餐廚", "料理"]) \
            and any(k in n for k in ["bar", "吧", "cocktail"]):
        vibes.append("chefs_table")
    if any(k in n for k in ["private", "reservation only", "預約", "私人", "member", "會員"]):
        vibes.append("private")

    return list(dict.fromkeys(vibes))  # 去重，保留順序

def guess_style(name: str) -> str:
    """
    保留 style 欄位做向下相容，取 vibes[0] 或預設 craft
    """
    vibes = guess_vibes(name, [])
    if vibes:
        return vibes[0]
    n = name.lower()
    if any(k in n for k in ["rooftop", "sky", "top", "頂樓"]):
        return "rooftop"
    if any(k in n for k in ["experimental", "lab", "molecular", "實驗"]):
        return "experimental"
    if any(k in n for k in ["hotel", "grand", "palace", "飯店"]):
        return "hotel"
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
            place_types = details.get("types", [])
            cat = guess_cat(name, place_types)
            vibes = guess_vibes(name, place_types, address)
            style = vibes[0] if vibes else guess_style(name)
            nightly_score = google_score_to_nightly(rating, review_count)
            # 新版 opening_hours 格式相容處理
            open_hours = format_open_hours(opening_hours)

            # 價格標示
            price_map = {1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}
            price_str = price_map.get(price_level, "$$")

            # 類別中英文
            cat_labels = {
                "cocktail":  ("調酒吧",     "Cocktail Bar"),
                "speakeasy": ("Speakeasy",   "Speakeasy"),
                "gin":       ("琴酒吧",      "Gin Bar"),
                "whisky":    ("威士忌吧",    "Whisky Bar"),
                "rum_agave": ("蘭姆/龍舌蘭", "Rum & Agave"),
                "wine":      ("紅酒吧",      "Wine Bar"),
                "craft":     ("精釀啤酒吧",  "Craft Beer Bar"),
                "sake":      ("清酒吧",      "Sake Bar"),
                "bistro":    ("餐酒館",      "Bistro Bar"),
            }
            vibe_labels = {
                "rooftop":     ("頂樓景觀",   "Rooftop"),
                "jazz":        ("爵士現場",   "Jazz Bar"),
                "dj":          ("DJ 電音",    "DJ / Club"),
                "listen":      ("音樂鑑賞",   "Listen Bar"),
                "lounge":      ("沙發放鬆",   "Lounge"),
                "dive":        ("Dive Bar",   "Dive Bar"),
                "theme":       ("主題酒吧",   "Theme Bar"),
                "hotel":       ("飯店酒吧",   "Hotel Bar"),
                "hidden":      ("隱藏私密",   "Hidden"),
                "date":        ("約會導向",   "Date Bar"),
                "party":       ("派對熱鬧",   "Party Bar"),
                "solo":        ("一人友善",   "Solo-friendly"),
                "afterwork":   ("下班小酌",   "Afterwork"),
                "experimental":("實驗調酒",   "Experimental"),
                "tasting":     ("品飲體驗",   "Tasting Room"),
                "zero_abv":    ("無酒精",     "Zero ABV"),
                "low_abv":     ("低酒精",     "Low ABV"),
                "sustainable": ("永續在地",   "Sustainable"),
                "chefs_table": ("餐酒融合",   "Chef's Table"),
                "private":     ("預約私人",   "Private Bar"),
            }
            style_labels = vibe_labels  # 向下相容

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
                "style_zh": vibe_labels.get(style, ("調酒吧","Cocktail Bar"))[0],
                "style_en": vibe_labels.get(style, ("調酒吧","Cocktail Bar"))[1],
                "vibes": vibes,
                "img": f"v{(bar_id % 4) + 1}",
                "tags": vibes,
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
