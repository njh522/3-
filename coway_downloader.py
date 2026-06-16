# -*- coding: utf-8 -*-
import os
import time
import sys
import re
from datetime import datetime, timedelta

# 필수 라이브러리 자동 설치 안내 및 임포트
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("*" * 60)
    print(" [안내] selenium 라이브러리가 설치되어 있지 않습니다.")
    print(" 설치를 완료한 후 다시 실행합니다. (pip install selenium)")
    print("*" * 60)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium"])
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

def get_wednesdays(start_year=2023):
    """지정한 연도부터 오늘까지의 매주 수요일 날짜 리스트를 반환합니다."""
    start_date = datetime(start_year, 1, 1)
    end_date = datetime.now()
    
    current = start_date
    wednesdays = []
    while current <= end_date:
        if current.weekday() == 2:  # 수요일
            wednesdays.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return wednesdays

def init_driver(download_dir):
    """다운로드 경로가 설정된 크롬 드라이버를 초기화합니다."""
    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("detach", True)
    
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    return driver

def select_websquare_selectbox(driver, selectbox_label, target_value):
    """
    웹스퀘어(WebSquare) Selectbox 제어 함수.
    라벨(예: '선택')을 가진 요소를 찾아 클릭하고, 드롭다운 목록에서 대상 텍스트(예: '유구')를 클릭합니다.
    """
    # 1. 화면에 보이는 모든 selectbox 형태의 요소들 검색
    elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'w2selectbox') or contains(@class, 'w2select') or @type='select']")
    
    # 만약 위 xpath로 못 찾으면 일반 '선택' 텍스트를 가진 클릭 가능한 요소 검색
    if not elements:
        elements = [el for el in driver.find_elements(By.XPATH, "//*[text()='선택' or @value='선택']") if el.is_displayed()]
        
    print(f"   - selectbox 후보 {len(elements)}개 감지")
    
    # 플랜트는 대개 첫 번째 '선택' 박스이므로 순서대로 시도
    for idx, el in enumerate(elements):
        try:
            el.click()
            time.sleep(0.5)
            
            # 드롭다운 레이어에서 대상 텍스트(유구, 인천, 포천 등)를 클릭 시도
            # 웹스퀘어 드롭다운 아이템 클래스 패턴: .w2selectbox_div_item, .w2select_div_item 등
            option_elements = driver.find_elements(By.XPATH, f"//*[text()='{target_value}' or contains(text(), '{target_value}')]")
            for opt in option_elements:
                if opt.is_displayed():
                    opt.click()
                    print(f"   ✓ 플랜트 [{target_value}] 선택 성공 (후보 {idx+1}번 이용)")
                    time.sleep(0.5)
                    return True
            
            # 실패했다면 드롭다운을 닫기 위해 다시 클릭
            el.click()
        except Exception as e:
            # 에러 시 다음 후보 시도
            continue
            
    # 백업 방법: input 필드 직접 강제 입력 시도
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        try:
            val = inp.get_attribute("value")
            if val == "선택":
                inp.click()
                inp.send_keys(Keys.CONTROL + "a")
                inp.send_keys(Keys.BACKSPACE)
                inp.send_keys(target_value)
                inp.send_keys(Keys.ENTER)
                print(f"   ✓ 플랜트 [{target_value}] 강제 입력 시도 성공")
                return True
        except:
            continue
            
    return False

def find_date_input_and_format(driver):
    """
    화면 상에서 YYYY/MM/DD 또는 YYYY-MM-DD 등 날짜가 적혀 있는 인풋 요소를 검색하여
    해당 요소와 날짜 구분자(separator)를 리턴합니다.
    """
    date_pattern = re.compile(r"^\d{4}[-/.]\d{2}[-/.]\d{2}$")
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        try:
            if inp.is_displayed():
                val = inp.get_attribute("value")
                if val:
                    val_clean = val.strip()
                    if date_pattern.match(val_clean):
                        separator = "/" if "/" in val_clean else ("-" if "-" in val_clean else "")
                        print(f"   ✓ 날짜 입력창 발견! (현재값: {val_clean}, 구분자: '{separator}')")
                        return inp, separator
        except:
            continue
    return None, None

