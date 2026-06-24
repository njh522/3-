import pandas as pd
import numpy as np
import datetime
from prophet import Prophet
import os
import warnings

# Prophet warning 무시
warnings.filterwarnings("ignore", category=FutureWarning)

def extract_sales(file_path, sheet_name, year):
    if not os.path.exists(file_path):
        return pd.DataFrame()
        
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    
    header_idx = 1
    for i in range(10):
        if '모델' in df.iloc[i].astype(str).values:
            header_idx = i
            break
            
    sub_idx = header_idx + 2
    for i in range(header_idx, header_idx+5):
        if '수량' in df.iloc[i].astype(str).values:
            sub_idx = i
            break
            
    qty_cols = {}
    amt_cols = {}
    model_col = None
    customer_col = None
    
    # 모델 및 고객사 컬럼 인덱스 찾기
    for c in range(df.shape[1]):
        h_val = str(df.iloc[header_idx, c]).strip()
        if h_val == '모델':
            model_col = c
        if '거래선' in h_val or '고객사' in h_val or '업체' in h_val:
            customer_col = c
            
    # 월별 수량 및 금액 컬럼 인덱스 매핑 (수량 바로 오른쪽 열이 금액인 구조)
    for c in range(df.shape[1] - 1):
        h_val = str(df.iloc[header_idx, c]).strip()
        s_val = str(df.iloc[sub_idx, c]).strip()
        s_val_next = str(df.iloc[sub_idx, c+1]).strip()
        
        if h_val.endswith('월') and len(h_val) <= 3 and h_val[:-1].isdigit():
            month = int(h_val[:-1])
            date_str = f"{year}-{month:02d}-01"
            
            if '수량' in s_val and '금액' in s_val_next:
                qty_cols[c] = date_str
                amt_cols[c+1] = date_str

    if model_col is None:
        return pd.DataFrame()
        
    if customer_col is not None:
        df[customer_col] = df[customer_col].replace(['', ' ', 'nan', 'NaN', 'None'], np.nan)
        df.loc[sub_idx+1:, customer_col] = df.loc[sub_idx+1:, customer_col].ffill()

    # 합계/소계/거래선계 등 집계 행 필터링을 위한 패턴
    skip_patterns = ['합계', '소계', '합 계', '소   계', '거래선계', '거래선 계', '기타']
    
    def is_skip_row(val):
        """합계/소계/기타 등 집계 행인지 판별"""
        val_clean = val.replace(' ', '')
        for p in ['합계', '소계', '거래선계']:
            if p in val_clean:
                return True
        if val_clean == '기타' or val_clean.startswith('기타('):
            return True
        return False
    
    data_rows = []
    for i in range(sub_idx + 1, df.shape[0]):
        model = str(df.iloc[i, model_col]).strip()
        if not model or model == 'nan' or model == 'None' or is_skip_row(model):
            continue
            
        customer = str(df.iloc[i, customer_col]).strip() if customer_col is not None else "Unknown"
        # 거래선도 집계 행이면 스킵
        if is_skip_row(customer):
            continue
            
        for q_col, date_str in qty_cols.items():
            a_col = q_col + 1
            qty = df.iloc[i, q_col]
            amt = df.iloc[i, a_col]
            
            try:
                qty = float(qty)
                if pd.isna(qty): qty = 0.0
            except:
                qty = 0.0
                
            try:
                amt = float(amt)
                if pd.isna(amt): amt = 0.0
            except:
                amt = 0.0
                
            data_rows.append({
                'ds': date_str,
                'customer': customer,
                'model': model,
                'y': int(qty * 1000),      # 수량은 실제 개수 단위(EA)
                'amount': amt             # 금액은 백만원 단위
            })
            
    return pd.DataFrame(data_rows)


def load_and_merge_data(base_dir):
    all_dfs = []
    current_year = datetime.datetime.now().year
    # 2023년부터 현재 년도까지 동적으로 매출 실적 파일 로드
    for year in range(2023, current_year + 1):
        short_year = str(year)[2:]  # 23, 24, 25, 26 ...
        file_path = f"{base_dir}\\{short_year}년 매출 실적.xlsx"
        sheet_name = f"{short_year}년(세부_실적)"
        df = extract_sales(file_path, sheet_name, year)
        if not df.empty:
            all_dfs.append(df)
    
    if not all_dfs:
        return pd.DataFrame()
    
    sales_df = pd.concat(all_dfs, ignore_index=True)
    if sales_df.empty:
        return pd.DataFrame()
        
    sales_df['ds'] = pd.to_datetime(sales_df['ds'])
    sales_df = sales_df.sort_values(by=['customer', 'model', 'ds']).reset_index(drop=True)
    
    return sales_df

