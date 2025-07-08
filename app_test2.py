import streamlit as st
import requests
import folium
import json
import os
from streamlit_folium import st_folium
from config import VWORLD_KEY  # API 키는 config.py에 따로 보관

# ---------------- 기본 설정 ----------------
DEFAULT_CENTER = [37.5665, 126.9780]
ALL_DISALLOWED_JIMOK = ["전", "답", "과", "염전", "임야", "양어장"]

# ---------------- 캐시 로딩/저장 ----------------
def load_geocode_cache():
    if os.path.exists("geocode_cache.json"):
        with open("geocode_cache.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_geocode_cache(cache):
    with open("geocode_cache.json", "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

geocode_cache = load_geocode_cache()

# ---------------- 주소 → 좌표 변환 ----------------
def geocode_address(addr):
    for addr_type in ["road", "parcel"]:
        params = {
            "service": "address",
            "request": "getcoord",
            "format": "json",
            "type": addr_type,
            "key": VWORLD_KEY,
            "address": addr,
        }
        try:
            res = requests.get("https://api.vworld.kr/req/address", params=params, timeout=5)
            data = res.json()
            if data["response"]["status"] == "OK":
                point = data["response"]["result"]["point"]
                x = float(point["x"])
                y = float(point["y"])
                return [y, x]
        except:
            continue
    return None

# ---------------- 캐시 우선 지오코딩 ----------------
def geocode_cached(addr):
    if addr in geocode_cache:
        return geocode_cache[addr]
    coords = geocode_address(addr)
    if coords:
        geocode_cache[addr] = coords
        save_geocode_cache(geocode_cache)
    return coords

# ---------------- 지적도 WFS API 호출 ----------------
def fetch_cadastral_features(lat, lng):
    buffer = 0.001  # 약 100m 반경
    bbox = f"{lng - buffer},{lat - buffer},{lng + buffer},{lat + buffer},EPSG:4326"
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typename": "lt_cad_dg",
        "bbox": bbox,
        "output": "json",
        "key": VWORLD_KEY
    }
    try:
        res = requests.get("https://api.vworld.kr/req/wfs", params=params, timeout=5)
        data = res.json()
        return data.get("features", [])
    except Exception as e:
        st.error(f"❌ WFS API 오류: {e}")
        return []

# ---------------- 세션 상태 초기화 ----------------
if "map_center" not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if "search_coords" not in st.session_state:
    st.session_state.search_coords = None

# ---------------- UI ----------------
st.title("☀️ Solar Site Analysis")

# 사이드바 지목 필터
st.sidebar.header("🛑 회색으로 표시할 불가능 지목 선택")
selected_disallowed = st.sidebar.multiselect(
    "태양광 설치 제한 지목",
    ALL_DISALLOWED_JIMOK,
    default=ALL_DISALLOWED_JIMOK
)

# 주소 입력
addr = st.text_input("📍 주소를 입력하세요")

# ---------------- 주소 검색 및 중심 설정 ----------------
if addr:
    coords = geocode_cached(addr)
    if coords:
        st.session_state.map_center = coords
        st.session_state.search_coords = coords
        st.success(f"📍 좌표 변환 성공: 위도 {coords[0]:.6f}, 경도 {coords[1]:.6f}")
    else:
        st.error("❌ 주소 좌표를 찾을 수 없습니다.")

# ---------------- 지도 생성 ----------------
m = folium.Map(location=st.session_state.map_center, zoom_start=15)
tile_url = f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png"
folium.TileLayer(tiles=tile_url, attr="VWorld").add_to(m)

# ---------------- 지목 필터링 및 시각화 ----------------
if st.session_state.search_coords:
    lat, lng = st.session_state.search_coords
    features = fetch_cadastral_features(lat, lng)

    if not features:
        st.warning("⚠️ 해당 주소 근처에 필지 데이터가 없습니다.")
    else:
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            jimok = props.get("jimok", "")

            if jimok not in selected_disallowed:
                continue

            if geom.get("type") == "Polygon":
                coords = geom["coordinates"][0]  # 외곽 폴리곤만 사용
                coords = [[y, x] for x, y in coords]  # GeoJSON → Folium 좌표 순서 변환

                folium.Polygon(
                    locations=coords,
                    color="gray",
                    fill=True,
                    fill_opacity=0.5,
                    tooltip=f"❌ {props.get('juso', '주소 없음')} - {jimok}"
                ).add_to(m)

# ---------------- 지도 출력 ----------------
st_folium(m, width=1000, height=600)