def find_clickable_by_text(driver, keywords):
    """
    화면에서 특정 텍스트를 포함하고 있고 클릭 가능한 div, span, a, button, input 요소를 찾습니다.
    """
    tags = ["button", "input", "a", "div", "span"]
    for tag in tags:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for el in elements:
            try:
                if el.is_displayed() and el.is_enabled():
                    txt = el.text.strip() if el.text else ""
                    val = el.get_attribute("value") if el.get_attribute("value") else ""
                    title = el.get_attribute("title") if el.get_attribute("title") else ""
                    onclick = el.get_attribute("onclick") if el.get_attribute("onclick") else ""
                    
                    combined = (txt + " " + val + " " + title + " " + onclick).lower()
                    
                    if any(kw.lower() in combined for kw in keywords):
                        if tag == "input" and el.get_attribute("type") in ["text", "password", "hidden"]:
                            continue
                        return el
            except:
                continue
    return None

def find_excel_download_icon_button(driver):
    """
    Results: 0 우측에 배치된 툴바 버튼 중 다운로드(아래 화살표) 아이콘을 찾아 클릭합니다.
    """
    # 웹스퀘어의 Grid excel 다운로드 버튼은 주로 클래스명에 grid_excel, btn_excel, xls 등을 포함하거나
    # title 속성에 '엑셀', 'excel', '다운로드'가 들어있습니다.
    excel_candidates = [
        "//*[contains(@title, '엑셀') or contains(@title, 'Excel') or contains(@title, '다운로드')]",
        "//*[contains(@class, 'excel') or contains(@class, 'xls') or contains(@class, 'down')]",
        "//a[contains(@class, 'btn') and contains(@class, 'excel')]"
    ]
    
    for xpath in excel_candidates:
        buttons = driver.find_elements(By.XPATH, xpath)
        for btn in buttons:
            try:
                if btn.is_displayed():
                    print(f"   ✓ 엑셀 다운로드 아이콘 버튼 발견! (Class: {btn.get_attribute('class')})")
                    return btn
            except:
                continue
                
    # 백업: 이미지나 텍스트가 없는 아래 화살표 모양의 아이콘 버튼 탐색
    # 일반적으로 웹스퀘어 엑셀 다운로드는 grid의 툴바 내부 세 번째 정도 버튼입니다.
    # title이나 class가 없어도 클릭 가능한 이미지/아이콘들을 가져와 다운로드 모양인지 추정합니다.
    all_icons = driver.find_elements(By.XPATH, "//a | //button | //div[contains(@class, 'btn')]")
    for el in all_icons:
        try:
            if el.is_displayed():
                cls = el.get_attribute("class")
                if cls and any(x in cls.lower() for x in ["download", "excel", "down"]):
                    return el
        except:
            continue
            
    return None

