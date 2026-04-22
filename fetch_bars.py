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

OUTPUT_FILE    = "bars.json"
EXISTING_FILE  = "bars.json"   # 合併用：保留既有評論 / 照片

# 篩選門檻
MIN_RATING      = 4.0
MIN_REVIEWS     = 100

# 排除關鍵字（名稱含這些字就跳過）
EXCLUDE_KEYWORDS = [
    # 居酒屋類
    "居酒屋", "izakaya", "いざかや", "焼き鳥", "yakitori",
    # 餐廳類
    "餐酒館", "bistro", "夜市", "night market", "觀光夜市", "小吃",
    # 零售 / 電商
    "買酒網", "酒條通", "酒訊", "宅配", "網購", "線上購買", "酒外送",
    "威士忌專賣", "威士忌販賣", "洋酒販賣",
    "清酒販賣", "日本酒販賣",
    "葡萄酒販賣", "紅酒販賣", "白酒販賣",
    # 無內用座位
    "外帶專賣", "純外帶", "外帶不內用", "外送服務",
]

# 目標城市（台北為主、新北為輔）
TARGET_AREAS = {'taipei', 'newtaipei'}

# ── 台北市 + 新北市 搜尋定點（高密度網格）────────────────────
CITIES = [
    # ════════════════════════════════════════════════════════
    #  台北市
    # ════════════════════════════════════════════════════════

    # ── 大安區（10 個點，r=900）── 酒吧密度最高
    {"name": "大安_仁愛大安路",    "loc": "25.0430,121.5300", "r": 900},
    {"name": "大安_忠孝復興",      "loc": "25.0415,121.5440", "r": 900},
    {"name": "大安_忠孝基隆",      "loc": "25.0415,121.5530", "r": 900},
    {"name": "大安_永康街",        "loc": "25.0315,121.5295", "r": 900},
    {"name": "大安_師大夜市",      "loc": "25.0265,121.5260", "r": 900},
    {"name": "大安_和平東路",      "loc": "25.0265,121.5400", "r": 900},
    {"name": "大安_敦化南仁愛",    "loc": "25.0380,121.5370", "r": 900},
    {"name": "大安_科技大樓",      "loc": "25.0290,121.5490", "r": 900},
    {"name": "大安_忠孝敦化北",    "loc": "25.0490,121.5380", "r": 900},
    {"name": "大安_公館羅斯福",    "loc": "25.0195,121.5340", "r": 900},

    # ── 中山區（8 個點，r=900）──
    {"name": "中山_林森北路",      "loc": "25.0555,121.5275", "r": 900},
    {"name": "中山_中山北路2段",   "loc": "25.0610,121.5200", "r": 900},
    {"name": "中山_南京東路1段",   "loc": "25.0520,121.5315", "r": 900},
    {"name": "中山_赤峰街",        "loc": "25.0575,121.5215", "r": 800},
    {"name": "中山_民權西路",      "loc": "25.0640,121.5175", "r": 900},
    {"name": "中山_長春路",        "loc": "25.0500,121.5250", "r": 900},
    {"name": "中山_中山北路3段",   "loc": "25.0690,121.5230", "r": 900},
    {"name": "中山_市民大道",      "loc": "25.0455,121.5340", "r": 900},

    # ── 信義區（8 個點，r=900）──
    {"name": "信義_松壽路",        "loc": "25.0360,121.5655", "r": 900},
    {"name": "信義_市政府",        "loc": "25.0420,121.5655", "r": 900},
    {"name": "信義_吳興街",        "loc": "25.0280,121.5630", "r": 900},
    {"name": "信義_基隆路",        "loc": "25.0490,121.5625", "r": 900},
    {"name": "信義_永吉路",        "loc": "25.0430,121.5585", "r": 900},
    {"name": "信義_松山路",        "loc": "25.0500,121.5740", "r": 900},
    {"name": "信義_象山",          "loc": "25.0310,121.5760", "r": 1000},
    {"name": "信義_忠孝東路5段",   "loc": "25.0395,121.5750", "r": 900},

    # ── 松山區（6 個點，r=1000）──
    {"name": "松山_饒河街",        "loc": "25.0500,121.5660", "r": 1000},
    {"name": "松山_民生社區",      "loc": "25.0600,121.5510", "r": 1000},
    {"name": "松山_南京東路5段",   "loc": "25.0480,121.5770", "r": 1000},
    {"name": "松山_八德路",        "loc": "25.0420,121.5720", "r": 1000},
    {"name": "松山_塔悠路",        "loc": "25.0545,121.5620", "r": 900},
    {"name": "松山_民生東路5段",   "loc": "25.0640,121.5620", "r": 1000},

    # ── 萬華區（6 個點，r=900）──
    {"name": "萬華_西門町",        "loc": "25.0430,121.5080", "r": 900},
    {"name": "萬華_龍山寺",        "loc": "25.0360,121.5005", "r": 900},
    {"name": "萬華_萬大路",        "loc": "25.0265,121.5025", "r": 900},
    {"name": "萬華_三水街",        "loc": "25.0310,121.5050", "r": 800},
    {"name": "萬華_漢中街",        "loc": "25.0470,121.5010", "r": 900},
    {"name": "萬華_環河南路",      "loc": "25.0315,121.4940", "r": 900},

    # ── 中正區（6 個點，r=1000）──
    {"name": "中正_師大商圈",      "loc": "25.0270,121.5265", "r": 1000},
    {"name": "中正_台大公館",      "loc": "25.0195,121.5340", "r": 1000},
    {"name": "中正_忠孝西路",      "loc": "25.0450,121.5115", "r": 1000},
    {"name": "中正_牯嶺街",        "loc": "25.0380,121.5180", "r": 900},
    {"name": "中正_金華街",        "loc": "25.0350,121.5280", "r": 900},
    {"name": "中正_南昌路",        "loc": "25.0300,121.5180", "r": 900},

    # ── 大同區（5 個點，r=800）──
    {"name": "大同_迪化街",        "loc": "25.0620,121.5105", "r": 800},
    {"name": "大同_南京西路",      "loc": "25.0530,121.5160", "r": 800},
    {"name": "大同_寧夏",          "loc": "25.0575,121.5130", "r": 800},
    {"name": "大同_大橋頭",        "loc": "25.0660,121.5130", "r": 800},
    {"name": "大同_重慶北路",      "loc": "25.0500,121.5190", "r": 800},

    # ── 士林區（5 個點，r=1800）──
    {"name": "士林_天母",          "loc": "25.1010,121.5240", "r": 1800},
    {"name": "士林_士林夜市",      "loc": "25.0940,121.5240", "r": 1500},
    {"name": "士林_芝山德行",      "loc": "25.0815,121.5325", "r": 1500},
    {"name": "士林_石牌",          "loc": "25.1150,121.5095", "r": 1800},
    {"name": "士林_天母北",        "loc": "25.1290,121.5020", "r": 2000},

    # ── 北投區（3 個點，r=2000）──
    {"name": "北投_溫泉區",        "loc": "25.1360,121.5020", "r": 2000},
    {"name": "北投_新北投",        "loc": "25.1510,121.4960", "r": 2000},
    {"name": "北投_石牌南",        "loc": "25.1130,121.4980", "r": 2000},

    # ── 內湖區（4 個點，r=1800）──
    {"name": "內湖_內湖路",        "loc": "25.0700,121.5880", "r": 1800},
    {"name": "內湖_文德",          "loc": "25.0600,121.5750", "r": 1800},
    {"name": "內湖_金湖",          "loc": "25.0800,121.5880", "r": 1800},
    {"name": "內湖_港墘",          "loc": "25.0650,121.6050", "r": 1800},

    # ── 南港區（2 個點，r=2000）──
    {"name": "南港_南港路",        "loc": "25.0550,121.6070", "r": 2000},
    {"name": "南港_展覽館",        "loc": "25.0480,121.6200", "r": 2000},

    # ── 文山區（2 個點，r=2500）──
    {"name": "文山_木柵",          "loc": "24.9980,121.5680", "r": 2500},
    {"name": "文山_景美政大",      "loc": "25.0100,121.5550", "r": 2000},

    # ════════════════════════════════════════════════════════
    #  新北市（30 個點）
    # ════════════════════════════════════════════════════════

    # ── 板橋區（4 個點）──
    {"name": "板橋_車站",          "loc": "25.0130,121.4620", "r": 1500},
    {"name": "板橋_南",            "loc": "25.0000,121.4600", "r": 1500},
    {"name": "板橋_東",            "loc": "25.0065,121.4730", "r": 1500},
    {"name": "板橋_北",            "loc": "25.0200,121.4500", "r": 1500},

    # ── 中和區（3 個點）──
    {"name": "中和_中和路",        "loc": "24.9980,121.4870", "r": 1500},
    {"name": "中和_南",            "loc": "24.9820,121.4800", "r": 1800},
    {"name": "中和_北",            "loc": "25.0080,121.4870", "r": 1500},

    # ── 永和區（2 個點）──
    {"name": "永和_永和路",        "loc": "25.0130,121.5140", "r": 1200},
    {"name": "永和_南",            "loc": "25.0060,121.5110", "r": 1200},

    # ── 三重區（3 個點）──
    {"name": "三重_三重路",        "loc": "25.0610,121.4870", "r": 1500},
    {"name": "三重_北",            "loc": "25.0730,121.4780", "r": 1500},
    {"name": "三重_南",            "loc": "25.0510,121.4940", "r": 1500},

    # ── 新莊區（3 個點）──
    {"name": "新莊_新莊路",        "loc": "25.0360,121.4490", "r": 1500},
    {"name": "新莊_北",            "loc": "25.0500,121.4420", "r": 1800},
    {"name": "新莊_南",            "loc": "25.0230,121.4530", "r": 1800},

    # ── 蘆洲區（2 個點）──
    {"name": "蘆洲_中正路",        "loc": "25.0870,121.4690", "r": 1200},
    {"name": "蘆洲_北",            "loc": "25.0940,121.4760", "r": 1200},

    # ── 新店區（3 個點）──
    {"name": "新店_新店路",        "loc": "24.9670,121.5380", "r": 1500},
    {"name": "新店_安坑",          "loc": "24.9530,121.5230", "r": 2000},
    {"name": "新店_北",            "loc": "24.9800,121.5450", "r": 1500},

    # ── 淡水區（3 個點）──
    {"name": "淡水_老街",          "loc": "25.1700,121.4500", "r": 1800},
    {"name": "淡水_漁人碼頭",      "loc": "25.1820,121.4250", "r": 2000},
    {"name": "淡水_紅樹林",        "loc": "25.1560,121.4640", "r": 1800},

    # ── 汐止區（2 個點）──
    {"name": "汐止_中正路",        "loc": "25.0670,121.6450", "r": 2000},
    {"name": "汐止_東",            "loc": "25.0790,121.6580", "r": 2000},

    # ── 土城區（2 個點）──
    {"name": "土城_中央路",        "loc": "24.9750,121.4390", "r": 2000},
    {"name": "土城_南",            "loc": "24.9600,121.4480", "r": 2000},

    # ── 樹林區（1 個點）──
    {"name": "樹林_中山路",        "loc": "24.9900,121.4200", "r": 2500},

    # ── 泰山/五股（2 個點）──
    {"name": "泰山_明志路",        "loc": "25.0610,121.4350", "r": 2000},
    {"name": "五股_成泰路",        "loc": "25.0880,121.4530", "r": 2000},

    # ── 林口區（1 個點）──
    {"name": "林口_文化三路",      "loc": "25.0780,121.3720", "r": 3000},
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
    # 葡萄酒（酒窖/酒莊 優先於清酒，避免誤判）
    if any(k in n for k in ["wine", "葡萄酒", "紅酒", "白酒", "champagne", "prosecco", "bubbles",
                             "酒窖", "酒莊", "winery", "vino", "vin", "cellar"]):
        return "wine"
    # 清酒
    if any(k in n for k in ["sake", "清酒", "日本酒", "izakaya", "居酒屋"]):
        return "sake"
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


def guess_cocktail_sub(name: str) -> str:
    """
    調酒吧子分類（僅 cat='cocktail' 時使用）
    優先順序：茶酒 > 水果 > 創意 > 妹酒 > 經典（預設）
    """
    n = name.lower()
    if any(k in n for k in ["茶", "tea", "oolong", "烏龍", "普洱", "花茶", "台灣茶", "東方美人", "茶酒"]):
        return "tea"
    if any(k in n for k in ["水果", "fruit", "熱帶", "tropical", "芒果", "mango",
                             "鳳梨", "荔枝", "lychee", "百香果", "passion", "莓", "berry", "柑橘", "citrus"]):
        return "fruit"
    if any(k in n for k in ["創意", "creative", "實驗", "lab", "分子", "molecular",
                             "concept", "概念", "innovative", "創新", "avant"]):
        return "creative"
    if any(k in n for k in ["甜", "sweet", "少女", "可愛", "cute", "花系", "bubble",
                             "夢幻", "kawaii", "糖", "粉", "dessert"]):
        return "sweet"
    if any(k in n for k in ["經典", "classic", "古典", "old fashioned", "manhattan",
                             "martini", "negroni", "daiquiri", "傳統", "老派"]):
        return "classic"
    return ""  # 無明顯特徵，留空（顯示在「全部」但不歸入子分類）

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

    print("🍸 TIPPLE 酒吧資料爬蟲 v3.0")
    print(f"   門檻：評分 >= {MIN_RATING}，評論數 >= {MIN_REVIEWS}")
    print(f"   目標城市：台北 / 新北 / 台中 / 台南 / 高雄")
    print(f"   輸出檔案：{OUTPUT_FILE}")
    print(f"   開始時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ── 載入既有資料，保留評論 / 照片 ────────────────────────────
    existing_by_pid = {}
    max_existing_id = 0
    try:
        with open(EXISTING_FILE, "r", encoding="utf-8") as f:
            raw = f.read()
        existing_data = json.loads(raw)
        for b in existing_data.get("bars", []):
            pid = b.get("google_place_id")
            if pid:
                existing_by_pid[pid] = b
            max_existing_id = max(max_existing_id, b.get("id", 0))
        print(f"📂 載入既有資料：{len(existing_by_pid)} 間（保留評論 / 照片）\n")
    except Exception:
        print("📂 無既有資料，從頭建立\n")

    seen_place_ids = set()
    bars = []
    bar_id = max_existing_id + 1

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
            if rating < MIN_RATING or review_count < MIN_REVIEWS:
                continue
            place_name_raw = place.get("displayName", {}).get("text", "").lower()
            if any(kw in place_name_raw for kw in EXCLUDE_KEYWORDS):
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
            cocktail_sub = guess_cocktail_sub(name) if cat == "cocktail" else ""
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
                "cocktail_sub": cocktail_sub,
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

            # 如果既有資料有這間酒吧，保留評論 / 照片 / vibes
            if place_id in existing_by_pid:
                old = existing_by_pid[place_id]
                bar["id"]             = old["id"]   # 保留原 ID
                bar["review_list"]    = old.get("review_list", [])
                bar["review_summary"] = old.get("review_summary", "")
                if old.get("photo_refs"):            # 有照片就用舊的
                    bar["photo_refs"] = old["photo_refs"]
                if old.get("vibes"):                 # 有分類就用舊的
                    bar["vibes"] = old["vibes"]
                    bar["tags"]  = old["vibes"]
                bar_id -= 1  # 不消耗新 ID
            else:
                bar["review_list"]    = []
                bar["review_summary"] = ""

            bars.append(bar)
            bar_id += 1
            tag = "🔄" if place_id in existing_by_pid else "🆕"
            print(f"  {tag} [{bar_id-1:03d}] {name} ({district['en']}) — {rating}★")

    # 依評分排序
    bars.sort(key=lambda b: b["score"], reverse=True)
    # 重新連號 ID
    for i, b in enumerate(bars, 1):
        b["id"] = i

    new_count      = sum(1 for b in bars if not b.get("review_list") and not existing_by_pid.get(b.get("google_place_id")))
    carried_count  = sum(1 for b in bars if b.get("review_list"))
    print(f"\n📊 統計：")
    print(f"   新酒吧（需抓評論）：{new_count} 間")
    print(f"   既有酒吧（保留評論）：{carried_count} 間")

    # 輸出 bars.json
    output = {
        "meta": {
            "version": "3.0",
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "total": len(bars),
            "min_rating": MIN_RATING,
            "min_reviews": MIN_REVIEWS,
            "sources": ["google_maps"],
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
