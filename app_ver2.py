import streamlit as st
import folium
import psycopg2
import json
import re
import time
from streamlit_folium import st_folium
from pyproj import Transformer
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT, VWORLD_KEY

DEFAULT_CENTER = [37.8740, 127.9460]
ALL_DISALLOWED_JIMOK = ["전", "답", "과", "염전", "임야", "양어장"]

if 'map_center' not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if 'search_coords' not in st.session_state:
    st.session_state.search_coords = None
if 'search_triggered' not in st.session_state:
    st.session_state.search_triggered = False
if 'filtered_data' not in st.session_state:
    st.session_state.filtered_data = None

st.title("☀️ Solar Site Analysis (DB 기반 지목 필터링)")
selected_disallowed = st.sidebar.multiselect("🛑 태양광 불가 지목 선택", ALL_DISALLOWED_JIMOK, default=ALL_DISALLOWED_JIMOK)

with st.form("search_form"):
    addr = st.text_input("📍 주소 입력", key="address_input")
    submitted = st.form_submit_button("🔍 검색")

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
                coords = [float(point["y"]), float(point["x"])]
                print(f"[DEBUG] 변환된 좌표: {coords}")
                return coords
        except Exception as e:
            print(f"[DEBUG] 주소 변환 실패: {e}")
            continue
    return None

def extract_jimok(jibun_value):
    if jibun_value:
        match = re.search(r'([가-힣]{1,3})$', jibun_value.strip())
        if match:
            return match.group(1)
    return ""

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
            FROM filter.land_category
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
        print(f"[DB ERROR] {e}")
        st.error(f"❌ 데이터베이스 연결 실패: {e}")
        return []

# 최초 로딩이거나 검색 전일 때 → 디폴트 필지 한 번만 불러오기
if not st.session_state.filtered_data:
    st.session_state.search_coords = DEFAULT_CENTER
    st.session_state.map_center = DEFAULT_CENTER
    st.session_state.filtered_data = query_features(DEFAULT_CENTER[0], DEFAULT_CENTER[1])

if 'drawn' not in st.session_state:
    st.session_state.drawn = False

if submitted and addr:
    coords = geocode_address(addr)
    if coords:
        lat, lng = coords
        st.session_state.map_center = coords[1], coords[0]
        st.session_state.search_coords = coords
        st.session_state.filtered_data = query_features(lat, lng)
        st.session_state.search_triggered = True
        st.success(f"📍 좌표: {lat:.6f}, {lng:.6f}")
    else:
        st.error("❌ 주소 좌표 변환 실패")


map_center = st.session_state.search_coords if st.session_state.search_coords else st.session_state.map_center
m = folium.Map(location=map_center, zoom_start=15)

if st.session_state.filtered_data:
    with st.spinner("🔍 지도를 분석 중입니다. 필지 시각화까지 수 초 걸릴 수 있습니다..."):
        start = time.time()
        for row in st.session_state.filtered_data:
            jibun, pnu, geojson = row
            jimok = extract_jimok(jibun)
            tooltip_text = f"{jibun}\nPNU: {pnu}"

            try:
                geometry = json.loads(geojson)
                geom_type = geometry.get("type")
                if geom_type == "Polygon":
                    polygons = [geometry["coordinates"]]
                elif geom_type == "MultiPolygon":
                    polygons = geometry["coordinates"]
                else:
                    continue

                for poly in polygons:
                    outer_ring = poly[0]
                    polygon = [[lat, lon] for lon, lat in outer_ring]
                    folium.Polygon(
                        locations=polygon,
                        color="red" if jimok in selected_disallowed else "green",
                        weight=3 if jimok in selected_disallowed else 2,
                        fill=True,
                        fill_color="#cccccc" if jimok in selected_disallowed else "#A8E6A3",
                        fill_opacity=0.4 if jimok in selected_disallowed else 0.3,
                        tooltip=f"{'❌' if jimok in selected_disallowed else '✅'} {tooltip_text}"
                    ).add_to(m)
            except Exception as e:
                st.warning(f"❗ 지오메트리 파싱 실패: {e}")
        end = time.time()
        print(f"[렌더링 시간] {end - start:.2f}초")

st_folium(m, width=1000, height=600)

if st.session_state.filtered_data:
    st.info("✅ 주소 기반 필지가 시각화되었습니다.")
else:
    st.info("🔍 주소를 검색하면 주변 필지를 확인할 수 있습니다.")
