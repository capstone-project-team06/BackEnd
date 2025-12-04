# musinsa_category_probe.py
import requests

BASE_URL = "https://api.musinsa.com/api2/dp/v1/plp/goods"


def probe_range(prefix: str, gender: str = "M", start: int = 1, end: int = 50):
    """
    prefix: "001", "002", "003" 등 (상의/하의/아우터)
    start, end: 뒤 3자리 범위 (001 ~ 050 이런 느낌)
    """
    label = {
        "001": "상의(TOP)",
        "002": "하의(BOTTOM)",
        "003": "아우터(OUTER)",
    }.get(prefix, prefix)

    print(f"\n==============================")
    print(f"=== {label} prefix={prefix} ({start:03d}~{end:03d}) 탐색 ===")
    print(f"==============================")

    for i in range(start, end + 1):
        cat_code = f"{prefix}{i:03d}"  # 예: 001001, 001002 ...

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://www.musinsa.com",
            "Referer": f"https://www.musinsa.com/category/{cat_code}?gf={gender}",
        }

        params = {
            "gf": gender,
            "sortCode": "POPULAR",
            "category": cat_code,
            "size": 20,
            "caller": "CATEGORY",
            "page": 1,
            "seen": 0,
            "seenAds": "",
        }

        try:
            resp = requests.get(BASE_URL, headers=headers, params=params, timeout=5)
        except Exception as e:
            print(f"  [!!] {cat_code} 요청 실패: {e}")
            continue

        if resp.status_code != 200:
            # 비정상 응답이면 그냥 스킵 (출력 X)
            continue

        data = resp.json()
        items = (data.get("data") or {}).get("list") or []

        # 🔥 상품이 아예 없으면 출력하지 않고 넘어감
        if not items:
            continue

        # 여기서부터는 "내용이 있는" 카테고리만 출력
        print(f"\n=== 카테고리 {cat_code} (gender={gender}) ===")
        print(f"  상품 개수(최대 20개 조회 기준): {len(items)}")

        print("  샘플 상품:")
        for it in items[:3]:
            name = it.get("goodsName")
            link = it.get("goodsLinkUrl") or it.get("linkUrl")
            print(f"   - {name} | {link}")


def main():
    # 🔹 상의: 001xxx
    probe_range(prefix="001", gender="M", start=1, end=50)

    # 🔹 하의: 002xxx
    probe_range(prefix="002", gender="M", start=1, end=50)

    # 🔹 아우터: 003xxx
    probe_range(prefix="003", gender="M", start=1, end=50)


if __name__ == "__main__":
    main()