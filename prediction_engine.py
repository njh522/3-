import pandas as pd
import numpy as np
from prophet import Prophet
import warnings

# 경고 무시
warnings.filterwarnings('ignore')

def get_last_actual_month_2026(df):
    """
    2026년 데이터 중 실제 실적이 존재하는 마지막 월을 동적으로 감지합니다.
    """
    df_2026 = df[df['연도'] == 2026]
    if df_2026.empty:
        return 4 # 기본값 4월
        
    last_month = 1
    for m in range(1, 13):
        qty_col = f"{m}월_수량"
        amt_col = f"{m}월_금액"
        if qty_col in df_2026.columns:
            if df_2026[qty_col].sum() > 0 or df_2026[amt_col].sum() > 0:
                last_month = m
    return last_month

def forecast_seasonal_index(df_all, target_cols, last_actual_month):
    """
    계절성 지수(Seasonal Index) 기반으로 2026년 전체 실적을 예측합니다.
    """
    # 1. 과거 3개년(23, 24, 25) 데이터 추출
    df_past = df_all[df_all['연도'].isin([2023, 2024, 2025])]
    if df_past.empty:
        return pd.DataFrame()
        
    # 과거 월별 평균 비중 산출
    monthly_shares = []
    for y in df_past['연도'].unique():
        df_y = df_past[df_past['연도'] == y]
        y_total_qty = df_y['년계_수량'].sum()
        y_total_amt = df_y['년계_금액'].sum()
        
        if y_total_qty == 0 or y_total_amt == 0:
            continue
            
        shares_y = {}
        for m in range(1, 13):
            m_qty = df_y[f"{m}월_수량"].sum()
            m_amt = df_y[f"{m}월_금액"].sum()
            shares_y[f"{m}월_수량_지수"] = m_qty / y_total_qty
            shares_y[f"{m}월_금액_지수"] = m_amt / y_total_amt
        monthly_shares.append(shares_y)
        
    if not monthly_shares:
        return pd.DataFrame()
        
    # 월별 지수 평균 계산
    df_shares = pd.DataFrame(monthly_shares)
    seasonal_index = df_shares.mean().to_dict()
    
    # 2. 2026년 데이터 처리
    df_2026 = df_all[df_all['연도'] == 2026]
    if df_2026.empty:
        return pd.DataFrame()
        
    # 2026년 실제 집계 누적치 계산 (1월 ~ last_actual_month)
    actual_qty_sum = 0
    actual_amt_sum = 0
    actual_share_qty_sum = 0
    actual_share_amt_sum = 0
    
    for m in range(1, last_actual_month + 1):
        actual_qty_sum += df_2026[f"{m}월_수량"].sum()
        actual_amt_sum += df_2026[f"{m}월_금액"].sum()
        actual_share_qty_sum += seasonal_index.get(f"{m}월_수량_지수", 1/12)
        actual_share_amt_sum += seasonal_index.get(f"{m}월_금액_지수", 1/12)
        
    # 연간 추정치 산출
    est_total_qty = (actual_qty_sum / actual_share_qty_sum) if actual_share_qty_sum > 0 else 0
    est_total_amt = (actual_amt_sum / actual_share_amt_sum) if actual_share_amt_sum > 0 else 0
    
    # 3. 12개월 예측치 분배 및 실제값 오버라이드
    results = []
    for m in range(1, 13):
        # 예측값 계산
        pred_qty = est_total_qty * seasonal_index.get(f"{m}월_수량_지수", 1/12)
        pred_amt = est_total_amt * seasonal_index.get(f"{m}월_금액_지수", 1/12)
        
        # 실제 데이터가 있는 월은 실제값으로 대체
        is_actual = (m <= last_actual_month)
        if is_actual:
            qty_val = df_2026[f"{m}월_수량"].sum()
            amt_val = df_2026[f"{m}월_금액"].sum()
        else:
            qty_val = pred_qty
            amt_val = pred_amt
            
        results.append({
            '월': f"{m}월",
            '수량': qty_val,
            '금액': amt_val,
            '구분': '실제 실적' if is_actual else '예측(계절성 지수)'
        })
        
    return pd.DataFrame(results)

