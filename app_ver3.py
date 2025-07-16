import streamlit as st
import folium
import psycopg2
import json
import re
from streamlit_folium import st_folium
from pyproj import Transformer
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT, VWORLD_KEY
from itertools import islice

# 기본 설정
DEFAULT_CENTER = [37.8740, 127.9460]  # 충주시 중심 좌표
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

def chunk(iterable, size):
    it = iter(iterable)
    return iter(lambda: list(islice(it, size)), [])

# 데이터 참조 속도 향상
def convert_to_5181(lat, lng):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5181", always_xy=True)
    x, y = transformer.transform(lng, lat)
    return x, y
# DB 쿼리 함수
def query_features(lat, lng):
    print(f"[DB QUERY] 요청 좌표: lat={lat}, lng={lng}")

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        print("[DB CONNECT] 연결 성공")

        cur = conn.cursor()

        x5181, y5181 = convert_to_5181(lat, lng)

        sql = f"""
            SELECT jibun, pnu, ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geometry
            FROM filter.land_category
            WHERE ST_DWithin(
                geom,
                ST_SetSRID(ST_MakePoint({x5181}, {y5181}), 5181),
                1500
            )
            AND jibun IS NOT NULL
        """


        print("[DB QUERY] 실행 중...")
        cur.execute(sql)
        rows = cur.fetchall()
        print(f"[DB RESULT] 행 개수: {len(rows)}")

        cur.close()
        conn.close()

        return rows

    except Exception as e:
        print(f"[DB ERROR] {e}")
        st.error(f"❌ 데이터베이스 연결 실패: {e}")
        return []


# 검색 처리
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

if not (33 <= map_center[0] <= 39 and 124 <= map_center[1] <= 132):
    print(f"[경고] 잘못된 중심 좌표: {map_center} → DEFAULT_CENTER로 되돌립니다.")
    map_center = DEFAULT_CENTER

# 지도 생성
m = folium.Map(location=map_center, zoom_start=15)

# (1) 폴리곤 먼저 그리기
if st.session_state.filtered_data:

    def feature_in_bounds(geojson_str, bounds):
        try:
            geom = json.loads(geojson_str)
            if geom["type"] == "Polygon":
                polygons = [geom["coordinates"]]
            elif geom["type"] == "MultiPolygon":
                polygons = geom["coordinates"]
            else:
                return False

            for poly in polygons:
                for coord in poly[0]:  # 외곽선
                    lon, lat = coord
                    if bounds and (bounds["south"] <= lat <= bounds["north"]) and (bounds["west"] <= lon <= bounds["east"]):
                        return True
            return False
        except:
            return False

    # 임시 bounds 초기화
    current_bounds = {"north": 90, "south": -90, "east": 180, "west": -180}  # 전 영역

    chunks = chunk(st.session_state.filtered_data, 200)
    for chunk_group in chunks:
        for row in chunk_group:
            jibun, pnu, geojson = row
            jimok = extract_jimok(jibun)
            tooltip_text = f"{jibun}\nPNU: {pnu}"

            if not feature_in_bounds(geojson, current_bounds):
                continue

            try:
                geometry = json.loads(geojson)
                geom_type = geometry.get("type")
                polygons = [geometry["coordinates"]] if geom_type == "Polygon" else geometry["coordinates"]

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
                print(f"[지오메트리 파싱 실패] {e}")

# (2) 마지막에 한 번만 지도 출력
map_result = st_folium(m, width=1000, height=600)

# (3) 지도 bounds 정보 출력 (선택)
if "bounds" in map_result:
    bounds = map_result["bounds"]
    print(f"[지도 bounds] {bounds}")


if st.session_state.filtered_data:
    st.info("✅ 주소 검색과 DB 기반 지목 필터링이 적용된 지도입니다.")
else:
    st.info("🔍 좌측에서 주소를 검색하면 필터링된 지도를 볼 수 있습니다.")
