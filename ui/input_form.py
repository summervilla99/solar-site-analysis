import streamlit as st

def show():
    with st.form("site_form"):
        transformer_id = st.text_input("전산화번호 (예: 9185W431)")
        submitted = st.form_submit_button("조회 시작")
        if submitted:
            return {"transformer_id": transformer_id}
    return None