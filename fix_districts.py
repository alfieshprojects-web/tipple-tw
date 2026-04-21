"""
TIPPLE — 地區修正腳本 v1.0
============================
從 addr_zh（Google Maps 格式）解析正確的城市（area）和行政區（district_zh/district_en），
修正 bars.json 中幾乎全為 'taipei' 的錯誤 area 欄位。

執行方式：
  python3 fix_districts.py           # 直接修正並儲存
  python3 fix_districts.py --dry-run # 預覽，不儲存
"""

import json
import re
import argparse
from datetime import datetime
from collections import Counter

INPUT_FILE  = "bars.json"
OUTPUT_FILE = "bars.json"

# ── 城市對應表 ────────────────────────────────────────────────────────────────
CITY_MAP = {
    "Taipei":     {"area": "taipei",     "zh": "台北市"},
    "New Taipei": {"area": "newtaipei",  "zh": "新北市"},
    "Taoyuan":    {"area": "taoyuan",    "zh": "桃園市"},
    "Hsinchu":    {"area": "hsinchu",    "zh": "新竹市"},
    "Miaoli":     {"area": "miaoli",     "zh": "苗栗縣"},
    "Taichung":   {"area": "taichung",   "zh": "台中市"},
    "Changhua":   {"area": "changhua",   "zh": "彰化縣"},
    "Nantou":     {"area": "nantou",     "zh": "南投縣"},
    "Yunlin":     {"area": "yunlin",     "zh": "雲林縣"},
    "Chiayi":     {"area": "chiayi",     "zh": "嘉義市"},
    "Tainan":     {"area": "tainan",     "zh": "台南市"},
    "Kaohsiung":  {"area": "kaohsiung",  "zh": "高雄市"},
    "Pingtung":   {"area": "pingtung",   "zh": "屏東縣"},
    "Yilan":      {"area": "yilan",      "zh": "宜蘭縣"},
    "Hualien":    {"area": "hualien",    "zh": "花蓮縣"},
    "Taitung":    {"area": "taitung",    "zh": "台東縣"},
    "Penghu":     {"area": "penghu",     "zh": "澎湖縣"},
    "Kinmen":     {"area": "kinmen",     "zh": "金門縣"},
    "Keelung":    {"area": "keelung",    "zh": "基隆市"},
}

# ── 行政區對應表（英文 key → 中文） ──────────────────────────────────────────
DISTRICT_ZH = {
    # 台北市 12區
    "Da'an":      "大安區", "Zhongshan":   "中山區", "Xinyi":     "信義區",
    "Songshan":   "松山區", "Zhongzheng":  "中正區", "Datong":    "大同區",
    "Wanhua":     "萬華區", "Neihu":       "內湖區", "Shilin":    "士林區",
    "Beitou":     "北投區", "Nangang":     "南港區", "Wenshan":   "文山區",
    # 新北市
    "Banqiao":    "板橋區", "Sanchong":    "三重區", "Zhonghe":   "中和區",
    "Yonghe":     "永和區", "Xinzhuang":   "新莊區", "Tucheng":   "土城區",
    "Luzhou":     "蘆洲區", "Tamsui":      "淡水區", "Xindian":   "新店區",
    "Xizhi":      "汐止區", "Linkou":      "林口區", "Shulin":    "樹林區",
    "Sijhih":     "汐止區", "Sindian":     "新店區",
    # 桃園市
    "Taoyuan":    "桃園區", "Zhongli":     "中壢區", "Bade":      "八德區",
    "Dayuan":     "大園區", "Guishan":     "龜山區", "Luzhu":     "蘆竹區",
    "Pingzhen":   "平鎮區", "Yangmei":     "楊梅區",
    # 新竹市/縣
    "East":       "東區",   "North":       "北區",   "Hsinchu":   "新竹區",
    # 台中市
    "Central":    "中區",   "West":        "西區",   "South":     "南區",
    "Xitun":      "西屯區", "Nantun":      "南屯區", "Beitun":    "北屯區",
    "Taiping":    "太平區", "Dali":        "大里區",  "Wufeng":   "霧峰區",
    # 台南市
    "West Central": "中西區", "Anping":    "安平區",  "Annan":    "安南區",
    "Yongkang":   "永康區", "Rende":       "仁德區",
    # 高雄市
    "Sanmin":     "三民區", "Zuoying":     "左營區",  "Yancheng": "鹽埕區",
    "Qianjin":    "前金區", "Xinxing":     "新興區",  "Lingya":   "苓雅區",
    "Fengshan":   "鳳山區", "Zuoying":     "左營區",  "Daliao":   "大寮區",
    "Nanzi":      "楠梓區", "Qianzhen":    "前鎮區",  "Cianjhen":  "前鎮區",
    "Sinsing":    "新興區",
    # 宜蘭縣
    "Yilan":      "宜蘭市", "Luodong":     "羅東鎮",
    # 花蓮縣
    "Hualien":    "花蓮市",
    # 台東縣
    "Taitung":    "台東市",
    # 屏東縣
    "Pingtung":   "屏東市",
    # 嘉義市
    "Chiayi":     "嘉義市",
    # 基隆市
    "Zhongzheng": "中正區", "Ren'ai":      "仁愛區",
}

