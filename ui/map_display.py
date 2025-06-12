import streamlit as st

def show(df):
    st.map(df.rename(columns={"lat": "latitude", "lon": "longitude"}), zoom=12)