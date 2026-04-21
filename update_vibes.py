"""
TIPPLE — Vibe 標籤自動分類腳本 v1.0
======================================
從酒吧名稱 + Google 評論文字自動偵測並更新 vibe tags。
建議每週執行一次（抓完新評論後）。

執行方式：
  python3 update_vibes.py          # 更新所有酒吧
  python3 update_vibes.py --dry-run  # 預覽但不儲存
"""

import json
import re
import argparse
from datetime import datetime

INPUT_FILE  = "bars.json"
OUTPUT_FILE = "bars.json"

# ── Vibe 關鍵字定義 ───────────────────────────────────────────────────────────
# 每個 vibe 對應中英文關鍵字（出現在名稱或評論中即計分）
VIBE_KEYWORDS = {
    "jazz": {
        "zh": ["爵士", "現場演奏", "樂手", "樂團", "live music", "爵士樂"],
        "en": ["jazz", "live music", "live band", "musicians", "saxophone", "trumpet"]
    },
    "dj": {
        "zh": ["DJ", "dj", "電音", "夜店", "舞池", "club"],
        "en": ["dj", "club", "electronic", "dance floor", "techno", "house music"]
    },
    "lounge": {
        "zh": ["沙發", "lounge", "放鬆", "舒適", "慵懶", "沙發區"],
        "en": ["lounge", "sofa", "cozy", "relax", "chill", "comfortable seating"]
    },
    "dive": {
        "zh": ["dive", "老派", "平價", "隨性", "庶民", "老酒吧", "復古"],
        "en": ["dive bar", "casual", "laid-back", "unpretentious", "neighborhood bar"]
    },
    "theme": {
        "zh": ["主題", "昭和", "電影", "遊戲", "cosplay", "裝潢", "特色佈置"],
        "en": ["theme", "themed", "retro", "game", "movie", "anime", "showa"]
    },
    "rooftop": {
        "zh": ["頂樓", "天台", "屋頂", "露天", "城市景觀", "夜景", "景觀台"],
        "en": ["rooftop", "rooftop bar", "skyline", "city view", "outdoor terrace", "panoramic"]
    },
    "hotel": {
        "zh": ["飯店", "hotel", "大廳", "lobby", "精品", "五星"],
        "en": ["hotel", "hotel bar", "lobby bar", "luxury", "five-star", "boutique hotel"]
    },
    "listen": {
        "zh": ["音樂鑑賞", "黑膠", "音響", "聆聽", "listen bar", "音樂酒吧", "唱片"],
        "en": ["listen bar", "vinyl", "hi-fi", "audiophile", "record", "music bar", "speakers"]
    },
    "group": {
        "zh": ["包廂", "朋友聚會", "團體", "聚餐", "大桌", "一群人", "適合團體"],
        "en": ["group", "private room", "party room", "group booking", "friends", "large table"]
    },
    "solo": {
        "zh": ["一人", "單獨", "吧台", "適合獨飲", "一個人", "自己來"],
        "en": ["solo", "bar seat", "alone", "single", "bar counter", "one person"]
    },
    "afterwork": {
        "zh": ["下班", "happy hour", "小酌", "輕鬆", "平日", "上班族"],
        "en": ["afterwork", "after work", "happy hour", "weeknight", "office workers", "casual drink"]
    },
    "party": {
        "zh": ["派對", "熱鬧", "嗨", "轟趴", "party", "慶生", "慶祝"],
        "en": ["party", "celebration", "birthday", "lively", "energetic", "nightlife"]
    },
    "date": {
        "zh": ["約會", "情侶", "浪漫", "氣氛", "romantic", "情調", "適合約會"],
        "en": ["date", "romantic", "couple", "intimate", "atmosphere", "candle", "date night"]
    },
    "zero_abv": {
        "zh": ["無酒精", "mocktail", "0%", "不含酒精", "清酒", "無酒"],
        "en": ["zero abv", "non-alcoholic", "mocktail", "alcohol-free", "virgin", "no alcohol"]
    },
    "low_abv": {
        "zh": ["低酒精", "低度", "微醺", "輕盈", "低ABV"],
        "en": ["low abv", "low alcohol", "light drink", "spritz", "session", "low-proof"]
    },
    "sustainable": {
        "zh": ["永續", "在地", "有機", "本土", "台灣食材", "友善環境", "環保"],
        "en": ["sustainable", "local", "organic", "farm-to-table", "eco", "green", "local ingredients"]
    },
    "experimental": {
        "zh": ["實驗", "分子", "創新", "實驗性", "前衛", "獨特", "創意調酒"],
        "en": ["experimental", "molecular", "innovative", "creative", "avant-garde", "unique cocktails"]
    },
    "tasting": {
        "zh": ["品飲", "侍酒", "tasting", "品酒", "評飲", "品鑑", "酒款介紹"],
        "en": ["tasting", "sommelier", "tasting room", "tasting menu", "pairing", "guided tasting"]
    },
    "chefs_table": {
        "zh": ["餐酒", "主廚", "美食", "料理", "omakase", "無菜單", "餐飲融合"],
        "en": ["chef", "food pairing", "gastro", "cuisine", "omakase", "tasting menu", "dining"]
    },
    "private": {
        "zh": ["預約", "私人", "包廂", "隱密", "會員", "限定", "需預約"],
        "en": ["reservation", "private", "members only", "exclusive", "booking required", "invitation"]
    },
    "hidden": {
        "zh": ["隱藏", "秘密", "地下", "找不到", "隱密", "speakeasy", "入口隱藏"],
        "en": ["hidden", "secret", "underground", "speakeasy", "hard to find", "unmarked door"]
    },
}

