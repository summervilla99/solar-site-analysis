import streamlit as st
import folium
import psycopg2
import json
import re
from streamlit_folium import st_folium
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT, VWORLD_KEY

# 기본 설정
DEFAULT_CENTER = [36.9910, 127.9260]  # 충주시 중심 좌표
ALL_DISALLOWED_JIMOK = ["전", "답", "과", "염전", "임야", "양어장"]

# 세션 상태 초기화
if 'map_center' not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if 'search_coords' not in st.session_state:
    st.session_state.search_coords = None
if 'search_triggered' not in st.session_state:
    st.session_state.search_triggered = False
if 'filtered_data' not in st.session_state:
    st.session_state.filtered_data = None

st.title("\u2600\ufe0f Solar Site Analysis (DB 기반 지목 필터링)")
selected_disallowed = st.sidebar.multiselect("🛑 태양광 불가 지목 선택", ALL_DISALLOWED_JIMOK, default=ALL_DISALLOWED_JIMOK)

# 주소 입력 및 검색
with st.form("search_form"):
    addr = st.text_input("📍 주소 입력", key="address_input")
    submitted = st.form_submit_button("🔍 검색")

# 주소 → 좌표 변환
def geocode_address(addr):
    import requests
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
                return [float(point["y"]), float(point["x"])]
        except:
            continue
    return None

# 지목 추출 함수
def extract_jimok(jibun_value):
    if jibun_value:
        match = re.search(r'([가-힣]{1,3})$', jibun_value.strip())
        if match:
            return match.group(1)
    return ""

# DB 쿼리 함수 (데이터만 반환)
def query_features(lat, lng):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()

        sql = f"""
            SELECT jibun, pnu, ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geometry
            FROM solar_analysis.land_parcels
            WHERE ST_DWithin(
                geom,
                ST_Transform(ST_SetSRID(ST_Point({lng}, {lat}), 4326), 5181),
                1500
            )
            AND jibun IS NOT NULL
        """

        cur.execute(sql)
        rows = cur.fetchall()

        cur.close()
        conn.close()

        return rows

    except Exception as e:
        st.error(f"❌ 데이터베이스 연결 실패: {e}")
        return []

# 검색 처리 (자동 실행)
if not st.session_state.search_triggered:
    st.session_state.search_coords = DEFAULT_CENTER
    st.session_state.map_center = DEFAULT_CENTER
    st.session_state.filtered_data = query_features(DEFAULT_CENTER[0], DEFAULT_CENTER[1])
    st.session_state.search_triggered = True

if submitted and addr:
    coords = geocode_address(addr)
    if coords:
        st.session_state.map_center = coords
        st.session_state.search_coords = coords
        st.session_state.filtered_data = query_features(coords[0], coords[1])
        st.success(f"📍 좌표: {coords[0]:.6f}, {coords[1]:.6f}")
    else:
        st.error("❌ 주소 좌표 변환 실패")

map_center = st.session_state.search_coords if st.session_state.search_coords else st.session_state.map_center

# 지도 초기화
m = folium.Map(location=map_center, zoom_start=15)

# 지도에 폴리곤 추가 (검색 유무 관계 없이 항상 실행)
if st.session_state.filtered_data:
    for row in st.session_state.filtered_data:
        jibun, pnu, geojson = row
        jimok = extract_jimok(jibun)

        tooltip_text = f"{jibun}\nPNU: {pnu}"

        geometry = json.loads(geojson)
        coords = geometry['coordinates'][0][0]
        polygon = [[lat, lon] for lon, lat in coords]

        if jimok in selected_disallowed:
            folium.Polygon(
                locations=polygon,
                color="red",
                weight=3,
                fill=True,
                fill_color="#cccccc",
                fill_opacity=0.4,
                tooltip=f"❌ {tooltip_text}"
            ).add_to(m)
        else:
            folium.Polygon(
                locations=polygon,
                color="green",
                weight=2,
                fill=True,
                fill_color="#A8E6A3",
                fill_opacity=0.3,
                tooltip=f"✅ {tooltip_text}"
            ).add_to(m)

st_folium(m, width=1000, height=600)

if st.session_state.filtered_data:
    st.info("✅ 주소 검색과 DB 기반 지목 필터링이 적용된 지도입니다.")
else:
    st.info("🔍 좌측에서 주소를 검색하면 필터링된 지도를 볼 수 있습니다.")