def run_download():
    # 저장 경로
    base_dir = os.path.dirname(os.path.abspath(__file__))
    download_dir = os.path.join(base_dir, "coway_download")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        
    print("=" * 60)
    print(" 코웨이 FCST 주별 데이터 자동 다운로드 매크로 (웹스퀘어5 최적화)")
    print(f" - 다운로드 경로: {download_dir}")
    print("=" * 60)
    
    print("\n1. 웹 브라우저를 실행합니다...")
    driver = init_driver(download_dir)
    
    # 코웨이 로그인 페이지 접속
    driver.get("https://buy.coway.do/afterLogin.do")
    
    print("\n[필독 - 수동 작업 필요]")
    print("1. 브라우저에서 '로그인'을 진행해 주세요.")
    print("2. 로그인 후, [생산계획] -> [3~12 F/C 주별] 메뉴로 이동해 주세요.")
    print("3. 이동을 마치셨다면, 아래에서 모드를 선택해 엔터(Enter)를 입력하세요.")
    print("-" * 60)
    
    mode = input("선택해주세요 (1: 테스트 모드 (1번만 다운로드), 2: 최근 3개년 전체 다운로드) [기본값: 1]: ").strip()
    if not mode:
        mode = "1"
        
    # 날짜 목록 가져오기 (2023년 ~ 현재 수요일)
    wednesdays = get_wednesdays(2023)
    if mode == "1":
        wednesdays = wednesdays[-1:]
        print(f"\n[테스트 모드 실행] 대상 날짜: {wednesdays[0]}")
    else:
        print(f"\n[전체 다운로드 실행] 총 {len(wednesdays)}개의 수요일 데이터를 다운로드합니다.")

    # 3개 플랜트 리스트
    plants = ["유구", "인천", "포천"]
    
    try:
        print("\n현재 화면에서 지능형 매칭 탐색 및 엑셀 다운로드 팝업 처리를 시작합니다...")
        
        for date_str in reversed(wednesdays): # 최근 날짜부터 역순으로 다운로드
            for plant in plants:
                print(f"\n▶ [{date_str}] - {plant} 플랜트 작업 시작...")
                
                # 1. 플랜트 선택 (웹스퀘어 selectbox 제어)
                success_plant = select_websquare_selectbox(driver, "선택", plant)
                if not success_plant:
                    print(f"   ⚠️ 플랜트 [{plant}] 선택에 실패하여 기본 상태로 시도합니다.")
                
                # 2. 계획 날짜 입력창 자동 찾기
                date_input, sep = find_date_input_and_format(driver)
                if date_input is None:
                    print("❌ 날짜 입력창을 화면에서 찾을 수 없습니다.")
                    input("로그인 및 [생산계획 -> 3~12 F/C 주별] 메뉴로 이동을 확인한 후 엔터를 누르세요...")
                    continue
                
                # 사이트의 날짜 입력 형식에 맞춰 포맷 변환 (2026/06/16)
                formatted_date = date_str
                if sep == "/":
                    formatted_date = date_str.replace("-", "/")
                elif sep == "":
                    formatted_date = date_str.replace("-", "")
                
                # 날짜 입력 진행
                try:
                    date_input.click()
                    date_input.send_keys(Keys.CONTROL + "a")
                    date_input.send_keys(Keys.BACKSPACE)
                    date_input.send_keys(formatted_date)
                    date_input.send_keys(Keys.TAB)
                    time.sleep(0.5)
                    print(f"   ✓ 날짜 [{formatted_date}] 입력 성공")
                except Exception as e:
                    print(f"   ❌ 날짜 입력 도중 에러: {e}")
                
                # 3. Search(조회) 클릭
                search_btn = find_clickable_by_text(driver, ["Search", "조회", "btnSearch"])
                if search_btn:
                    try:
                        search_btn.click()
                        print("   ✓ Search 클릭 완료")
                        time.sleep(3.5) # 조회 로딩 대기 시간 충분히 부여
                    except Exception as e:
                        print(f"   ❌ Search 클릭 오류: {e}")
                else:
                    print("   ❌ Search 버튼을 찾을 수 없습니다.")
                    
                # 4. 엑셀 다운로드 아이콘 버튼 클릭
                excel_btn = find_excel_download_icon_button(driver)
                if excel_btn is None:
                    # 백업 텍스트 기반 탐색
                    excel_btn = find_clickable_by_text(driver, ["엑셀", "excel", "다운로드", "download"])
                    
                if excel_btn:
                    try:
                        excel_btn.click()
                        print("   ✓ 엑셀 다운로드 클릭 시도...")
                        time.sleep(1.5) # 팝업 뜨는 시간 대기
                        
                        # 5. 엑셀다운로드 팝업창의 '예' 버튼 클릭 처리
                        print("   ✓ 엑셀다운로드 '예' 버튼 확인 중...")
                        yes_btn = find_clickable_by_text(driver, ["예"])
                        if yes_btn:
                            yes_btn.click()
                            print("   ✓ '예' 버튼 클릭 완료! (파일이 저장될 때까지 5초 대기...)")
                            time.sleep(5)
                        else:
                            print("   ❌ 팝업창에서 '예' 버튼을 찾지 못해 강제 엔터 전송 시도...")
                            # 팝업에 포커스가 기본으로 '예' 버튼에 가있을 수 있으므로 활성 객체에 엔터 전송
                            driver.switch_to.active_element.send_keys(Keys.ENTER)
                            time.sleep(5)
                    except Exception as e:
                        print(f"   ❌ 엑셀 다운로드 진행 중 오류: {e}")
                else:
                    print("   ❌ 엑셀 다운로드 버튼을 찾을 수 없습니다.")
                    
        print("\n" + "=" * 60)
        print(" 모든 작업이 완료되었습니다!")
        print(f" 다운로드된 파일들은 다음 폴더에서 확인하실 수 있습니다:")
        print(f" -> {download_dir}")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 매크로가 중단되었습니다.")
    except Exception as e:
        print(f"\n작업 중 알 수 없는 에러가 발생했습니다: {e}")
    finally:
        print("\n브라우저 세션을 열어둔 상태로 종료합니다. 직접 창을 닫아주세요.")

if __name__ == "__main__":
    run_download()
