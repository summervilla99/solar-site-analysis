import streamlit as st
import requests
import folium
import xml.etree.ElementTree as ET
import re
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
        coords_text = member.find(".//gml:coordinates", namespace)
        polygon = []
        if coords_text is not None:
            coord_pairs = coords_text.text.strip().split(" ")
            for pair in coord_pairs:
                x, y = map(float, pair.split(","))
                polygon.append([y, x])

        jibun_jimok_text = member.find(".//lnm_lndcgr_smbol")
        jibun_jimok = jibun_jimok_text.text if jibun_jimok_text is not None else ""

        pnu_text = member.find(".//pnu")
        pnu = pnu_text.text if pnu_text is not None else ""

        issue_code_text = member.find(".//issu_confm_code")
        issue_code = issue_code_text.text if issue_code_text is not None else ""

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
    buffer_km = 1.0  # ← 원하는 반경 km
    buffer_deg = buffer_km / 111  # 위도 기준 1도 = 약 111km
    bbox = f"{lat - buffer_deg},{lng - buffer_deg},{lat + buffer_deg},{lng + buffer_deg},EPSG:4326"


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

        # 우선 UTF-8 시도
        try:
            xml_text = res.content.decode('utf-8')
        except UnicodeDecodeError:
            xml_text = res.content.decode('euc-kr', errors='replace')

        print("\n[DEBUG] 응답 일부 (디코딩 완료):")
        print(xml_text[:1000])

        st.text_area("📄 API 응답 (디코딩)", xml_text, height=200)

        if res.status_code == 200 and "<ServiceException" not in xml_text:
            return parse_gml_features(xml_text)
        else:
            st.warning("❌ 지적도 데이터 없음 또는 오류")
            return []

    except Exception as e:
        print(f"[DEBUG] API 호출 실패: {e}")
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

if addr:
    coords = geocode_address(addr)
    if coords:
        st.session_state.map_center = coords
        st.session_state.search_coords = coords
        st.success(f"📍 주소 → 좌표: {coords[0]:.6f}, {coords[1]:.6f}")
    else:
        st.error("❌ 주소 변환 실패")

# ---------------- 지도 생성 ----------------
m = folium.Map(location=st.session_state.map_center, zoom_start=15)
tile_url = f"http://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png"
folium.TileLayer(tiles=tile_url, attr="VWorld").add_to(m)

features = []
if st.session_state.search_coords:
    lat, lng = st.session_state.search_coords
    features = fetch_cadastral_from_vworld(lat, lng)

    for feature in features:
        jimok = feature['jimok']
        jibun = feature['jibun']
        polygon = feature['polygon']
        pnu = feature.get('pnu', '')

        tooltip_text = f"{jibun} - {jimok}\nPNU: {pnu}"

        if jimok in selected_disallowed:
            # ❌ 설치 불가 → 회색 폴리곤 + 빨간 테두리 + 네모 박스 추가
            folium.Polygon(
                locations=polygon,
                color="red",             # 두꺼운 빨간 테두리
                weight=3,
                fill=True,
                fill_color="#cccccc",    # 회색 채움
                fill_opacity=0.4,
                tooltip=f"❌ {tooltip_text}"
            ).add_to(m)

            # ➕ 바운딩 박스 네모 추가 (더 눈에 띄게)
            lats = [pt[0] for pt in polygon]
            lngs = [pt[1] for pt in polygon]
            bbox_polygon = [
                [min(lats), min(lngs)],
                [max(lats), min(lngs)],
                [max(lats), max(lngs)],
                [min(lats), max(lngs)],
                [min(lats), min(lngs)],
            ]
            folium.PolyLine(
                locations=bbox_polygon,
                color="red",
                weight=2,
                dash_array="5,5",
                tooltip="🚫 설치 불가 영역 (Bounding Box)"
            ).add_to(m)

        else:
            # ✅ 설치 가능 → 초록 테두리 + 연두 채움
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

st.info("✅ 지도 클릭 없이도 좌표 검색 → WFS 호출 → 터미널 + UI에 디버깅이 바로 나옵니다.")
