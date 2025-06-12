import pandas as pd

def aggregate(site_info, capacity_data, luris_data, legal_summary):
    return pd.DataFrame([{
        "site_id": "S001",
        "변압기번호": capacity_data["transformer_id"],
        "여유용량": capacity_data["capacity"],
        "용도지역": luris_data["용도지역"],
        "지목": luris_data["지목"],
        "이격거리": "YES",
        "권리사항": legal_summary["저당권"],
        "최종평가": "적합"
    }])