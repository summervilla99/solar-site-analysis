import streamlit as st
from modules import keonon_rpa, geo_utils, luris_api, registry_parser, data_aggregator
from ui import input_form, map_display

st.set_page_config(page_title="태양광 입지 분석기", layout="wide")
st.title("☀️ 태양광 입지 자동 분석 도구")

site_info = input_form.show()
if site_info:
    with st.spinner("여유 용량 조회 중..."):
        capacity_data = keonon_rpa.get_capacity(site_info["transformer_id"])

    luris_data = luris_api.query_luris(site_info["address"])
    legal_summary = registry_parser.parse_pdf(site_info["registry_file"])

    site_summary = data_aggregator.aggregate(site_info, capacity_data, luris_data, legal_summary)
    st.success("분석 완료!")

    map_display.show(site_summary)
    st.dataframe(site_summary)