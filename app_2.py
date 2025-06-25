import streamlit as st
from streamlit_folium import st_folium
import folium
import requests

# ------------------ 설정 ------------------
VWORLD_KEY = "72BB0951-F21B-3180-AD11-06B62E0C92FA"
DEFAULT_CENTER = [37.5665, 126.9780]  # 서울 시청

st.set_page_config(page_title="Auto Solar - 입지 필터링", layout="wide")
st.title("☀️ Auto Solar - 태양광 입지 필터링")

# ------------------ 세션 상태 ------------------
if "map_center" not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if "last_clicked" not in st.session_state:
    st.session_state.last_clicked = None

# ------------------ 주소 검색 함수 ------------------
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
    return None

# ------------------ 주소 입력 ------------------
addr = st.text_input("📍 주소를 입력하세요", "")
if addr:
    coords = geocode_address(addr)
    if coords:
        st.session_state.map_center = coords
        st.success(f"📍 {addr} → 위도 {coords[0]:.5f}, 경도 {coords[1]:.5f}")
    else:
        st.error("❌ 주소 변환 실패 또는 결과 없음")

# ------------------ 필터 설정 ------------------
st.sidebar.header("🎛️ 필터 조건")
zone_filter = st.sidebar.multiselect("허용 용도지역", ["계획관리지역", "농림지역", "도시지역"], default=["계획관리지역"])
distance_filter = st.sidebar.slider("최소 이격거리 (m)", 0, 1000, 300, 50)

# ------------------ 지도 생성 ------------------
m = folium.Map(location=st.session_state.map_center, zoom_start=14, control_scale=True)
vworld_tile_url = f"http://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png"
folium.TileLayer(
    tiles=vworld_tile_url,
    attr="VWorld",
    name="VWorld Base Map",
    overlay=False,
    control=True,
).add_to(m)
m.add_child(folium.LatLngPopup())

# 지도 출력 및 좌표 클릭 수신
map_data = st_folium(m, width=900, height=600)
if map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lng = map_data["last_clicked"]["lng"]
    st.session_state.last_clicked = [lat, lng]
    st.success(f"🖱️ 클릭된 위치: 위도 {lat:.5f}, 경도 {lng:.5f}")

# ------------------ LURIS API ------------------
def query_luris(lat, lng):
    base_url = "https://apis.data.go.kr/1611000/nsdi/LandUseZoningService/attr/getLandUseZoningAttr"
    service_key = "YOUR_LURIS_API_KEY_HERE"  # 여기에 실제 키 입력
    params = {
        "serviceKey": service_key,
        "format": "json",
        "crs": "EPSG:4326",
        "geom": f"{lng},{lat}"
    }
    try:
        res = requests.get(base_url, params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}

# ------------------ 클릭 후 필터 분석 ------------------
if st.session_state.last_clicked:
    lat, lng = st.session_state.last_clicked
    result = query_luris(lat, lng)

    if "error" in result:
        st.error(f"LURIS 오류: {result['error']}")
    else:
        field = result.get("landUseZoningAttrs", {}).get("field", {})
        use_zone = field.get("luse", "알 수 없음")
        st.subheader("📋 LURIS 용도지역 분석")
        st.write(f"**용도지역:** {use_zone}")

        # 지도에 필터 시각화 적용
        if use_zone in zone_filter:
            folium.Marker(
                location=[lat, lng],
                popup=f"✅ 허용 지역: {use_zone}",
                icon=folium.Icon(color="green"),
            ).add_to(m)
        else:
            folium.Circle(
                location=[lat, lng],
                radius=80,
                color="gray",
                fill=True,
                fill_color="gray",
                fill_opacity=0.5,
                tooltip="❌ 필터 미충족 (회색 셰이드)",
            ).add_to(m)

        # 지도 다시 출력
        st_folium(m, width=900, height=600, key="filtered_map")