def check_volatility(recent_12m_df):
    if len(recent_12m_df) < 3:
        return "데이터부족", 0, "판단불가"
    
    mean_qty = recent_12m_df['y'].mean()
    std_qty = recent_12m_df['y'].std()
    
    if mean_qty == 0:
        return "출하중단(0)", 0, "휴면"
        
    cv = std_qty / mean_qty
    
    if cv > 1.2:
        return f"🚨 극심 (오차율 {int(cv*100)}%)", cv, "사전 긴급 물량(버퍼 30%) 확보 필수. FCST 무시 오더 잦음"
    elif cv > 0.6:
        return f"⚠️ 불안정 (오차율 {int(cv*100)}%)", cv, "정기적 모니터링 및 버퍼 10% 운용 권장"
    else:
        return f"✅ 안정 (오차율 {int(cv*100)}%)", cv, "생판 정규 리드타임 맞춰 안전 가동 가능"


def detect_seasonality(m_df):
    if len(m_df) < 12:
        return "데이터부족"
    
    # 23, 24년 기반 계절성 도출
    past_years = m_df[m_df['ds'].dt.year.isin([2023, 2024])]
    if past_years.empty:
        return "데이터부족"
        
    past_years['month'] = past_years['ds'].dt.month
    monthly_sums = past_years.groupby('month')['y'].sum()
    
    if monthly_sums.sum() == 0:
        return "수요없음"
        
    # 평균 대비 특정 월 비중이 1.5배 높으면 성수기
    avg_per_month = monthly_sums.mean()
    peak_months = monthly_sums[monthly_sums > avg_per_month * 1.5].index.tolist()
    
    if peak_months:
        return f"{', '.join(map(str, peak_months))}월 폭발"
    else:
        return "사계절 균등(무계절성)"


def analyze_models(sales_df, current_date=None):
    if current_date is None:
        today = datetime.datetime.now()
        current_date = datetime.datetime(today.year, today.month, 1)
        
    # 생판회의를 위한 고객사-모델 심층 분석
    sales_grouped = sales_df.groupby(['customer', 'model', 'ds'])[['y', 'amount']].sum().reset_index()
    
    results = []
    pairs = sales_grouped[['customer', 'model']].drop_duplicates()
    
    for _, row in pairs.iterrows():
        customer = row['customer']
        model = row['model']
        m_df = sales_grouped[(sales_grouped['customer'] == customer) & (sales_grouped['model'] == model)].sort_values(by='ds')
        past_m_df = m_df[m_df['ds'] < current_date].copy()
        
        if past_m_df.empty:
            continue
            
        last_12_months = past_m_df.tail(12)
        
        # Volatility (긴급 오더 오차)
        vol_grade, cv, vol_action = check_volatility(last_12_months)
        
        # Seasonality (성수기 파악)
        peak_season = detect_seasonality(past_m_df)
        
        # 평균 단가 계산 (원/개): 금액(백만원) * 1,000,000 / 수량(개)
        tot_qty = past_m_df['y'].sum()
        tot_amt = past_m_df['amount'].sum()
        if tot_qty > 0:
            unit_price = (tot_amt * 1000000) / tot_qty
        else:
            unit_price = 0.0
            
        results.append({
            '업체(거래선)': customer,
            'model': model,
            '12개월 평점(CV)': cv,
            '불규칙오더(변동성) 등급': vol_grade,
            '가이던스(액션플랜)': vol_action,
            '역대 데이터 성수기 패턴': peak_season,
            '단가(원)': int(round(unit_price))
        })
        
    return pd.DataFrame(results)

