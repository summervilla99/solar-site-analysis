import streamlit as st
from modules import keonon_rpa
# geo_utils, luris_api, registry_parser, data_aggregator
from ui import input_form
# map_display

st.set_page_config(page_title="태양광 입지 분석기", layout="wide")
st.title("☀️ 태양광 입지 분석기 - Step 1: 여유용량 조회")

site_info = input_form.show()

if site_info:
    with st.spinner("한전ON에서 여유용량을 조회 중입니다..."):
        result = keonon_rpa.get_capacity_from_kepco(site_info["transformer_id"])

    if result["status"] == "success":
        st.success("조회 성공!")
        st.write(f"**전산화번호**: {result['serial_number']}")
        st.write("**여유용량**:")
        st.json(result["remain_data"])
    else:
        st.error(f"조회 실패: {result['message']}")