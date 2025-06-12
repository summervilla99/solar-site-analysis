from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def get_capacity_from_kepco(serial_number="9185W431"):
    if len(serial_number) != 8:
        return {"status": "error", "message": "전산화번호는 8자리여야 합니다. (예: 9185W431)"}

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        url = "https://online.kepco.co.kr/EWM090D00"
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "mf_wfm_layout_inp_trpoleNo01"))
        )

        # 1. 전산화번호 입력
        for i, digit in enumerate(serial_number):
            input_id = f"mf_wfm_layout_inp_trpoleNo0{i+1}"
            elem = driver.find_element(By.ID, input_id)
            elem.clear()
            elem.send_keys(digit)

        # 1. 검색 버튼 클릭
        driver.find_element(By.ID, "mf_wfm_layout_btn_search").click()

        # 2. 상세보기 버튼 클릭 가능한 상태까지 대기
        detail_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "mf_wfm_layout_anc_detail"))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", detail_btn)
        driver.execute_script("arguments[0].click();", detail_btn)
        time.sleep(1)

        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "mf_wfm_layout_txt_aremain"))
        )

        # remain_data = {
        #     "A": driver.find_element(By.ID, "mf_wfm_layout_txt_aremain").text.strip(),
        #     "B": driver.find_element(By.ID, "mf_wfm_layout_txt_bremain").text.strip(),
        #     "C": driver.find_element(By.ID, "mf_wfm_layout_txt_cremain").text.strip(),
        # }

        # ✅ 간단하게 모든 _remain 요소를 찾고, 상 이름을 추출
        # 1. 텍스트 추출
        texts = [div.text.strip() for div in driver.find_elements(By.CLASS_NAME, "w2textbox") if div.text.strip()]
        print("📋 전체 추출된 텍스트:", texts)

        # 2. A상/B상 형태를 기준으로 값 매칭
        remain_data = {}
        for i in range(len(texts) - 1):
            if texts[i].endswith("상") and len(texts[i]) == 2 and texts[i][0].isalpha():
                remain_data[texts[i]] = texts[i + 1]

        if all(not v for v in remain_data.values()):
            raise ValueError("여유용량 텍스트 없음")
        
 
        return {"status": "success", 
                "serial_number": serial_number,
                "remain_data": remain_data}
        
    except Exception as e:
        print("예외 발생:", e)
        return {"status": "error", "message": "여유용량 없음 또는 파싱 실패"}