def parse_city(addr: str) -> dict | None:
    """從地址解析城市，回傳 CITY_MAP 中的 dict 或 None"""
    for city_en, info in CITY_MAP.items():
        if city_en + " City" in addr or city_en + " County" in addr:
            return {**info, "en": city_en}
    return None

def parse_district(addr: str) -> tuple[str, str]:
    """從地址解析行政區，回傳 (district_en, district_zh)"""
    parts = addr.replace(",", " ,").split()
    for i, p in enumerate(parts):
        if p == "District" and i > 0:
            # 抓前面最多 2 個詞
            district_parts = []
            j = i - 1
            while j >= 0 and parts[j] not in [",", "City", "Taiwan", "County"]:
                word = parts[j]
                if word == ",":
                    break
                district_parts.insert(0, word)
                j -= 1
                if len(district_parts) >= 2:
                    break
            key = " ".join(district_parts)
            zh = DISTRICT_ZH.get(key, "")
            return (key + " District", zh)
    return ("", "")

def main():
    parser = argparse.ArgumentParser(description="TIPPLE 地區修正腳本")
    parser.add_argument("--dry-run", action="store_true", help="只預覽，不儲存")
    args = parser.parse_args()

    print("🗺  TIPPLE 地區修正腳本 v1.0")
    print(f"   開始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.dry_run:
        print("   ⚠  DRY-RUN 模式，不會寫入檔案\n")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    bars = data.get("bars", [])
    print(f"📋 酒吧總數：{len(bars)} 間\n")

    city_count   = Counter()
    no_city      = []
    changed      = 0
    no_district  = 0

    for bar in bars:
        addr = bar.get("addr_zh", "") or bar.get("addr_en", "")
        city_info = parse_city(addr)

        if not city_info:
            no_city.append(bar.get("name", "?"))
            continue

        new_area = city_info["area"]
        dist_en, dist_zh = parse_district(addr)

        old_area = bar.get("area", "")
        changed += (old_area != new_area)

        if not args.dry_run:
            bar["area"]        = new_area
            bar["district_en"] = dist_en
            bar["district_zh"] = dist_zh if dist_zh else dist_en

        city_count[new_area] += 1
        if not dist_zh:
            no_district += 1

    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 完成！{changed} 間酒吧的 area 有更新")
    print(f"   無行政區資料：{no_district} 間（保留英文名）")
    if no_city:
        print(f"   無城市資料（跳過）：{len(no_city)} 間")

    print("\n📊 城市分布：")
    for area, cnt in sorted(city_count.items(), key=lambda x: -x[1]):
        bar_str = "█" * (cnt // 50)
        print(f"  {area:<12} {cnt:5d}  {bar_str}")

if __name__ == "__main__":
    main()
