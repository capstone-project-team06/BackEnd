# app/services/image_searcher.py
# -*- coding: utf-8 -*-
"""
Image Search Adapter (SerpAPI Bing / Google Images)

환경변수:
    SERPAPI_KEY       : str  (SerpAPI API Key)
    IMG_HOST_WHITELIST: str  (쉼표구분 도메인 목록, 없으면 기본값 사용)
    IMG_HOST_BLACKLIST: str  (쉼표구분 도메인 목록, 없으면 기본값 사용)
    IMG_SEARCH_DEBUG  : "1" 이면 디버그 로그 출력

주요 함수:
    search_reference_images(celeb_name, needs, providers=("bing","google"), max_results=30, ...)

반환 스키마(예):
{
  "title": str | None,
  "image": str,          # 원본 이미지 URL
  "thumb": str | None,   # 썸네일 URL
  "page": str | None,    # 호스트 페이지(컨텍스트)
  "format": str | None,  # jpg/png/gif 등 (SerpAPI에서는 대부분 None)
  "license": str | None, # (SerpAPI에 직접 라이선스는 잘 안옴, 보통 None)
  "source": "bing_serpapi" | "google_serpapi",
  "host": str | None,    # 도메인
  "editorial_only": bool,# 휴리스틱(언론/보도성) True/False
}
"""
from __future__ import annotations
import os, time, json
from typing import List, Dict, Any, Iterable, Tuple
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl
import requests
import re
from dotenv import load_dotenv
load_dotenv()


# -----------------------------
# Config
# -----------------------------
_SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()

# 디버그 플래그
_IMG_DEBUG = os.getenv("IMG_SEARCH_DEBUG", "0") == "1"

_DEFAULT_TIMEOUT = 10
_DEFAULT_HEADERS = {"User-Agent": "style-pipeline/1.0 (+image_searcher)"}

# 호스트 화이트/블랙리스트(환경변수로 커스터마이즈 가능, 쉼표구분)
_HOST_WHITELIST = set([h.strip().lower() for h in os.getenv(
    "IMG_HOST_WHITELIST",
    "gettyimages.com,images.unsplash.com,upload.wikimedia.org,commons.wikimedia.org,"
    "vogue.com,harpersbazaar.com,elle.com,naver.com,news.naver.com"
).split(",") if h.strip()])

_HOST_BLACKLIST = set([h.strip().lower() for h in os.getenv(
    "IMG_HOST_BLACKLIST",
    "pinterest.com,kr.pinterest.com,facebook.com,instagram.com,x.com,twitter.com"
).split(",") if h.strip()])

# 편집/보도 전용으로 분류할 확률이 높은 도메인(휴리스틱)
_EDITORIAL_HOST_HINTS = set([
    "gettyimages.com", "alamy.com", "shutterstock.com", "afp.com",
    "apimages.com", "reuters.com", "news.naver.com", "bbc.com", "cnn.com",
    "nytimes.com", "washingtonpost.com", "variety.com", "hollywoodreporter.com"
])

# -----------------------------
# Utils
# -----------------------------
def _canonical_url(u: str) -> str:
    """간단한 URL 정규화: 쿼리에서 추적 파라미터 제거 등."""
    try:
        p = urlparse(u)
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if k.lower() not in ("utm_source","utm_medium","utm_campaign","utm_term","utm_content","spm")]
        return urlunparse((p.scheme, p.netloc.lower(), p.path, p.params, urlencode(query, doseq=True), ""))
    except Exception:
        return u

def _host(u: str) -> str | None:
    try:
        return urlparse(u).netloc.lower()
    except Exception:
        return None

def _is_editorial_host(host: str | None) -> bool:
    if not host:
        return False
    return any(host.endswith(h) for h in _EDITORIAL_HOST_HINTS)

def _pass_host_policy(host: str | None) -> bool:
    if not host:
        return False
    if any(host.endswith(b) for b in _HOST_BLACKLIST):
        return False
    if _HOST_WHITELIST and not any(host.endswith(w) for w in _HOST_WHITELIST):
        # 화이트리스트가 설정돼 있으면 리스트 외 도메인 제외
        return False
    return True

