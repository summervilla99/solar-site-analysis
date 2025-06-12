import streamlit as st

def show():
    with st.form("site_form"):
        transformer_id = st.text_input("변압기번호")
        address = st.text_input("주소")
        registry_file = st.file_uploader("등기부등본 PDF")
        submitted = st.form_submit_button("분석 시작")
        if submitted:
            return {
                "transformer_id": transformer_id,
                "address": address,
                "registry_file": registry_file
            }
    return None