def forecast_prophet(df_all, last_actual_month):
    """
    Facebook Prophet 시계열 모델을 학습시켜 2026년 말까지 물량을 예측합니다.
    """
    # 1. 시계열 데이터 가공 (23년 1월 ~ 26년 last_actual_month까지의 월별 실제 데이터)
    time_series_data = []
    
    # 전체 연도의 월별 실제 실적만 추려내기
    for y in sorted(df_all['연도'].unique()):
        df_y = df_all[df_all['연도'] == y]
        limit_m = last_actual_month if y == 2026 else 12
        
        for m in range(1, limit_m + 1):
            m_qty = df_y[f"{m}월_수량"].sum()
            m_amt = df_y[f"{m}월_금액"].sum()
            
            # 날짜형 ds 컬럼 생성 (각 월의 1일 기준)
            ds_str = f"{y}-{m:02d}-01"
            time_series_data.append({
                'ds': pd.to_datetime(ds_str),
                'qty': m_qty,
                'amt': m_amt
            })
            
    df_ts = pd.DataFrame(time_series_data)
    if len(df_ts) < 12:
        # 데이터가 너무 적으면 Prophet 학습이 안 되므로 빈 DataFrame 리턴
        return pd.DataFrame()
        
    # 2. 수량(Quantity) 예측 모델 학습 및 예측
    df_qty = df_ts[['ds', 'qty']].rename(columns={'qty': 'y'})
    m_qty = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    m_qty.fit(df_qty)
    
    # 2026년 12월 말까지의 월 단위 날짜 생성
    future_qty = m_qty.make_future_dataframe(periods=12 - last_actual_month, freq='MS')
    forecast_qty = m_qty.predict(future_qty)
    
    # 3. 금액(Amount) 예측 모델 학습 및 예측
    df_amt = df_ts[['ds', 'amt']].rename(columns={'amt': 'y'})
    m_amt = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    m_amt.fit(df_amt)
    
    future_amt = m_amt.make_future_dataframe(periods=12 - last_actual_month, freq='MS')
    forecast_amt = m_amt.predict(future_amt)
    
    # 4. 결과 병합 및 가공
    results = []
    # 2026년 1월 ~ 12월 범위의 예측/실제값 추출
    for m in range(1, 13):
        target_date = pd.to_datetime(f"2026-{m:02d}-01")
        is_actual = (m <= last_actual_month)
        
        # 수량 예측/실제 매칭
        row_q = forecast_qty[forecast_qty['ds'] == target_date]
        if not row_q.empty:
            q_val = df_qty[df_qty['ds'] == target_date]['y'].values[0] if is_actual else max(0, row_q['yhat'].values[0])
            q_lower = max(0, row_q['yhat_lower'].values[0])
            q_upper = max(0, row_q['yhat_upper'].values[0])
        else:
            q_val, q_lower, q_upper = 0, 0, 0
            
        # 금액 예측/실제 매칭
        row_a = forecast_amt[forecast_amt['ds'] == target_date]
        if not row_a.empty:
            a_val = df_amt[df_amt['ds'] == target_date]['y'].values[0] if is_actual else max(0, row_a['yhat'].values[0])
            a_lower = max(0, row_a['yhat_lower'].values[0])
            a_upper = max(0, row_a['yhat_upper'].values[0])
        else:
            a_val, a_lower, a_upper = 0, 0, 0
            
        results.append({
            '월': f"{m}월",
            '수량': q_val,
            '수량_최소': q_val if is_actual else q_lower,
            '수량_최대': q_val if is_actual else q_upper,
            '금액': a_val,
            '금액_최소': a_val if is_actual else a_lower,
            '금액_최대': a_val if is_actual else a_upper,
            '구분': '실제 실적' if is_actual else '예측(Prophet ML)'
        })
        
    return pd.DataFrame(results)
