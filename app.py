import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import requests
import pandas as pd
from modules import keonon_rpa  # Step 1에서 RPA 기능 사용

st.set_page_config(page_title="태양광 입지 분석기", layout="wide")

# 사이드바에서 Step 선택
step = st.sidebar.radio("📌 분석 단계 선택", ["Step 1: 여유용량 조회", "Step 2: LURIS 분석"])

# 데이터 저장용 리스트 초기화
if "history" not in st.session_state:
    st.session_state["history"] = []

# -------------------- STEP 1 --------------------
if step == "Step 1: 여유용량 조회":
    st.title("🔌 Step 1: 한전ON 여유용량 조회")
    serial_number = st.text_input("전산화번호 (예: 9185W431)", max_chars=8)

    if st.button("여유용량 조회"):
        result = keonon_rpa.get_capacity_from_kepco(serial_number)

        if result["status"] == "success":
            st.success("✅ 조회 성공")
            st.write(f"**전산화번호**: {result['serial_number']}")
            st.write("**여유용량 (상별)**")
            st.json(result["remain_data"])

            # ✅ 세션 상태에 저장
            st.session_state["serial_number"] = result["serial_number"]
            st.session_state["remain_data"] = result["remain_data"]

            # ✅ 히스토리 저장
            row = {"serial_number": result["serial_number"]}
            row.update(result["remain_data"])
            st.session_state["history"].append(row)
        else:
            st.error(f"조회 실패: {result['message']}")

    # ✅ 저장된 히스토리 확인만 (다운로드 버튼 제거)
    if st.session_state["history"]:
        st.subheader("📄 누적 조회 결과")
        df = pd.DataFrame(st.session_state["history"])
        st.dataframe(df)

# -------------------- STEP 2 --------------------
elif step == "Step 2: LURIS 분석":
    st.title("🗺️ Step 2: 지도에서 위치 클릭 → LURIS 용도지역 조회")

    # 이전 Step 1 데이터 있으면 표시
    if "serial_number" in st.session_state:
        st.info(f"이전 조회 전산화번호: {st.session_state['serial_number']}")
        st.write("이전 여유용량:")
        st.json(st.session_state["remain_data"])

    # KakaoMap 지도 불러오기
    with open("ui/kakao_map.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    st.components.v1.html(html_code, height=550)

    # JS에서 클릭된 좌표 가져오기
    coords = streamlit_js_eval(js_expressions="window._clickedCoords", key="coords")
    if coords:
        st.success("✅ 클릭된 좌표 수신 완료")
        st.write(f"위도: {coords['lat']}, 경도: {coords['lng']}")

        # LURIS API 요청 함수
        def query_luris(lat, lng):
            try:
                base_url = "https://apis.data.go.kr/1611000/nsdi/LandUseZoningService/attr/getLandUseZoningAttr"
                service_key = "YOUR_LURIS_API_KEY_HERE"  # 여기에 본인 API 키 입력
                params = {
                    "serviceKey": service_key,
                    "format": "json",
                    "crs": "EPSG:4326",
                    "geom": f"{lng},{lat}"
                }
                res = requests.get(base_url, params=params)
                res.raise_for_status()
                return res.json()
            except Exception as e:
                return {"error": str(e)}

        result = query_luris(coords['lat'], coords['lng'])

        if "error" in result:
            st.error(f"🚫 LURIS 요청 실패: {result['error']}")
        else:
            st.subheader("🏙️ 용도지역 / 지목 정보")
            st.json(result)