# ── 分類主函式 ────────────────────────────────────────────────────────────────
def classify_vibes(bar: dict) -> list:
    """分析酒吧名稱 + 評論，回傳符合的 vibe 列表"""
    # 收集全部文字
    texts = [
        bar.get("name", ""),
        bar.get("zh", ""),
        bar.get("addr_zh", ""),
        bar.get("addr_en", ""),
    ]
    for r in bar.get("review_list", []):
        texts.append(r.get("text", ""))

    combined = " ".join(texts).lower()

    detected = []
    for vibe, kws in VIBE_KEYWORDS.items():
        score = 0
        for kw in kws["zh"] + kws["en"]:
            if kw.lower() in combined:
                score += 1
        if score >= 1:   # 只要出現 1 個關鍵字就算符合
            detected.append((vibe, score))

    # 依命中次數排序，取前 6 個 vibe
    detected.sort(key=lambda x: x[1], reverse=True)
    return [v for v, _ in detected[:6]]

def main():
    parser = argparse.ArgumentParser(description="TIPPLE Vibe 自動分類")
    parser.add_argument("--dry-run", action="store_true", help="只預覽不儲存")
    parser.add_argument("--min-rating", type=float, default=0.0, help="只處理評分 >= N 的酒吧")
    args = parser.parse_args()

    print("🏷  TIPPLE Vibe 自動分類 v1.0")
    print(f"   開始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.dry_run:
        print("   ⚠  DRY-RUN 模式，不會寫入檔案\n")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    bars = data.get("bars", [])

    targets = [b for b in bars if b.get("google_rating", 0) >= args.min_rating]
    print(f"📋 處理酒吧：{len(targets)} 間\n")

    changed = 0
    vibe_count = {}

    for bar in targets:
        old_vibes = set(bar.get("vibes", bar.get("tags", [])))
        new_vibes = classify_vibes(bar)
        new_set   = set(new_vibes)

        # 統計各 vibe 出現次數
        for v in new_vibes:
            vibe_count[v] = vibe_count.get(v, 0) + 1

        if new_set != old_vibes:
            if not args.dry_run:
                bar["vibes"] = new_vibes
                bar["tags"]  = new_vibes
            changed += 1
            if args.dry_run:
                added   = new_set - old_vibes
                removed = old_vibes - new_set
                print(f"  {bar['name'][:30]:<30}  +"
                      f"{list(added)} -{list(removed)}")

    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！{changed} 間酒吧的 vibe 有更新")
    print("\n📊 各 Vibe 分布：")
    for vibe, cnt in sorted(vibe_count.items(), key=lambda x: -x[1]):
        bar_str = "█" * (cnt // 10)
        print(f"  {vibe:<15} {cnt:4d}  {bar_str}")

if __name__ == "__main__":
    main()