def forecast_single_pair(row, sales_grouped, current_date, target_months):
    """
    개별 (고객사, 모델) 조합에 대한 M~M+3 4개월 예측 연산을 수행하는 워커 함수입니다.
    """
    customer = row['customer']
    model = row['model']
    
    m_df = sales_grouped[(sales_grouped['customer'] == customer) & (sales_grouped['model'] == model)].sort_values(by='ds')
    past_m_df = m_df[m_df['ds'] < current_date].copy()
    
    # 1. 과거 데이터가 아예 없는 경우
    if past_m_df.empty:
        row_res = {'업체(거래선)': customer, 'model': model}
        for mon in target_months:
            row_res[f"{mon.year}년 {mon.month}월"] = 0
        row_res['4개월 총합계(자재준비)'] = 0
        return row_res
        
    # 2. 직전 12개월 동안 매출 실적이 전혀 없는 경우 (단종/휴면 모델 스킵)
    recent_12m = past_m_df[past_m_df['ds'] >= (current_date - pd.DateOffset(months=12))]
    if recent_12m.empty or recent_12m['y'].sum() == 0:
        row_res = {'업체(거래선)': customer, 'model': model}
        for mon in target_months:
            row_res[f"{mon.year}년 {mon.month}월"] = 0
        row_res['4개월 총합계(자재준비)'] = 0
        return row_res
        
    # 3. 데이터 개수가 12개 미만인 경우 (신규 품목 등은 단순 3개월 평균으로 고속 대체)
    if len(past_m_df) < 12:
        recent_3m = past_m_df.tail(3)
        avg_val = int(recent_3m['y'].mean()) if not recent_3m.empty else 0
        
        row_res = {'업체(거래선)': customer, 'model': model}
        tot = 0
        for mon in target_months:
            row_res[f"{mon.year}년 {mon.month}월"] = avg_val
            tot += avg_val
        row_res['4개월 총합계(자재준비)'] = tot
        return row_res
        
    # 4. 활성화된 코어 모델에 대해서만 정밀 Prophet 시계열 예측 가동
    try:
        import logging
        logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
        
        m = Prophet(yearly_seasonality=True, daily_seasonality=False, weekly_seasonality=False, uncertainty_samples=0)
        m.add_country_holidays(country_name='KR')
        m.fit(past_m_df)
        
        future = m.make_future_dataframe(periods=4, freq='MS')
        forecast = m.predict(future)
        
        # Filter for target_months
        recent_pred = forecast[forecast['ds'].isin(target_months)]
        
        row_res = {'업체(거래선)': customer, 'model': model}
        tot = 0
        for mon in target_months:
            val = recent_pred[recent_pred['ds'] == mon]['yhat']
            clean_val = max(0, int(val.values[0])) if not val.empty else 0
            row_res[f"{mon.year}년 {mon.month}월"] = clean_val
            tot += clean_val
            
        row_res['4개월 총합계(자재준비)'] = tot
        return row_res
    except Exception as e:
        # 예외 처리: Prophet 피팅 에러 시 최근 3개월 평균으로 백업
        recent_3m = past_m_df.tail(3)
        avg_val = int(recent_3m['y'].mean()) if not recent_3m.empty else 0
        row_res = {'업체(거래선)': customer, 'model': model}
        tot = 0
        for mon in target_months:
            row_res[f"{mon.year}년 {mon.month}월"] = avg_val
            tot += avg_val
        row_res['4개월 총합계(자재준비)'] = tot
        return row_res


def generate_rolling_4m_forecast(sales_df, current_date=None):
    import concurrent.futures
    from functools import partial
    import sys
    
    if current_date is None:
        today = datetime.datetime.now()
        current_date = datetime.datetime(today.year, today.month, 1)
        
    sales_grouped = sales_df.groupby(['customer', 'model', 'ds'])[['y', 'amount']].sum().reset_index()
    pairs = sales_grouped[['customer', 'model']].drop_duplicates()
    
    target_months = [current_date, 
                     current_date + pd.DateOffset(months=1),
                     current_date + pd.DateOffset(months=2),
                     current_date + pd.DateOffset(months=3)]
                     
    # pairs의 각 행을 딕셔너리로 변환하여 피클링 안정성 확보
    rows_list = [row.to_dict() for _, row in pairs.iterrows()]
    
    max_workers = min(32, os.cpu_count() or 4)
    
    worker_func = partial(forecast_single_pair, 
                          sales_grouped=sales_grouped, 
                          current_date=current_date, 
                          target_months=target_months)
                          
    if sys.platform == 'win32':
        print(f"Windows 환경 감지: ThreadPoolExecutor로 예측 연산 가동 (작업자 수 {max_workers})...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(worker_func, rows_list))
    else:
        print(f"Prophet 병렬 예측 연산 가동 (ProcessPoolExecutor, 작업자 수 {max_workers})")
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(worker_func, rows_list))
        
    return pd.DataFrame(results), target_months


