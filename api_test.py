import requests
import json

VWORLD_KEY = "98285DC0-D0EE-3E78-A4AA-FE8DABAF045A"  # ← 당신의 API 키

# ✔️ 테스트 위치 (서울시청 근처)
lat = 37.5665
lng = 126.9780
buffer = 0.001  # 약 100m 반경

# ✔️ bbox (minX, minY, maxX, maxY, EPSG:4326)
bbox = f"{lng-buffer},{lat-buffer},{lng+buffer},{lat+buffer},EPSG:4326"

# ✔️ API 요청 구성
url = "https://api.vworld.kr/req/wfs"
params = {
    "service": "WFS",
    "version": "2.0.0",
    "request": "GetFeature",
    "typename": "lt_cad_dg",
    "bbox": bbox,
    "output": "json",
    "key": VWORLD_KEY
}

# ✔️ API 요청 및 응답 확인
res = requests.get(url, params=params)
print("응답 코드:", res.status_code)

try:
    data = res.json()
    features = data.get("features", [])
    print(f"필지 개수: {len(features)}")

    # ✔️ 샘플 3개 출력
    for f in features[:3]:
        props = f.get("properties", {})
        print(f"주소: {props.get('juso')}, 지목: {props.get('jimok')}")
except Exception as e:
    print("JSON 파싱 오류:", e)
