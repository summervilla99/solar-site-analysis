import streamlit as st
import folium
import requests
import pandas as pd
from streamlit_folium import st_folium
from config import VWORLD_KEY

# st.set_page_config(page_title="Auto Solar - 주소 기반 필터링", layout="wide")
# ---------------- 설정 ----------------
DEFAULT_CENTER = [37.5665, 126.9780]
# ---------------- CSV 로딩 ----------------
@st.cache_data
def load_csv():
    df_zone = pd.read_csv("TN_SPCFC_WTNNC.csv", encoding="cp949")
    df_area = pd.read_csv("TN_USGAR_WTNNC.csv", encoding="cp949")
    return df_zone[["LOCATION_NAME", "ZONE_NAME"]], df_area[["LOCATION_NAME", "ZONE_NAME"]]

df_zone, df_area = load_csv()

# ---------------- 상태 초기화 ----------------
if "map_center" not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if "search_coords" not in st.session_state:
    st.session_state.search_coords = None

st.title("☀️ Solar System Analysis")

# ---------------- 주소 검색 함수 ----------------
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
            res = requests.get("http://api.vworld.kr/req/address", params=params)
            data = res.json()
            if data["response"]["status"] == "OK":
                point = data["response"]["result"]["point"]
                x = float(point["x"])
                y = float(point["y"])
                st.success(f"🎯 좌표 변환 성공: {addr} → 위도 {y:.6f}, 경도 {x:.6f}")
                return [y, x]
        except:
            continue
    return Nonep

# ---------------- 주소 → 지역명 추출 함수 ----------------
def reverse_geocode(lat, lng):
    url = "http://api.vworld.kr/req/address"
    params = {
        "service": "address",
        "request": "getaddress",
        "point": f"{lng},{lat}",
        "type": "both",
        "format": "json",
        "key": VWORLD_KEY
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        if data["response"]["status"] == "OK":
            return data["response"]["result"][0]["text"]
    except:
        return None

# ---------------- 주소 입력 UI ----------------
addr = st.text_input("📍 주소를 입력하세요", "")
if addr:
    coords = geocode_address(addr)
    if coords:
        st.session_state.map_center = coords
        st.session_state.search_coords = coords

# ---------------- 필터 UI ----------------
st.sidebar.header("🎛️ 필터 조건")
zone_filter = st.sidebar.multiselect("허용 용도지역 (ZONE_NAME)", df_zone["ZONE_NAME"].unique().tolist(), default=[])
area_filter = st.sidebar.multiselect("허용 용도구역 (ZONE_NAME)", df_area["ZONE_NAME"].unique().tolist(), default=[])

# ---------------- 지도 생성 ----------------
m = folium.Map(location=st.session_state.map_center, zoom_start=14)
vworld_tile_url = f"http://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png"
folium.TileLayer(tiles=vworld_tile_url, attr="VWorld").add_to(m)

# ---------------- 주소 검색 결과 → 필터링 ----------------
if st.session_state.search_coords:
    lat, lng = st.session_state.search_coords
    address = reverse_geocode(lat, lng)

    if address:
        st.info(f"📌 주소 검색 결과: {address}")
        region_keyword = address.split()[1]  # 예: "경주시"

        zone_match = df_zone[df_zone["LOCATION_NAME"].str.contains(region_keyword, na=False)]
        area_match = df_area[df_area["LOCATION_NAME"].str.contains(region_keyword, na=False)]

        zone_pass = any(zone_match["ZONE_NAME"].isin(zone_filter))
        area_pass = any(area_match["ZONE_NAME"].isin(area_filter))

        if zone_pass and area_pass:
            folium.Marker(
                location=[lat, lng],
                popup="✅ 조건 충족",
                icon=folium.Icon(color="green")
            ).add_to(m)
            st.success("✅ 해당 위치는 모든 조건을 만족합니다.")
        else:
            folium.Circle(
                location=[lat, lng],
                radius=100,
                color="gray",
                fill=True,
                fill_opacity=0.5,
                tooltip="❌ 조건 불충족"
            ).add_to(m)
            st.warning("❌ 필터 조건을 충족하지 않습니다.")
    else:
        st.error("📡 주소를 가져오지 못했습니다.")

# ---------------- 지도 출력 ----------------
st_folium(m, width=900, height=550)