def _dedup(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        key = (_canonical_url(it.get("image","")), _canonical_url(it.get("page","") or ""))
        if key[0] and key not in seen:
            out.append(it)
            seen.add(key)
    return out

def _normalize_format(fmt: str | None) -> str | None:
    if not fmt:
        return None
    fmt = fmt.lower()
    if fmt.startswith("image/"):
        fmt = fmt.split("/",1)[1]
    return fmt

def _normalize_item(
    title: str | None, image: str, thumb: str | None, page: str | None,
    fmt: str | None, license_: str | None, source: str
) -> Dict[str, Any]:
    image = _canonical_url(image)
    page  = _canonical_url(page) if page else None
    host  = _host(page or image)
    return {
        "title": title,
        "image": image,
        "thumb": thumb,
        "page": page,
        "format": _normalize_format(fmt),
        "license": license_,
        "source": source,
        "host": host,
        "editorial_only": _is_editorial_host(host)
    }

# -----------------------------
# Query builder
# -----------------------------
def build_query(celeb_name: str, needs: List[str] | Tuple[str,...]) -> str:
    """
    예) celeb_name="아일릿 원희", needs=["여름", "블레이저"] →
        "아일릿 원희 여름 블레이저 코디 착장 패션 스타일 룩"

    예) needs=["블레이저, 여름"] 처럼 한 문자열 안에 콤마가 섞여 있어도
        "여름 블레이저" 식으로 정규화해서 사용.
    """
    # 1) needs 리스트 안의 문자열을 콤마/공백 기준으로 전부 쪼개서 토큰화
    tokens: List[str] = []
    for n in needs:
        if not n:
            continue
        parts = re.split(r"[,\s]+", n)
        for p in parts:
            p = p.strip()
            if p:
                tokens.append(p)

    # 2) 순서 유지 + 중복 제거
    seen = set()
    clean_needs: List[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            clean_needs.append(t)

    need_txt = " ".join(clean_needs)

    base = f"{celeb_name} {need_txt}".strip()
    tail = "코디 착장 패션 스타일 룩"
    return f"{base} {tail}".strip()
# -----------------------------
# SerpAPI provider
# -----------------------------
def _search_serpapi(
    engine: str,
    q: str,
    num: int = 20,
) -> List[Dict[str, Any]]:
    """
    공통 SerpAPI 호출 함수.
    engine 예:
        - "bing_images"
        - "google_images"
    """
    if not _SERPAPI_KEY:
        if _IMG_DEBUG:
            print(f"[image_searcher] _search_serpapi: SERPAPI_KEY not set. engine={engine}, q='{q}'")
        return []

    url = "https://serpapi.com/search.json"
    params = {
        "engine": engine,
        "q": q,
        "api_key": _SERPAPI_KEY,
        # 엔진별로 실제 지원 파라미터는 조금 다르지만,
        # num/count 정도는 대부분 받아줌. 필요시 튜닝 가능.
        "num": num,
        "safe": "off",
    }

    try:
        if _IMG_DEBUG:
            print(f"[image_searcher] _search_serpapi: engine={engine}, q='{q}', num={num}")

        r = requests.get(url, headers=_DEFAULT_HEADERS, params=params, timeout=_DEFAULT_TIMEOUT)
        r.raise_for_status()
        js = r.json()

        items: List[Dict[str, Any]] = []

        # bing_images / google_images 모두 images_results 필드를 사용하는 공통 패턴
        for v in js.get("images_results", []) or []:
            image_url = v.get("original") or v.get("thumbnail") or v.get("image")
            page_url  = v.get("link")
            title     = v.get("title") or v.get("source")

            if not image_url:
                continue

            # SerpAPI는 mime/type을 잘 안 주므로 fmt/license는 대부분 None
            items.append(_normalize_item(
                title=title,
                image=image_url,
                thumb=v.get("thumbnail"),
                page=page_url,
                fmt=None,
                license_=None,
                source=f"{engine}_serpapi",
            ))

        if _IMG_DEBUG:
            print(f"[image_searcher] _search_serpapi: engine={engine}, got {len(items)} raw items")

        return items
    except requests.RequestException as e:
        if _IMG_DEBUG:
            print(f"[image_searcher] _search_serpapi: ERROR engine={engine}, err={e}")
        return []

# -----------------------------
# Rank / Filter
# -----------------------------
def _filter(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for it in items:
        if not it.get("image"):
            continue
        if not _pass_host_policy(it.get("host")):
            continue
        out.append(it)
    return out

def _rank(items: List[Dict[str, Any]], prefer_editorial: bool = True) -> List[Dict[str, Any]]:
    """
    간단 랭킹: (editorial 우선) + (호스트명 길이 짧을수록) + (제목 길이 가산)
    실제론 CLIP/text score와 결합 권장.
    """
    def score(x):
        s = 0.0
        if prefer_editorial and x.get("editorial_only"):
            s += 2.0
        host = x.get("host") or ""
        title = x.get("title") or ""
        s += max(0.0, 1.0 - len(host)/40.0)
        s += min(len(title)/80.0, 1.0)
        return s
    return sorted(items, key=score, reverse=True)

# -----------------------------
# Public API
# -----------------------------
def search_reference_images(
    celeb_name: str,
    needs: List[str] | Tuple[str, ...],
    providers: Tuple[str, ...] = ("bing", "google"),
    max_results: int = 30,
    freshness: str = "Month",   # SerpAPI에 직접 쓰진 않지만 시그니처 유지
    img_size: str = "large",    # SerpAPI에도 직접 쓰진 않음
    prefer_editorial: bool = True,
    sleep_between: float = 0.3
) -> List[Dict[str, Any]]:
    """
    연예인 + 요구사항(예: ["여름옷","블레이저"]) 기준으로 이미지 검색.
    - providers:
        "bing"   → SerpAPI Bing Images (engine="bing_images")
        "google" → SerpAPI Google Images (engine="google_images")
    - 반환: 공통 스키마 리스트
    """
    q = build_query(celeb_name, list(needs) if isinstance(needs, tuple) else needs)

    if _IMG_DEBUG:
        print("==================================================")
        print(f"[image_searcher] search_reference_images()")
        print(f"  celeb_name   = {celeb_name}")
        print(f"  needs        = {needs}")
        print(f"  query        = '{q}'")
        print(f"  providers    = {providers}")
        print(f"  max_results  = {max_results}")
        print(f"  whitelist    = {_HOST_WHITELIST}")
        print(f"  blacklist    = {_HOST_BLACKLIST}")

    results: List[Dict[str, Any]] = []

    for p in providers:
        if p == "bing":
            items = _search_serpapi("bing_images", q, num=max_results)
            if _IMG_DEBUG:
                print(f"[image_searcher] provider=bing_serpapi -> {len(items)} items")
            results += items

        elif p == "google":
            items = _search_serpapi("google_images", q, num=min(10, max_results))
            if _IMG_DEBUG:
                print(f"[image_searcher] provider=google_serpapi -> {len(items)} items")
            results += items

        if sleep_between > 0:
            time.sleep(sleep_between)

    if _IMG_DEBUG:
        print(f"[image_searcher] total raw results before filter/dedup: {len(results)}")
        sample_hosts = list({it.get("host") for it in results if it.get("host")})[:10]
        print(f"[image_searcher] sample hosts (raw): {sample_hosts}")

    filtered = _filter(results)
    if _IMG_DEBUG:
        print(f"[image_searcher] after host filter: {len(filtered)}")

    deduped = _dedup(filtered)
    if _IMG_DEBUG:
        print(f"[image_searcher] after dedup: {len(deduped)}")

    ranked = _rank(deduped, prefer_editorial=prefer_editorial)
    if _IMG_DEBUG:
        print(f"[image_searcher] after ranking: {len(ranked)}")
        print("==================================================")

    return ranked[:max_results]

# -----------------------------
# CLI quick test
# -----------------------------
if __name__ == "__main__":
    """
    예시 실행 (프로젝트 루트에서):
        cd app
        python -m services.image_searcher "아이유" "여름옷,블레이저"

    전제:
        - SERPAPI_KEY 환경변수 설정
        - (선택) IMG_SEARCH_DEBUG=1 설정 시 디버그 출력
    """
    import sys
    celeb = sys.argv[1] if len(sys.argv) > 1 else "아이유"
    needs = (sys.argv[2] if len(sys.argv) > 2 else "여름옷,블레이저").split(",")
    data = search_reference_images(celeb, needs, providers=("bing", "google"), max_results=25)
    print(json.dumps(data[:5], ensure_ascii=False, indent=2))