def extract_inventory(base_dir):
    """
    base_dir 디렉토리 내에서 재고_*.xlsx 파일을 찾아서 실재고 수량을 파싱합니다.
    """
    import glob
    files = glob.glob(os.path.join(base_dir, "재고_*.xlsx"))
    if not files:
        return pd.DataFrame(columns=['model', 'inventory'])
        
    # 가장 최근 파일 또는 첫 번째 파일 사용
    file_path = files[0]
    
    try:
        xls = pd.ExcelFile(file_path)
        # 마감 시트 찾기
        sheet_name = xls.sheet_names[0]
        for name in xls.sheet_names:
            if "마감" in name and "최종" in name:
                sheet_name = name
                break
                
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    except Exception as e:
        return pd.DataFrame(columns=['model', 'inventory'])
        
    model_col = -1
    qty_col = -1
    start_row = 0
    
    for i in range(min(5, df.shape[0])):
        vals = df.iloc[i].astype(str).tolist()
        for j, v in enumerate(vals):
            v_str = str(v)
            if '행 레이블' in v_str or '모델' in v_str:
                model_col = j
            if '실재고수량' in v_str:
                qty_col = j
                
        if model_col != -1 and qty_col != -1:
            start_row = i + 1
            break
            
    if model_col == -1 or qty_col == -1:
        model_col = 0
        qty_col = 1
        start_row = 2
        
    inv_data = []
    for i in range(start_row, df.shape[0]):
        model = str(df.iloc[i, model_col]).strip()
        if model.endswith(' v'):
            model = model[:-2].strip()
            
        if not model or model == 'nan' or '총합계' in model or '소계' in model:
            continue
            
        qty = df.iloc[i, qty_col]
        try:
            qty = int(float(qty))
        except:
            qty = 0
            
        inv_data.append({'model': model, 'inventory': qty})
        
    return pd.DataFrame(inv_data)


def calculate_net_requirements(final_df):
    """
    예측 결과와 실재고 데이터를 조합하여 순소요량 및 안전 버퍼가 반영된 최종 추천 조달량을 연산합니다.
    """
    if 'inventory' not in final_df.columns:
        final_df['inventory'] = 0
        
    # 실재고 정수 변환 및 결측치 처리
    final_df['현재 실재고량'] = final_df['inventory'].fillna(0).round().astype(int)
    
    pred_col = '4개월 총합계(자재준비)'
    if pred_col not in final_df.columns:
        pred_col = '4개월 합계'
        
    if pred_col not in final_df.columns:
        # 합계가 없는 경우 계산
        month_cols = [c for c in final_df.columns if '월' in c and ('년' in c or '/' in c)]
        if month_cols:
            final_df[pred_col] = final_df[month_cols].sum(axis=1)
        else:
            final_df[pred_col] = 0
            
    # 결측치(NaN) 방지 처리
    final_df[pred_col] = final_df[pred_col].fillna(0)
            
    # 1. 순소요량 = 4개월 총예측량 - 현재 실재고량 (최소 0)
    final_df['순소요량'] = (final_df[pred_col] - final_df['현재 실재고량']).clip(lower=0)
    
    # 2. 버퍼 비율 정의
    def get_buffer_rate(grade):
        if pd.isna(grade):
            return 1.0
        grade_str = str(grade)
        if '극심' in grade_str:
            return 1.3
        elif '불안정' in grade_str:
            return 1.1
        else:
            return 1.0
            
    buffer_rates = final_df['불규칙오더(변동성) 등급'].apply(get_buffer_rate)
    
    # 3. 최종 추천 조달량 = (4개월 총예측량 * 버퍼율) - 현재 실재고량 (최소 0)
    final_df['최종 추천 조달량'] = ((final_df[pred_col] * buffer_rates) - final_df['현재 실재고량']).round().clip(lower=0).astype(int)
    
    # 4. 최종 추천 조달 금액(백만원) = (최종 추천 조달량 * 단가(원)) / 1,000,000
    if '단가(원)' in final_df.columns:
        final_df['최종 추천 조달 금액(백만원)'] = (final_df['최종 추천 조달량'] * final_df['단가(원)']) / 1000000
        # 소수점 둘째 자리까지 반올림
        final_df['최종 추천 조달 금액(백만원)'] = final_df['최종 추천 조달 금액(백만원)'].round(2)
    else:
        final_df['최종 추천 조달 금액(백만원)'] = 0.0
        
    return final_df


def load_rolling_forecast_cache(base_dir):
    """
    미리 생성된 AI 예측 결과 캐시 파일(rolling_forecast_cache.csv)이 있으면 로드합니다.
    캐시의 첫 번째 예측 월이 현재 월과 일치하지 않으면 오래된 캐시로 판단하고 무시합니다.
    """
    import os
    import re
    cache_path = os.path.join(base_dir, "rolling_forecast_cache.csv")
    if not os.path.exists(cache_path):
        return None, []
        
    try:
        df = pd.read_csv(cache_path)
        # 컬럼 중 'YYYY년 MM월' 형태를 파싱하여 target_months 복원
        target_months = []
        for col in df.columns:
            m = re.match(r"(\d+)년\s*(\d+)월", str(col))
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                target_months.append(datetime.datetime(year, month, 1))
                
        target_months = sorted(target_months)
        
        # 캐시 유효성 검증: 첫 번째 예측 월이 현재 월과 일치하는지 확인
        if target_months:
            today = datetime.datetime.now()
            expected_first_month = datetime.datetime(today.year, today.month, 1)
            if target_months[0] != expected_first_month:
                print(f"[캐시 만료] 캐시 기준월({target_months[0].strftime('%Y-%m')})이 현재 월({expected_first_month.strftime('%Y-%m')})과 불일치. 캐시를 무시합니다.")
                return None, []
        
        return df, target_months
    except:
        return None, []


