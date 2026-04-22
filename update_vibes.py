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

# ── 調酒子分類關鍵字 ─────────────────────────────────────────────────────────
COCKTAIL_SUB_KEYWORDS = {
    "tea": {
        "zh": ["茶", "烏龍", "普洱", "花茶", "綠茶", "紅茶", "高山茶", "台灣茶", "東方美人", "茶調酒"],
        "en": ["tea", "oolong", "pu-erh", "green tea", "taiwanese tea", "tea cocktail", "herbal tea"]
    },
    "fruit": {
        "zh": ["水果", "熱帶", "芒果", "鳳梨", "荔枝", "百香果", "莓果", "柑橘", "西瓜", "草莓", "水蜜桃"],
        "en": ["fruit", "tropical", "mango", "pineapple", "lychee", "passion fruit", "berry", "citrus", "watermelon"]
    },
    "creative": {
        "zh": ["創意", "實驗", "分子", "創新", "前衛", "獨特", "特調", "概念", "手法"],
        "en": ["creative", "experimental", "molecular", "innovative", "avant-garde", "concept", "signature technique"]
    },
    "sweet": {
        "zh": ["甜", "少女", "可愛", "花系", "夢幻", "糖漿", "甜蜜", "粉紅", "輕甜", "甜口"],
        "en": ["sweet", "kawaii", "cute", "floral", "bubbly", "girly", "dessert cocktail", "sugar syrup"]
    },
    "classic": {
        "zh": ["經典", "古典", "傳統", "純飲", "純粹", "老派", "調酒師", "職人"],
        "en": ["classic", "traditional", "old fashioned", "manhattan", "martini", "negroni", "daiquiri"]
    },
}

def classify_cocktail_sub(bar: dict) -> str:
    """
    從 review_summary + 評論 + 名稱推斷調酒子分類。
    只對 cat='cocktail' 的酒吧執行，預設 classic。
    """
    if bar.get("cat") != "cocktail":
        return bar.get("cocktail_sub", "")

    summary = bar.get("review_summary", "").lower()
    has_summary = bool(summary)

    base_texts = [bar.get("name", ""), bar.get("zh", "")]
    for r in bar.get("review_list", []):
        base_texts.append(r.get("text", ""))
    base = " ".join(base_texts).lower()

    scores = {}
    for sub, kws in COCKTAIL_SUB_KEYWORDS.items():
        score = 0
        for kw in kws["zh"] + kws["en"]:
            kw_l = kw.lower()
            if has_summary and kw_l in summary:
                score += 3
            if kw_l in base:
                score += 1
        scores[sub] = score

    best = max(scores, key=lambda k: scores[k])
    # 只有確實命中關鍵字才回傳子分類；無明顯特徵就留空（顯示在「全部」但不歸入任何子分類）
    return best if scores[best] > 0 else ""

# ── 分類主函式 ────────────────────────────────────────────────────────────────
def classify_vibes(bar: dict) -> list:
    """
    分析酒吧名稱 + AI 摘要（generativeSummary）+ 評論，回傳符合的 vibe 列表。

    加權策略：
      - review_summary（Google AI 彙整所有評論）: 權重 ×3
      - 個別評論文字: 權重 ×1
      - 酒吧名稱 / 地址: 權重 ×1
    閾值：
      - 有 review_summary 時：score >= 2（避免雜訊）
      - 無 review_summary 時：score >= 1
    """
    summary = bar.get("review_summary", "").lower()
    has_summary = bool(summary)

    # 基礎文字（權重 1）
    base_texts = [
        bar.get("name", ""),
        bar.get("zh", ""),
    ]
    for r in bar.get("review_list", []):
        base_texts.append(r.get("text", ""))
    base = " ".join(base_texts).lower()

    detected = []
    for vibe, kws in VIBE_KEYWORDS.items():
        score = 0
        for kw in kws["zh"] + kws["en"]:
            kw_l = kw.lower()
            # review_summary 命中：權重 ×3
            if has_summary and kw_l in summary:
                score += 3
            # 評論 / 名稱命中：權重 ×1
            if kw_l in base:
                score += 1

        threshold = 2 if has_summary else 1
        if score >= threshold:
            detected.append((vibe, score))

    # 依命中分數排序，取前 6 個 vibe
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
    sub_changed = 0
    vibe_count = {}
    sub_count = {}

    for bar in targets:
        old_vibes = set(bar.get("vibes", bar.get("tags", [])))
        new_vibes = classify_vibes(bar)
        new_set   = set(new_vibes)

        # 調酒子分類
        new_sub = classify_cocktail_sub(bar)
        old_sub = bar.get("cocktail_sub", "")

        # 統計各 vibe / sub 出現次數
        for v in new_vibes:
            vibe_count[v] = vibe_count.get(v, 0) + 1
        if new_sub:
            sub_count[new_sub] = sub_count.get(new_sub, 0) + 1

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

        if new_sub != old_sub:
            if not args.dry_run:
                bar["cocktail_sub"] = new_sub
            sub_changed += 1

    if not args.dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！{changed} 間酒吧的 vibe 有更新")
    print(f"   {sub_changed} 間調酒吧的子分類有更新")
    print("\n📊 調酒子分類分布：")
    for sub, cnt in sorted(sub_count.items(), key=lambda x: -x[1]):
        print(f"  {sub:<10} {cnt:4d}")
    print("\n📊 各 Vibe 分布：")
    for vibe, cnt in sorted(vibe_count.items(), key=lambda x: -x[1]):
        bar_str = "█" * (cnt // 10)
        print(f"  {vibe:<15} {cnt:4d}  {bar_str}")

if __name__ == "__main__":
    main()
