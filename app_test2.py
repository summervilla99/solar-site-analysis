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

# ---------------- 지번+지목 추출 함수 ----------------
def extract_jibun_and_jimok(jibun_jimok_raw):
    jibun_jimok = jibun_jimok_raw.strip() if jibun_jimok_raw else ""

    parts = jibun_jimok.split()
    if len(parts) >= 2:
        jibun = parts[0].strip()
        jimok = parts[1].strip()
        return jibun, jimok

    match = re.match(r"([\d\-가-힣]+?)([가-힣]{1,3})$", jibun_jimok)
    if match:
        jibun = match.group(1).strip()
        jimok = match.group(2).strip()
        return jibun, jimok

    return jibun_jimok, ""

# ---------------- GML 파싱 함수 ----------------
def parse_gml_features(xml_text):
    namespace = {'gml': 'http://www.opengis.net/gml', 'sop': 'https://www.vworld.kr'}
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

        jibun_jimok_text = member.find(".//sop:lnm_lndcgr_smbol", namespace)
        jibun_jimok_raw = jibun_jimok_text.text if jibun_jimok_text is not None else ""

        jibun, jimok = extract_jibun_and_jimok(jibun_jimok_raw)

        pnu_text = member.find(".//sop:pnu", namespace)
        pnu = pnu_text.text if pnu_text is not None else ""

        features.append({
            'polygon': polygon,
            'jibun': jibun,
            'jimok': jimok,
            'pnu': pnu
        })

    return features

# ---------------- WFS API 호출 ----------------
def fetch_cadastral_from_vworld(lat, lng, buffer_km=1.0):
    buffer_deg = buffer_km / 111.0
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
        xml_text = res.content.decode('utf-8', errors='replace')

        print("[DEBUG] 호출 URL:", res.url)
        print("[DEBUG] 응답 코드:", res.status_code)

        st.text_area("📄 API 응답", xml_text, height=200)

        if res.status_code == 200 and "<ServiceException" not in xml_text:
            return parse_gml_features(xml_text)
        else:
            st.warning("❌ 지적도 데이터 없음 또는 오류")
            return []

    except Exception as e:
        print(f"[DEBUG] API 호출 실패: {e}")
        st.error(f"API 호출 실패: {e}")
        return []

# ---------------- Streamlit 앱 ----------------
if 'map_center' not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if 'search_coords' not in st.session_state:
    st.session_state.search_coords = None

st.title("☀️ Solar Site Analysis")
selected_disallowed = st.sidebar.multiselect("🛑 태양광 불가 지목 선택", ALL_DISALLOWED_JIMOK, default=ALL_DISALLOWED_JIMOK)

addr = st.text_input("📍 주소 입력")

# 주소 → 좌표 변환
if addr:
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
                    return [float(point["y"]), float(point["x"])]
            except:
                continue
        return None

    coords = geocode_address(addr)
    if coords:
        st.session_state.map_center = coords
        st.session_state.search_coords = coords
        st.success(f"📍 좌표: {coords[0]:.6f}, {coords[1]:.6f}")
    else:
        st.error("❌ 주소 좌표 변환 실패")

# 지도 생성
m = folium.Map(location=st.session_state.map_center, zoom_start=15)
folium.TileLayer(tiles=f"http://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png", attr="VWorld").add_to(m)

features = []
if st.session_state.search_coords:
    lat, lng = st.session_state.search_coords
    features = fetch_cadastral_from_vworld(lat, lng, buffer_km=1.0)

    for feature in features:
        jimok = feature['jimok']
        jibun = feature['jibun']
        polygon = feature['polygon']
        pnu = feature.get('pnu', '')

        tooltip_text = f"{jibun} - {jimok}\nPNU: {pnu}"

        if not polygon:
            continue

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
                tooltip="🚫 설치 불가 영역"
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

st.info("✅ 1km 반경 내 지목 필터링 및 시각화 완료. 불가 지역은 빨간색, 가능 지역은 초록색으로 표시됩니다.")
