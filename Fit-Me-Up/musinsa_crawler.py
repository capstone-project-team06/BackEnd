import requests
import pandas as pd
import time


# ============================
#  카테고리 정의
# ============================

TOP_CATEGORIES = [
    "001001", "001002", "001003", "001004", "001005",
    "001006", "001008", "001010", "001011"
]

OUTER_CATEGORIES = [
    "002001", "002002", "002003", "002004", "002006",
    "002007", "002008", "002009", "002012", "002013",
    "002014", "002015", "002017", "002018", "002019",
    "002020", "002021", "002022", "002023", "002024",
    "002025", "002027"
]

BOTTOM_CATEGORIES = [
    "003002", "003004", "003005", "003006",
    "003007", "003008", "003009", "003010"
]


# ============================
#  단일 카테고리 크롤링
# ============================

def crawl_category_items(category, gender="M", target_count=30):
    """
    특정 카테고리에서 최대 30개의 상품 데이터를 가져와 리스트로 반환
    """
    base_url = "https://api.musinsa.com/api2/dp/v1/plp/goods"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Origin": "https://www.musinsa.com",
        "Referer": f"https://www.musinsa.com/category/{category}?gf={gender}",
    }

    rows = []
    page = 1

    print(f"\n=== 카테고리 {category} 크롤링 시작 ===")

    while len(rows) < target_count:
        params = {
            "gf": gender,
            "sortCode": "POPULAR",
            "category": category,
            "size": 60,
            "caller": "CATEGORY",
            "page": page,
            "seen": 0,
            "seenAds": "",
        }

        resp = requests.get(base_url, headers=headers, params=params)
        print(f"[요청] page={page}, status={resp.status_code}")

        if resp.status_code != 200:
            print("  응답 오류 → 중단")
            break

        data = resp.json()
        items = (data.get("data") or {}).get("list") or []

        if not items:
            print("  더 이상 상품 없음 → 중단")
            break

        for item in items:
            if len(rows) >= target_count:
                break

            name = item.get("goodsName")
            shop_link = item.get("goodsLinkUrl") or item.get("linkUrl")
            image_url = item.get("thumbnail") or item.get("imageUrl")

            if not (name and shop_link and image_url):
                continue

            rows.append({
                "category": category,
                "name": name,
                "shop_link": shop_link,
                "image_url": image_url,
            })

        page += 1
        time.sleep(0.2)

    print(f"→ {category} 수집 완료 (총 {len(rows)}개)")
    return rows


# ============================
#  전체 카테고리 통합 크롤링
# ============================

def crawl_all_to_single_csv(
    gender="M",
    target_count=30,
    out_csv="musinsa_full_clothes.csv"
):
    """
    상의/아우터/하의 전체 카테고리에서 30개씩 가져와 하나의 CSV로 저장
    """
    all_categories = TOP_CATEGORIES + OUTER_CATEGORIES + BOTTOM_CATEGORIES
    all_rows = []

    print("\n============== 전체 카테고리 크롤링 시작 ==============\n")

    for cat in all_categories:
        items = crawl_category_items(cat, gender=gender, target_count=target_count)
        all_rows.extend(items)

    print("\n============== CSV 생성 시작 ==============\n")

    df = pd.DataFrame(all_rows)

    # id 추가
    df.insert(0, "id", range(1, len(df) + 1))

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"✅ 저장 완료 → {out_csv} (총 {len(df)}개 상품)")


# ============================
#  실행
# ============================

if __name__ == "__main__":
    crawl_all_to_single_csv(
        gender="M",
        target_count=30,
        out_csv="musinsa_all_clothes_M.csv",
    )