def find_desktop_sales_dir():
    # 바탕화면 가전영업팀 실적파일 경로 탐색
    paths = [
        r"C:\Users\power\OneDrive\바탕 화면\영업팀 실적파일",
        r"C:\Users\power\Desktop\영업팀 실적파일",
        r"C:\Users\power\OneDrive\바탕 화면",
        r"C:\Users\power\Desktop"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def extract_code_model_mapping(base_dir):
    """
    재고_*.xlsx 및 매출 실적 파일, 그리고 코웨이 모델 품번 정리 LIST.xlsx에서 모델 코드 -> 모델명 매핑을 추출합니다.
    """
    import json
    cache_json_path = os.path.join(base_dir, "code_model_mapping.json")
    mapping_file = ""
    desktop_dir = find_desktop_sales_dir()
    if desktop_dir:
        mapping_file = os.path.join(desktop_dir, "코웨이 모델 품번 정리 LIST.xlsx")
        
    if os.path.exists(cache_json_path):
        use_cache = True
        if os.path.exists(mapping_file):
            if os.path.getmtime(mapping_file) > os.path.getmtime(cache_json_path):
                use_cache = False
                print("[캐시 만료] 품번 정리 LIST 엑셀이 수정되었습니다. 매핑을 재추출합니다.")
        
        if use_cache:
            try:
                with open(cache_json_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
                print(f"[매핑 캐시 로드 성공] JSON 캐시에서 매핑 {len(mapping)}건을 즉시 복원했습니다. (0.001초)")
                return mapping
            except Exception as e:
                print(f"[캐시 로드 실패] {e}, 매핑을 재추출합니다.")

    mapping = {}
    import glob
    import re
    import shutil
    
    # 1. 코웨이 모델 품번 정리 LIST.xlsx 에서 추출 (바탕화면 영업팀 실적파일 내)
    desktop_dir = find_desktop_sales_dir()
    if desktop_dir:
        mapping_file = os.path.join(desktop_dir, "코웨이 모델 품번 정리 LIST.xlsx")
        if os.path.exists(mapping_file):
            temp_map = os.path.join(base_dir, "temp_mapping_load.xlsx")
            try:
                shutil.copy2(mapping_file, temp_map)
                xl_map = pd.ExcelFile(temp_map)
                for sheet in xl_map.sheet_names:
                    df_map = xl_map.parse(sheet, header=None)
                    for _, row in df_map.iterrows():
                        row_vals = [str(x).strip() for x in row.tolist()]
                        
                        # 7자리 숫자 코드 후보 추출
                        code_cands = []
                        for v in row_vals:
                            v_clean = v.split('.')[0]
                            if re.match(r'^\d{7}$', v_clean):
                                code_cands.append(v_clean)
                                
                        # 모델명 후보 추출
                        model_cands = []
                        for v in row_vals:
                            v_clean = v.strip()
                            if not v_clean or v_clean.lower() == 'nan' or len(v_clean) <= 3:
                                continue
                            if '합계' in v_clean or '소계' in v_clean:
                                continue
                            if v_clean.startswith('PN') or 'TANK' in v_clean:
                                model_cands.append(v_clean)
                                
                        if code_cands and model_cands:
                            for c in code_cands:
                                for m in model_cands:
                                    mapping[c] = m
                xl_map.close()
            except Exception as e:
                print(f"[매핑 추출 경고] 품번 정리 LIST 파일 파싱 실패: {e}")
            finally:
                if os.path.exists(temp_map):
                    try: os.remove(temp_map)
                    except: pass

    # 2. 재고 파일에서 추출
    files = glob.glob(os.path.join(base_dir, "재고_*.xlsx"))
    if files:
        file_path = files[0]
        try:
            xls = pd.ExcelFile(file_path)
            sheet_name = xls.sheet_names[0]
            for name in xls.sheet_names:
                if "마감" in name and "최종" in name:
                    sheet_name = name
                    break
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
            
            # 첫 번째 열에서 모델명과 괄호 안의 코드 매핑 추출
            for val in df[0]:
                if pd.notna(val):
                    val_str = str(val).strip()
                    m = re.search(r'([A-Za-z0-9_#-]+)\s*\((.*?)\)', val_str)
                    if m:
                        model_name = m.group(1).strip()
                        code = m.group(2).strip()
                        if code and model_name:
                            if model_name.endswith(' v'):
                                model_name = model_name[:-2].strip()
                            mapping[code] = model_name
        except Exception as e:
            print(f"[매핑 추출 경고] 재고 파일 파싱 실패: {e}")

    # 3. 매출 실적 파일에서 추출 (예: 26년 매출 실적.xlsx)
    sales_files = glob.glob(os.path.join(base_dir, "*년 매출 실적.xlsx"))
    for sales_file in sales_files:
        try:
            df = pd.read_excel(sales_file, sheet_name=None, header=None)
            for sheet_name, sheet_df in df.items():
                if "세부" in sheet_name or "실적" in sheet_name:
                    model_col = -1
                    code_col = -1
                    header_row = -1
                    for r in range(min(10, sheet_df.shape[0])):
                        row_vals = [str(x).strip() for x in sheet_df.iloc[r]]
                        if '모델' in row_vals and ('Code' in row_vals or 'code' in row_vals or 'CODE' in row_vals):
                            header_row = r
                            model_col = row_vals.index('모델')
                            for idx, val in enumerate(row_vals):
                                if val.lower() == 'code':
                                    code_col = idx
                                    break
                            break
                    
                    if model_col != -1 and code_col != -1:
                        for i in range(header_row + 1, sheet_df.shape[0]):
                            model = str(sheet_df.iloc[i, model_col]).strip()
                            code = str(sheet_df.iloc[i, code_col]).strip()
                            if model and code and model != 'nan' and code != 'nan' and '계' not in model and '합계' not in model:
                                mapping[code] = model
        except Exception as e:
            print(f"[매핑 추출 경고] 매출 실적 파일 파싱 실패: {e}")
            
    try:
        with open(cache_json_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=4)
        print(f"[매핑 캐시 생성 완료] code_model_mapping.json 에 저장되었습니다.")
    except Exception as e:
        print(f"[캐시 저장 실패] {e}")
        
    return mapping


def parse_customer_fcst(file_path, mapping_dict):
    """
    고객사 12주 FCST 엑셀 파일을 파싱하여 월별 고객 요구량 및 2주 선행 생산량 계획을 도출합니다.
    """
    import re
    import shutil
    if not os.path.exists(file_path):
        return None
        
    cache_csv_path = file_path + "_parsed_cache.csv"
    
    if os.path.exists(cache_csv_path) and os.path.getmtime(cache_csv_path) >= os.path.getmtime(file_path):
        try:
            df_cached = pd.read_csv(cache_csv_path)
            if 'month' in df_cached.columns:
                df_cached['month'] = pd.to_datetime(df_cached['month'])
            print(f"[FCST 캐시 로드 성공] 파싱 캐시 {len(df_cached)}건을 즉시 복원했습니다. (0.01초)")
            return df_cached
        except Exception as e:
            print(f"[FCST 캐시 로드 실패] {e}, 재파싱을 진행합니다.")
        
    temp_fcst = file_path + "_temp.xlsx"
    try:
        shutil.copy2(file_path, temp_fcst)
        xl = pd.ExcelFile(temp_fcst)
    except Exception as e:
        print(f"[FCST 파서 에러] 파일 로딩 실패: {e}")
        return None

    # Coway 전용 다중 시트 구조 자동 감지 (예: '0618'과 '0618 W12'가 모두 존재하는지)
    sheets = xl.sheet_names
    daily_sheet = None
    weekly_sheet = None
    
    # 0618, 0624 등 4자리 날짜 시트 후보들을 추출 후 역순 정렬하여 최신 날짜 순으로 조회
    candidate_sheets = sorted([name for name in sheets if re.match(r'^\d{4}$', name)], reverse=True)
    
    for name in candidate_sheets:
        # 매칭되는 W12 시트가 있는지 확인
        w_name = f"{name} W12"
        w_name_alt = f"{name}W12"
        w_name_alt2 = f"{name} W3-12"
        w_sheet = None
        for sn in sheets:
            if sn.replace(" ", "").lower() in [w_name.replace(" ", "").lower(), w_name_alt.replace(" ", "").lower(), w_name_alt2.replace(" ", "").lower()]:
                w_sheet = sn
                break
        if w_sheet:
            daily_sheet = name
            weekly_sheet = w_sheet
            break
                
    if daily_sheet and weekly_sheet:
        print(f"[Coway 전용 시트 감지] Daily 시트: '{daily_sheet}', Weekly 시트: '{weekly_sheet}'")
        try:
            # 1) Daily 시트 파싱
            df_daily = xl.parse(daily_sheet)
            daily_date_cols = {}
            for c in range(1, df_daily.shape[1]):
                col_name = str(df_daily.columns[c]).strip()
                m = re.match(r'(\d+)/(\d+)', col_name)
                if m:
                    month = int(m.group(1))
                    day = int(m.group(2))
                    # 2026년 기준
                    daily_date_cols[c] = datetime.date(2026, month, day)
                    
            daily_records = []
            for r in range(df_daily.shape[0]):
                code_val = str(df_daily.iloc[r, 0]).strip().split('.')[0]
                if not re.match(r'^\d{7}$', code_val):
                    continue
                model_name = mapping_dict.get(code_val, f"Unknown_{code_val}")
                for c, demand_date in daily_date_cols.items():
                    qty_val = df_daily.iloc[r, c]
                    try:
                        qty = float(qty_val)
                        if pd.isna(qty): qty = 0.0
                    except:
                        qty = 0.0
                    if qty > 0:
                        daily_records.append({
                            'model': model_name,
                            'demand_date': demand_date,
                            'qty': qty
                        })
                        
            # 2) Weekly 시트 파싱
            df_weekly = xl.parse(weekly_sheet, header=None)
            weekly_date_cols = {}
            row1 = df_weekly.iloc[1].tolist()
            for c in range(2, df_weekly.shape[1]):
                val = row1[c]
                if pd.notna(val):
                    val_str = str(val).strip()
                    m = re.match(r'(\d+)/(\d+)', val_str)
                    if m:
                        month = int(m.group(1))
                        day = int(m.group(2))
                        weekly_date_cols[c] = datetime.date(2026, month, day)
                        
            weekly_records = []
            for r in range(2, df_weekly.shape[0]):
                code_val = str(df_weekly.iloc[r, 1]).strip().split('.')[0]
                if not re.match(r'^\d{7}$', code_val):
                    continue
                model_name = mapping_dict.get(code_val, f"Unknown_{code_val}")
                for c, demand_date in weekly_date_cols.items():
                    qty_val = df_weekly.iloc[r, c]
                    try:
                        qty = float(qty_val)
                        if pd.isna(qty): qty = 0.0
                    except:
                        qty = 0.0
                    if qty > 0:
                        weekly_records.append({
                            'model': model_name,
                            'demand_date': demand_date,
                            'qty': qty
                        })
            xl.close()
            try: os.remove(temp_fcst)
            except: pass
            
            # 병합 및 가공
            all_records = daily_records + weekly_records
            if not all_records:
                return pd.DataFrame(columns=['업체(거래선)', 'model', 'month', 'fcst_qty', 'prod_qty'])
                
            df_all = pd.DataFrame(all_records)
            df_all['prod_date'] = df_all['demand_date'].apply(lambda d: d - datetime.timedelta(days=14))
            df_all['demand_month'] = df_all['demand_date'].apply(lambda d: datetime.datetime(d.year, d.month, 1))
            df_all['prod_month'] = df_all['prod_date'].apply(lambda d: datetime.datetime(d.year, d.month, 1))
            
            demand_grp = df_all.groupby(['model', 'demand_month'])['qty'].sum().reset_index()
            demand_grp.columns = ['model', 'month', 'fcst_qty']
            
            prod_grp = df_all.groupby(['model', 'prod_month'])['qty'].sum().reset_index()
            prod_grp.columns = ['model', 'month', 'prod_qty']
            
            merged = pd.merge(demand_grp, prod_grp, on=['model', 'month'], how='outer').fillna(0)
            merged['fcst_qty'] = merged['fcst_qty'].round().astype(int)
            merged['prod_qty'] = merged['prod_qty'].round().astype(int)
            merged['업체(거래선)'] = 'Coway'
            try:
                merged.to_csv(cache_csv_path, index=False, encoding='utf-8-sig')
                print(f"[FCST 캐시 생성 완료] {cache_csv_path} 에 저장되었습니다.")
            except Exception as e:
                print(f"[FCST 캐시 저장 실패] {e}")
            return merged
        except Exception as e:
            print(f"[Coway 전용 시트 파싱 에러] {e}")
            
    # 표준 파싱 (1개 시트의 Code 및 날짜 컬럼 자동 인식 구조)
    try:
        df = xl.parse(sheets[0], header=None)
        xl.close()
        try: os.remove(temp_fcst)
        except: pass
    except Exception as e:
        print(f"[FCST 표준 파서 에러] 시트 파싱 실패: {e}")
        try: os.remove(temp_fcst)
        except: pass
        return None

    code_col = -1
    date_cols = {}
    best_date_row = -1
    max_dates_found = 0
    
    # 상위 15개 행을 스캔하여 Code 및 날짜 컬럼 정보 수집
    for r in range(min(15, df.shape[0])):
        dates_in_row = {}
        row_vals = df.iloc[r].tolist()
        for c, val in enumerate(row_vals):
            if pd.isna(val):
                continue
            val_str = str(val).strip()
            
            if code_col == -1 and any(x in val_str.lower() for x in ['code', '코드', 'part', '품목', '모델코드', '부품코드']):
                code_col = c
                
            date_val = None
            if isinstance(val, (datetime.datetime, datetime.date)):
                date_val = pd.to_datetime(val).date()
            else:
                if val_str.isdigit() and len(val_str) <= 4:
                    continue
                try:
                    clean_str = re.sub(r'[\s년월일]', '-', val_str).replace('--', '-').strip('-')
                    if '주차' in val_str:
                        m_week = re.search(r'(\d+)년\s*(\d+)주차', val_str)
                        if m_week:
                            yr = int(m_week.group(1))
                            if yr < 100: yr += 2000
                            wk = int(m_week.group(2))
                            d = f"{yr}-W{wk-1}-1"
                            date_val = datetime.datetime.strptime(d, "%Y-W%W-%w").date()
                    else:
                        if any(sep in clean_str for sep in ['-', '/', '.']):
                            date_val = pd.to_datetime(clean_str).date()
                except:
                    pass
            
            if date_val is not None:
                dates_in_row[c] = date_val
                
        if len(dates_in_row) > max_dates_found:
            max_dates_found = len(dates_in_row)
            best_date_row = r
            date_cols = dates_in_row

    if code_col == -1:
        code_col = 0
        
    if not date_cols:
        print("[FCST 파서 에러] 날짜 또는 주차 컬럼을 찾지 못했습니다.")
        return None

    data_start_row = best_date_row + 1 if best_date_row != -1 else 1
    fcst_records = []
    
    for r in range(data_start_row, df.shape[0]):
        code_val = str(df.iloc[r, code_col]).strip().split('.')[0]
        if not code_val or code_val == 'nan' or code_val == 'None' or '계' in code_val or '합계' in code_val:
            continue
            
        model_name = mapping_dict.get(code_val, code_val)
        if model_name.endswith(' v'):
            model_name = model_name[:-2].strip()
            
        for c, demand_date in date_cols.items():
            qty_val = df.iloc[r, c]
            try:
                qty = float(qty_val)
                if pd.isna(qty): qty = 0.0
            except:
                qty = 0.0
                
            if qty == 0.0:
                continue
                
            prod_date = demand_date - datetime.timedelta(days=14)
            demand_month = datetime.datetime(demand_date.year, demand_date.month, 1)
            prod_month = datetime.datetime(prod_date.year, prod_date.month, 1)
            
            fcst_records.append({
                'model': model_name,
                'demand_month': demand_month,
                'prod_month': prod_month,
                'qty': qty
            })
            
    if not fcst_records:
        return pd.DataFrame(columns=['업체(거래선)', 'model', 'month', 'fcst_qty', 'prod_qty'])
        
    records_df = pd.DataFrame(fcst_records)
    
    demand_grp = records_df.groupby(['model', 'demand_month'])['qty'].sum().reset_index()
    demand_grp.columns = ['model', 'month', 'fcst_qty']
    
    prod_grp = records_df.groupby(['model', 'prod_month'])['qty'].sum().reset_index()
    prod_grp.columns = ['model', 'month', 'prod_qty']
    
    merged_grp = pd.merge(demand_grp, prod_grp, on=['model', 'month'], how='outer').fillna(0)
    merged_grp['업체(거래선)'] = 'Coway'
    
    merged_grp['fcst_qty'] = merged_grp['fcst_qty'].round().astype(int)
    merged_grp['prod_qty'] = merged_grp['prod_qty'].round().astype(int)
    
    try:
        merged_grp.to_csv(cache_csv_path, index=False, encoding='utf-8-sig')
        print(f"[FCST 캐시 생성 완료] {cache_csv_path} 에 저장되었습니다.")
    except Exception as e:
        print(f"[FCST 캐시 저장 실패] {e}")
        
    return merged_grp


