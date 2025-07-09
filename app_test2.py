import streamlit as st
import requests
import folium
import xml.etree.ElementTree as ET
from streamlit_folium import st_folium
from config import VWORLD_KEY

# ---------------- 기본 설정 ----------------
DEFAULT_CENTER = [37.5665, 126.9780]
ALL_DISALLOWED_JIMOK = ["전", "답", "과", "염전", "임야", "양어장"]

# ---------------- GML 파싱 함수 ----------------
def parse_gml_features(xml_text):
    namespace = {'gml': 'http://www.opengis.net/gml'}
    tree = ET.ElementTree(ET.fromstring(xml_text))
    root = tree.getroot()

    features = []

    for member in root.findall(".//gml:featureMember", namespace):
        props = {}

        # Extract geometry (coordinates)
        coords_text = member.find(".//gml:coordinates", namespace)
        if coords_text is not None:
            coord_pairs = coords_text.text.strip().split(" ")
            polygon = []
            for pair in coord_pairs:
                x, y = map(float, pair.split(","))
                polygon.append([y, x])  # folium 순서
            
        # Extract attributes (lnm_lndcgr_smbol: 지번+지목)
        jibun_jimok_text = member.find(".//lnm_lndcgr_smbol")
        jibun_jimok = jibun_jimok_text.text if jibun_jimok_text is not None else ""

        # Extract PNU (optional)
        pnu_text = member.find(".//pnu")
        pnu = pnu_text.text if pnu_text is not None else ""

        # Extract issuance code (optional)
        issue_code_text = member.find(".//issu_confm_code")
        issue_code = issue_code_text.text if issue_code_text is not None else ""

        # Extract only 지목 (지번과 분리)
        if jibun_jimok:
            jibun = ''.join(filter(lambda c: not ('\uAC00' <= c <= '\uD7A3'), jibun_jimok)).strip()
            jimok = ''.join(filter(lambda c: ('\uAC00' <= c <= '\uD7A3'), jibun_jimok)).strip()
        else:
            jibun = ""
            jimok = ""

        features.append({
            'polygon': polygon,
            'jibun': jibun,
            'jimok': jimok,
            'pnu': pnu,
            'issue_code': issue_code
        })

    return features

# ---------------- WFS API 호출 ----------------
def fetch_cadastral_from_vworld(lat, lng):
    buffer = 0.001
    bbox = f"{lat - buffer},{lng - buffer},{lat + buffer},{lng + buffer},EPSG:4326"

    params = {
        "key": VWORLD_KEY,
        "typename": "dt_d002",
        "bbox": bbox,
        "maxFeatures": "50",
        "resultType": "results",
        "srsName": "EPSG:4326",
        "output": "text/xml; subtype=gml/2.1.2"
    }

    try:
        res = requests.get("https://api.vworld.kr/ned/wfs/getCtnlgsSpceWFS", params=params, timeout=10)

        print("👉 호출 URL:", res.url)
        print("👉 응답 코드:", res.status_code)
        print("👉 응답 내용:", res.text[:1000])  # 최대 1000자 잘라서 출력

        st.text_area("📜 서버 응답 요약", res.text[:1000], height=200)

        if res.status_code == 200 and "<ServiceException" not in res.text:
            return parse_gml_features(res.text)
        else:
            st.warning("❌ 지적도 데이터 없음 or 호출 오류")
            return []
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        return []


    
    

# ---------------- 세션 초기화 ----------------
if 'map_center' not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if 'search_coords' not in st.session_state:
    st.session_state.search_coords = None

# ---------------- UI ----------------
st.title("☀️ Solar Site Analysis")

selected_disallowed = st.sidebar.multiselect("🛑 태양광 불가 지목 선택", ALL_DISALLOWED_JIMOK, default=ALL_DISALLOWED_JIMOK)

addr = st.text_input("📍 주소 입력")

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

if addr and not st.session_state.search_coords:
    coords = geocode_address(addr)  # ✅ 함수 그대로 사용
    if coords:
        st.session_state.map_center = coords
        st.session_state.search_coords = coords
        st.success(f"📍 좌표 변환 성공: 위도 {coords[0]:.6f}, 경도 {coords[1]:.6f}")
    else:
        st.error("❌ 주소 좌표를 찾을 수 없습니다.")

if st.session_state.get('search_triggered', False):
    lat, lng = st.session_state.search_coords
    features = fetch_cadastral_from_vworld(lat, lng)

# ---------------- 지도 생성 ----------------
m = folium.Map(location=st.session_state.map_center, zoom_start=15)
tile_url = f"http://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png"
folium.TileLayer(tiles=tile_url, attr="VWorld").add_to(m)
# ---------------- 데이터 호출 및 필터링 ----------------
if st.session_state.search_coords:
    lat, lng = st.session_state.search_coords
    features = fetch_cadastral_from_vworld(lat, lng)

    for feature in features:
        jimok = feature['jimok']  # ✅ 지목 정보 추출
        jibun = feature['jibun']  # ✅ 지번 정보 추출
        polygon = feature['polygon']  # ✅ 폴리곤 추출

        # ✅ 필터 조건: 선택된 불가 지목이면 회색으로 표시
        if jimok in selected_disallowed:
            folium.Polygon(
                locations=polygon,
                color="gray",          # 테두리 색
                weight=1,              # 테두리 두께
                fill=True,             
                fill_color="gray",     # 채우기 색
                fill_opacity=0.5,      # 투명도
                tooltip=f"❌ {jibun} - {jimok} (설치 불가)"
            ).add_to(m)

# ---------------- 지도 출력 ----------------
st_folium(m, width=1000, height=600)

st.info("✅ 지목 정보는 VWorld 연속지적도에서 실시간 조회됩니다. CSV 없이 자동 갱신!")