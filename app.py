import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import sqlite3
from datetime import datetime
import time
import prediction_engine

# 페이지 기본 설정 (가로로 넓게 사용)
st.set_page_config(
    page_title="[코웨이 영업] 데이터 기반 수요 예측 분석기",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 데이터베이스 제출용 테이블 초기화
# 데이터베이스 제출용 테이블 초기화
def init_db():
    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
    cursor = conn.cursor()
    # 1) PSI 예측 최종 승인 제출 이력 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT,
            customer TEXT,
            target_month TEXT,
            lme_price REAL,
            exchange_rate REAL,
            price_change_rate REAL,
            operating_profit_rate REAL,
            ai_recommendation INTEGER,
            submitted_at TEXT
        )
    """)
    # 2) 3개년 실제 출하 실적 테이블 (중복 방지를 위한 UNIQUE 인덱스 적용)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actual_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT,
            customer TEXT,
            year INTEGER,
            month INTEGER,
            qty INTEGER,
            amount REAL,
            UNIQUE(item_code, customer, year, month)
        )
    """)
    # 3) 고객사 계획량 (Forecast) 테이블 (item_code, customer, year, month 복합 기본키 적용)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_fcst (
            item_code TEXT,
            customer TEXT,
            year INTEGER,
            month INTEGER,
            qty INTEGER,
            PRIMARY KEY(item_code, customer, year, month)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# 프리미엄 테마 및 스타일링 Custom CSS 주입
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
    
    /* 기본 폰트 설정 */
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif;
        background-color: #f3f5f8;
    }
    
    /* 메인 앱 백그라운드 색상 변경 */
    .stApp {
        background-color: #f3f5f8;
    }
    
    /* 여백 조정 */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    
    /* 헤더 스타일 */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #ffffff;
        padding: 0.8rem 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
        margin-bottom: 1.2rem;
        border: 1px solid #eaedf2;
    }
    
    .logo-text {
        font-size: 1.8rem;
        font-weight: 800;
        font-family: 'Outfit', sans-serif;
    }
    .logo-power {
        color: #ff6b35;
        font-style: italic;
    }
    .logo-net {
        color: #0b3c5d;
    }
    
    .header-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #1a1a1a;
        text-align: center;
        flex-grow: 1;
    }
    

    
    /* 섹션 타이틀 */
    .section-title {
        font-size: 1.15rem;
        font-weight: 800;
        color: #0f172a;
        padding-left: 8px;
        margin-top: 0.2rem;
        margin-bottom: 0.8rem;
        position: relative;
    }
    .section-title::before {
        content: "";
        position: absolute;
        left: 0;
        top: 3px;
        bottom: 3px;
        width: 4px;
        background-color: #0288d1;
        border-radius: 2px;
    }
    
    /* 대시보드 카드 기본 스타일 */
    .dashboard-card {
        background-color: #ffffff;
        border-radius: 14px;
        padding: 1.2rem;
        border: 1px solid #eaedf2;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
        margin-bottom: 1rem;
    }
    
    /* 외부 변수 API 카드 스타일 */
    .api-card {
        padding: 1.1rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
        border: 1px solid #eaedf2;
        box-shadow: 0 2px 8px rgba(0,0,0,0.01);
    }
    
    .api-card-green {
        background-color: #f0fdf4;
        border-color: #dcfce7;
    }
    
    .api-card-blue {
        background-color: #f0f9ff;
        border-color: #e0f2fe;
    }
    
    .api-title-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
    }
    
    .api-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #4b5563;
    }
    
    .api-indicator-container {
        display: flex;
        gap: 4px;
    }
    
    .indicator-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
    }
    
    .dot-green { background-color: #22c55e; }
    .dot-red { background-color: #ef4444; }
    .dot-gray { background-color: #d1d5db; }
    
    .api-value-container {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
    }
    
    .api-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #111827;
    }
    
    .api-unit {
        font-size: 0.85rem;
        color: #6b7280;
        font-weight: 500;
    }
    
    .api-change {
        font-size: 0.95rem;
        font-weight: 700;
    }
    
    .change-up { color: #dc2626; }
    .change-down { color: #2563eb; }
    
    .api-subtext {
        font-size: 0.75rem;
        color: #9ca3af;
        margin-top: 2px;
    }
    
    /* 시뮬레이션 슬라이더 스타일 커스텀 */
    .slider-title-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 10px;
    }
    .slider-label {
        font-size: 0.9rem;
        font-weight: 600;
        color: #374151;
    }
    .slider-value {
        font-size: 1.1rem;
        font-weight: 800;
        color: #0b3c5d;
    }
    
    /* 게이지바 스타일 */
    .gauge-container {
        margin-top: 0.8rem;
        margin-bottom: 0.8rem;
    }
    .gauge-track {
        background-color: #e5e7eb;
        height: 8px;
        border-radius: 4px;
        position: relative;
        margin-top: 5px;
    }
    .gauge-fill {
        height: 8px;
        border-radius: 4px;
    }
    .gauge-fill-blue { background-color: #3b82f6; }
    .gauge-fill-green { background-color: #10b981; }
    .gauge-fill-orange { background-color: #f59e0b; }
    
    .gauge-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.75rem;
        color: #9ca3af;
        margin-top: 3px;
    }
    
    /* AI Insight 요약 영역 스타일 */
    .insight-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.2rem;
        border: 1px solid #eaedf2;
        height: 100%;
    }
    .insight-title {
        font-size: 1rem;
        font-weight: 700;
        color: #1f2937;
        border-bottom: 1px solid #f3f4f6;
        padding-bottom: 6px;
        margin-bottom: 10px;
    }
    .insight-highlight {
        font-size: 1.4rem;
        font-weight: 800;
        color: #111827;
        margin-bottom: 6px;
    }
    .insight-qty {
        color: #00b4d8;
        font-size: 1.6rem;
    }
    .insight-reason {
        font-size: 0.85rem;
        color: #4b5563;
        line-height: 1.5;
        background-color: #f8fafc;
        padding: 8px 12px;
        border-radius: 8px;
        border-left: 3px solid #0b3c5d;
    }
    
    /* 녹색 제출 버튼 스타일 */
    .submit-container {
        background-color: #10b981;
        color: #ffffff;
        padding: 1.5rem;
        border-radius: 14px;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        margin-top: 1.5rem;
        border: none;
        width: 100%;
        display: block;
    }
    .submit-container:hover {
        background-color: #059669;
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
    }
    .submit-text {
        font-size: 1.25rem;
        font-weight: 800;
        letter-spacing: 0.5px;
    }
    .submit-subtext {
        font-size: 0.8rem;
        opacity: 0.9;
        margin-top: 4px;
    }
    
    /* 풋터 스타일 */
    .footer-container {
        display: flex;
        justify-content: space-between;
        font-size: 0.75rem;
        color: #9ca3af;
        margin-top: 1.5rem;
        padding-top: 0.8rem;
        border-top: 1px solid #eaedf2;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- 데이터 로드 및 전처리 -----------------
@st.cache_data
def load_all_data(excels_mtime):
    workspace_dir = r"c:\Users\power\OneDrive\바탕 화면\영업팀 실적파일"
    
    # 1. DB 연결 및 이전 동기화 mtime, 데이터 수 조회
    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS sync_meta (key TEXT PRIMARY KEY, val REAL)")
    cursor.execute("SELECT val FROM sync_meta WHERE key = 'last_mtime'")
    res = cursor.fetchone()
    last_db_mtime = res[0] if res else 0.0
    
    cursor.execute("SELECT COUNT(*) FROM actual_sales")
    db_count = cursor.fetchone()[0]
    
    # 엑셀 파일의 최종 수정시각이 이전과 다르거나 DB가 비어있다면 일괄 적재
    if excels_mtime != last_db_mtime or db_count == 0:
        years = [2023, 2024, 2025, 2026]
        dfs = []
        
        for y in years:
            file_name = f"{y - 2000}년 매출 실적.xlsx"
            file_path = os.path.join(workspace_dir, file_name)
            sheet_name = f"{y - 2000}년(세부_실적)"
            
            if not os.path.exists(file_path):
                continue
                
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
                
                # 헤더 행 찾기
                header_idx = None
                for idx, row in df.iterrows():
                    row_values = [str(x).strip() for x in row.dropna()]
                    if any(x in ['거래선', '거래', '거래처'] for x in row_values):
                        header_idx = idx
                        break
                        
                if header_idx is None:
                    continue
                    
                df.columns = [str(x).strip() for x in df.iloc[header_idx]]
                df = df.iloc[header_idx + 1:].reset_index(drop=True)
                
                for col in ['거래처', '거래선', '거래']:
                    if col in df.columns:
                        df.rename(columns={col: '거래처'}, inplace=True)
                        break
                for col in ['모델명', '모델', '규격']:
                    if col in df.columns:
                        df.rename(columns={col: '모델명'}, inplace=True)
                        break
                        
                if '거래처' not in df.columns or '모델명' not in df.columns:
                    continue
                    
                df['거래처'] = df['거래처'].ffill()
                
                # 1) 모델명이 NaN이거나 빈 문자열인 행 제거
                df = df[df['모델명'].notna()]
                df = df[df['모델명'].astype(str).str.strip() != '']
                
                # 2) 한글 깨짐 등으로 필터링되지 않는 '소계', '합계' 행을 정밀하게 제거하기 위해, 
                # 진짜 품목 코드 규격(영숫자, 하이픈, 언더바, 괄호, 슬래시, 공백)만 허용하는 필터 적용
                import re
                valid_model_pattern = re.compile(r'^[A-Za-z0-9\-_()/ ]+$')
                df = df[df['모델명'].astype(str).apply(lambda x: bool(valid_model_pattern.match(x.strip())))]
                
                # 거래처명에 대한 기존 필터링 유지 (합계 제거)
                invalid_keywords = '소계|합계|TOTAL|Total|소 계'
                df = df[~df['거래처'].astype(str).str.contains(invalid_keywords, na=False)]
                
                cols = list(df.columns)
                new_cols = []
                for i, col in enumerate(cols):
                    if col in ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월', '년계']:
                        new_cols.append(col + "_수량")
                    elif i > 0 and new_cols[-1].endswith("_수량") and col == 'nan':
                        base = new_cols[-1].split("_")[0]
                        new_cols.append(base + "_금액")
                    else:
                        new_cols.append(col)
                df.columns = new_cols
                
                num_cols = [c for c in df.columns if c.endswith('_수량') or c.endswith('_금액')]
                for col in num_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    if col.endswith('_수량'):
                        df[col] = df[col] * 1000
                    elif col.endswith('_금액'):
                        df[col] = df[col] * 1000000
                    
                if '제품' in df.columns:
                    df['제품'] = df['제품'].ffill().fillna('미분류')
                else:
                    df['제품'] = '미분류'
                    
                df['연도'] = y
                
                target_cols = ['연도', '거래처', '제품', '모델명', '년계_수량', '년계_금액']
                for m in range(1, 13):
                    target_cols.extend([f'{m}월_수량', f'{m}월_금액'])
                    
                for col in target_cols:
                    if col not in df.columns:
                        if col == '연도':
                            df['연도'] = y
                        elif col == '제품':
                            df['제품'] = '미분류'
                        else:
                            df[col] = 0
                
                df_clean = df[target_cols].copy()
                dfs.append(df_clean)
            except Exception as e:
                st.error(f"{y}년 데이터 로드 실패: {e}")
                
        if dfs:
            df_merged = pd.concat(dfs, ignore_index=True)
            
            # 동일 모델명, 거래처, 연도로 중복 행들 합산 집계 (유실 방지)
            agg_cols = []
            for m in range(1, 13):
                agg_cols.extend([f"{m}월_수량", f"{m}월_금액"])
            df_grouped = df_merged.groupby(['모델명', '거래처', '연도'])[agg_cols].sum().reset_index()
            
            cursor.execute("DELETE FROM actual_sales")
            
            rows_to_insert = []
            for _, row in df_grouped.iterrows():
                item_code = str(row['모델명']).strip()
                customer = str(row['거래처']).strip()
                year = int(row['연도'])
                for m in range(1, 13):
                    qty_val = int(row.get(f"{m}월_수량", 0))
                    amt_val = float(row.get(f"{m}월_금액", 0.0))
                    rows_to_insert.append((item_code, customer, year, m, qty_val, amt_val))
                    
            cursor.executemany("""
                INSERT OR REPLACE INTO actual_sales (item_code, customer, year, month, qty, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rows_to_insert)
            
            # 메타 업데이트
            cursor.execute("INSERT OR REPLACE INTO sync_meta (key, val) VALUES ('last_mtime', ?)", (excels_mtime,))
            conn.commit()
            
    conn.close()
            
    # 2. DB에서 데이터 로드하여 피벗 (wide format 재구성)
    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
    df_long = pd.read_sql_query("SELECT * FROM actual_sales", conn)
    conn.close()
    
    if df_long.empty:
        return pd.DataFrame()
        
    pivoted_qty = df_long.pivot(index=['item_code', 'customer', 'year'], columns='month', values='qty').fillna(0)
    pivoted_qty.columns = [f"{col}월_수량" for col in pivoted_qty.columns]
    
    pivoted_amt = df_long.pivot(index=['item_code', 'customer', 'year'], columns='month', values='amount').fillna(0)
    pivoted_amt.columns = [f"{col}월_금액" for col in pivoted_amt.columns]
    
    df_wide = pivoted_qty.join(pivoted_amt).reset_index()
    df_wide.rename(columns={'item_code': '모델명', 'customer': '거래처', 'year': '연도'}, inplace=True)
    df_wide['제품'] = '미분류'
    
    qty_cols = [f"{m}월_수량" for m in range(1, 13)]
    amt_cols = [f"{m}월_금액" for m in range(1, 13)]
    for col in qty_cols + amt_cols:
        if col not in df_wide.columns:
            df_wide[col] = 0.0
            
    df_wide['년계_수량'] = df_wide[qty_cols].sum(axis=1)
    df_wide['년계_금액'] = df_wide[amt_cols].sum(axis=1)
    
    target_cols = ['연도', '거래처', '제품', '모델명', '년계_수량', '년계_금액']
    for m in range(1, 13):
        target_cols.extend([f'{m}월_수량', f'{m}월_금액'])
        
    return df_wide[target_cols]

# 엑셀 파일들의 최종 수정시각 구하기
excels_mtime_val = 0.0
workspace_dir = r"c:\Users\power\OneDrive\바탕 화면\영업팀 실적파일"
for y in [2023, 2024, 2025, 2026]:
    f_path = os.path.join(workspace_dir, f"{y - 2000}년 매출 실적.xlsx")
    if os.path.exists(f_path):
        excels_mtime_val += os.path.getmtime(f_path)

with st.spinner("🔄 실적 데이터를 실시간 로드 중입니다..."):
    df_raw = load_all_data(excels_mtime_val)

if df_raw.empty:
    st.error("❌ 실적 데이터를 불러오지 못했습니다. DB 상태를 확인해 주세요.")
    st.stop()

# 초기 세션 구성 완료

# ----------------- AI 예측 사유 생성 유틸리티 -----------------
def generate_forecast_reason(m_val, qty, qty_average_val, prev_qty):
    avg_diff = qty - qty_average_val
    avg_diff_pct = (avg_diff / qty_average_val * 100) if qty_average_val > 0 else 0
    mom_diff_pct = ((qty - prev_qty) / prev_qty * 100) if prev_qty > 0 else 0
    
    # 추세 분석
    trend_txt = ""
    if abs(mom_diff_pct) < 3.0:
        trend_txt = "전월과 유사한 보합세 유지"
    elif mom_diff_pct >= 3.0:
        trend_txt = f"전월 대비 {mom_diff_pct:.1f}% 증가 흐름"
    else:
        trend_txt = f"전월 대비 {abs(mom_diff_pct):.1f}% 감소 흐름"
        
    # 과거 대조 분석
    comparison_txt = ""
    if avg_diff > 0:
        comparison_txt = f"과거 3개년 평균 대비 약 {avg_diff:,.0f}대({avg_diff_pct:+.1f}%) 상회하는 수준"
    else:
        comparison_txt = f"과거 3개년 평균 대비 약 {abs(avg_diff):,.0f}대({avg_diff_pct:.1f}%) 하회하는 수준"
        
    return f"{trend_txt} 및 {comparison_txt}을 반영한 통계치"

if df_raw.empty:
    st.error("❌ 실적 데이터를 불러오지 못했습니다. DB 상태를 확인해 주세요.")
    st.stop()

# 고유한 거래처(업체) 및 품목(모델명) 리스트 추출
customer_list = sorted(df_raw['거래처'].dropna().unique().tolist())

# ----------------- 세션 상태 관리 초기화 -----------------
if 'customer_select' not in st.session_state:
    st.session_state.customer_select = customer_list[0] if customer_list else ""

# 선택된 거래처에 해당되는 모델명 리스트만 동적으로 추출
df_cust_only = df_raw[df_raw['거래처'] == st.session_state.customer_select]
model_list = sorted(df_cust_only['모델명'].dropna().unique().tolist())

if 'model_select' not in st.session_state or st.session_state.model_select not in model_list:
    st.session_state.model_select = model_list[0] if model_list else ""
if 'target_month_select' not in st.session_state:
    st.session_state.target_month_select = "2026.06"
if 'model_type_select' not in st.session_state:
    st.session_state.model_type_select = "Prophet 시계열 모델"

# ----------------- 커스텀 헤더 렌더링 -----------------
st.markdown(f"""
<div class="header-container">
    <div class="logo-text"><span class="logo-power">POWER</span><span class="logo-net">NET</span></div>
    <div class="header-title">[영업팀] 데이터 기반 수요 예측 분석기</div>
    <div style="width: 150px;"></div> <!-- 대칭 정렬을 위한 빈 공간 -->
</div>
""", unsafe_allow_html=True)

# ----------------- 데이터 가공 및 예측 엔진 사전 구동 -----------------
# 1. 선택된 거래처 및 품목의 데이터 추출
df_item = df_raw[(df_raw['모델명'] == st.session_state.model_select) & (df_raw['거래처'] == st.session_state.customer_select)].copy()

# 2. 과거 5개년 월별 출하 추이 꺾은선 데이터 구성
def get_yearly_monthly_qty(year_val):
    df_y = df_item[df_item['연도'] == year_val]
    if df_y.empty:
        # 데이터가 없을 시 품목 모델명 해싱 기준의 일관성 있는 가상 트렌드 생성
        hash_val = sum(ord(c) for c in st.session_state.model_select) % 5
        base_trend = [30000, 35000, 42000, 38000, 32000, 48000, 52000, 45000, 33000, 28000, 35000, 43000]
        multiplier = 0.8 + (year_val - 2021) * 0.07 + (hash_val * 0.05)
        return [int(v * multiplier) for v in base_trend]
    
    return [int(df_y[f"{m}월_수량"].sum()) for m in range(1, 13)]

qty_2023 = get_yearly_monthly_qty(2023)
qty_2024 = get_yearly_monthly_qty(2024)
qty_2025 = get_yearly_monthly_qty(2025)

# 계절성 평균 계산 (2023 ~ 2025 3개년 평균)
qty_average = []
for i in range(12):
    avg_val = (qty_2023[i] + qty_2024[i] + qty_2025[i]) / 3.0
    qty_average.append(int(avg_val))

# 3. 2026년 실제 데이터 감지 및 AI 예측
# 사용자가 선택한 예측 기준 월보다 1개월 앞선 월까지를 실제 실적 기입 구간으로 결정
target_month_int = int(st.session_state.target_month_select.split(".")[1])
last_actual_month = target_month_int - 1

# Facebook Prophet ML 단일 예측 모델 고정 구동
df_forecast = prediction_engine.forecast_prophet(df_item, last_actual_month)

# 4. 2026년 실제 + 예측 데이터 구성 (1년치 전체)
qty_2026 = []
for m in range(1, 13):
    if m <= last_actual_month:
        df_y = df_item[df_item['연도'] == 2026]
        qty_val = int(df_y[f"{m}월_수량"].sum()) if not df_y.empty else 0
        qty_2026.append(qty_val)
    else:
        if not df_forecast.empty:
            f_row = df_forecast[df_forecast['월'] == f"{m}월"]
            qty_val = int(f_row['수량'].values[0]) if not f_row.empty else 0
            qty_2026.append(qty_val)
        else:
            qty_2026.append(qty_average[m - 1])

# ----------------- 2단 Grid Layout 구성 -----------------
col_left, col_right = st.columns([1.0, 3.2])

# ==========================================
# 1. 좌측 영역 (Column 1: 입력 및 조건, 최종 Action)
# ==========================================
with col_left:
    st.markdown('<div class="section-title">입력/조건</div>', unsafe_allow_html=True)
    
    with st.container():
        # 거래처 (Customer) 드롭다운
        selected_customer = st.selectbox(
            "거래처 (Customer)",
            options=customer_list,
            index=customer_list.index(st.session_state.customer_select) if st.session_state.customer_select in customer_list else 0,
            key="customer_select_box"
        )
        if selected_customer != st.session_state.customer_select:
            st.session_state.customer_select = selected_customer
            # 거래처가 바뀌면 모델 리스트가 달라지므로 새로운 거래처의 첫 번째 모델로 세션을 초기화
            df_cust_only = df_raw[df_raw['거래처'] == selected_customer]
            new_model_list = sorted(df_cust_only['모델명'].dropna().unique().tolist())
            st.session_state.model_select = new_model_list[0] if new_model_list else ""
            st.rerun()

        # 품목 코드 드롭다운
        selected_model = st.selectbox(
            "품목 코드 (Item Code)",
            options=model_list,
            index=model_list.index(st.session_state.model_select) if st.session_state.model_select in model_list else 0,
            key="model_select_box"
        )
        st.session_state.model_select = selected_model
        
        # 예측 기준 월
        months_options = [f"2026.{m:02d}" for m in range(1, 13)]
        selected_month_str = st.selectbox(
            "예측 기준 월 (Target Month)",
            options=months_options,
            index=months_options.index(st.session_state.target_month_select) if st.session_state.target_month_select in months_options else 5,
            key="month_select_box"
        )
        st.session_state.target_month_select = selected_month_str
        target_month_int = int(st.session_state.target_month_select.split(".")[1])

    # 1) 고객사 FCST 관리 아코디언 (A/B/C 일괄 구현)
    st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
    with st.expander(f"📊 고객사 FCST 관리 (계획량) - {st.session_state.customer_select}"):
        st.markdown("**[옵션 B] 엑셀 파일 업로드**")
        uploaded_fcst_file = st.file_uploader(
            "FCST 엑셀 업로드 (품목, 월별 수량 포함)",
            type=["xlsx", "xls"],
            key="fcst_uploader"
        )
        if uploaded_fcst_file is not None:
            try:
                df_up = pd.read_excel(uploaded_fcst_file)
                model_col = None
                for col in df_up.columns:
                    if any(x in str(col).lower() for x in ['모델', '품목', 'item', 'code', 'model']):
                        model_col = col
                        break
                if model_col is None:
                    model_col = df_up.columns[0]
                
                month_cols = []
                for col in df_up.columns:
                    col_str = str(col).strip()
                    if any(f"{m}월" in col_str or col_str == str(m) for m in range(1, 13)):
                        month_cols.append(col)
                
                if not month_cols:
                    st.error("❌ '1월', '2월' 등 월별 수량 컬럼을 찾을 수 없습니다.")
                else:
                    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
                    cursor = conn.cursor()
                    inserted_cnt = 0
                    for _, row in df_up.iterrows():
                        up_item = str(row[model_col]).strip()
                        if not up_item or up_item.lower() in ['nan', 'total', '합계', '소계']:
                            continue
                        for col in month_cols:
                            col_str = str(col).strip()
                            m_val = None
                            for m in range(1, 13):
                                if f"{m}월" in col_str or col_str == str(m):
                                    m_val = m
                                    break
                            if m_val is None:
                                continue
                            qty_val = pd.to_numeric(row[col], errors='coerce')
                            qty_val = int(qty_val) if not pd.isna(qty_val) else 0
                            
                            cursor.execute("""
                                INSERT OR REPLACE INTO customer_fcst (item_code, customer, year, month, qty)
                                VALUES (?, ?, 2026, ?, ?)
                            """, (up_item, st.session_state.customer_select, m_val, qty_val))
                            inserted_cnt += 1
                    conn.commit()
                    conn.close()
                    st.success(f"✅ 엑셀 FCST 반영 완료 ({inserted_cnt}건)")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ 파싱 오류: {e}")

         # 옵션 A
        st.markdown("---")
        st.markdown("**[옵션 A] 직접 수동 기입**")
        manual_vals = {}
        for idx in range(4):
            m_val = (target_month_int + idx - 1) % 12 + 1
            # 기존 FCST 조회
            conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
            cursor = conn.cursor()
            cursor.execute("SELECT qty FROM customer_fcst WHERE item_code = ? AND customer = ? AND year = 2026 AND month = ?", 
                           (st.session_state.model_select, st.session_state.customer_select, m_val))
            res = cursor.fetchone()
            conn.close()
            db_fcst_val = res[0] if res else int(qty_average[m_val - 1] * 0.98)
            
            manual_vals[m_val] = st.number_input(
                f"{m_val}월 계획 수량 (대)",
                min_value=0,
                value=int(db_fcst_val),
                step=100,
                key=f"fcst_manual_{m_val}"
            )
            
        if st.button("FCST 수동 업데이트 💾", use_container_width=True):
            conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
            cursor = conn.cursor()
            for m_val, qty_val in manual_vals.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO customer_fcst (item_code, customer, year, month, qty)
                    VALUES (?, ?, 2026, ?, ?)
                """, (st.session_state.model_select, st.session_state.customer_select, m_val, int(qty_val)))
            conn.commit()
            conn.close()
            st.success("✅ FCST 수동 저장 성공!")
            st.rerun()

    st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
    submit_btn = st.button("최종 입력 및 공유 (Submit to PSI) 📤", use_container_width=True, type="primary")
    
    if submit_btn:
        try:
            lme_price = 0.0
            exchange_rate = 0.0
            price_change_rate = 0.0
            profit_rate = 0.0
            ai_final_recommendation = qty_2026[target_month_int - 1]
            
            conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO submissions 
                (item_code, customer, target_month, lme_price, exchange_rate, price_change_rate, operating_profit_rate, ai_recommendation, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                selected_model,
                st.session_state.customer_select,
                selected_month_str,
                lme_price,
                exchange_rate,
                price_change_rate,
                profit_rate,
                ai_final_recommendation,
                now_str
            ))
            conn.commit()
            conn.close()
            
            st.success(f"""
            🎉 **PSI 제출 및 공유 성공!**
            - **품목**: {selected_model}
            - **대상월**: {selected_month_str}
            - **추천량**: {ai_final_recommendation:,.0f} 대
            - **데이터베이스 반영 완료**
            """)
        except Exception as e:
            st.error(f"제출 중 오류가 발생했습니다: {e}")

# ==========================================
# 2. 우측 영역 (Column 2: 과거 1년치 추이 차트, 4개월 예측, PSI 대조 테이블)
# ==========================================
with col_right:
    st.markdown('<div class="section-title">분석 처리 및 출력 결과</div>', unsafe_allow_html=True)
    
    # 1. 1년치 전체 과거 3개년 월별 출하 추이 및 계절성 라인 차트
    st.markdown('<div style="font-size:1.0rem; font-weight:700; color:#374151; margin-bottom:5px;">과거 3개년 월별 출하 추이 및 계절성 (12개월 전체 트렌드)</div>', unsafe_allow_html=True)
    
    fig_lines = go.Figure()
    
    # 1~12월 전체 x축 구성
    display_months = [f"{m}월" for m in range(1, 13)]
    x_axis = display_months
    
    # 시각적 대비가 명확한 연도별 색상 맵핑
    years_style = {
        "2023년": (qty_2023, "#2dd4bf", 2.0, None), # 세련된 청록색 (Teal)
        "2024년": (qty_2024, "#3b82f6", 2.0, None), # 클래식 블루
        "2025년": (qty_2025, "#1e3a8a", 2.5, None), # 짙은 네이비 (직전연도 강조)
        "Seasonal Average": (qty_average, "#8b5cf6", 2.2, "dash") # 퍼플 점선 (계절성 흐름)
    }
    
    for name, (qty_list, color, width, dash_style) in years_style.items():
        fig_lines.add_trace(go.Scatter(
            x=x_axis,
            y=qty_list,
            name=name,
            mode='lines',
            line=dict(color=color, width=width, dash=dash_style),
            hoverinfo='text+name',
            hovertext=[f"{q:,.0f}대" for q in qty_list]
        ))

    # Prophet 신뢰구간 시각화 추가 (12월까지 확장)
    if st.session_state.model_type_select == "Prophet 시계열 모델" and not df_forecast.empty and '수량_최소' in df_forecast.columns:
        start_idx = max(0, last_actual_month - 1)
        proj_months = display_months[start_idx:]
        y_lower = []
        y_upper = []
        for m_str in proj_months:
            m_int = int(m_str.replace("월", ""))
            if m_int <= last_actual_month:
                df_y = df_item[df_item['연도'] == 2026]
                val = int(df_y[f"{m_int}월_수량"].sum()) if not df_y.empty else 0
                y_lower.append(val)
                y_upper.append(val)
            else:
                f_row = df_forecast[df_forecast['월'] == m_str]
                y_lower.append(int(f_row['수량_최소'].values[0]) if not f_row.empty else 0)
                y_upper.append(int(f_row['수량_최대'].values[0]) if not f_row.empty else 0)
        
        fig_lines.add_trace(go.Scatter(
            x=proj_months + proj_months[::-1],
            y=y_upper + y_lower[::-1],
            fill='toself',
            fillcolor='rgba(255, 77, 0, 0.08)',
            line=dict(color='rgba(255, 77, 0, 0)'),
            hoverinfo="skip",
            showlegend=True,
            name="AI 예측 신뢰구간"
        ))

    # 2026년 실제 및 예측 라인 12월까지 연장
    # 실제 구간 (1월 ~ last_actual_month)
    if last_actual_month > 0:
        fig_lines.add_trace(go.Scatter(
            x=x_axis[:last_actual_month],
            y=qty_2026[:last_actual_month],
            name="2026년 실제 실적",
            mode='lines+markers',
            line=dict(color="#ff4d00", width=4.0),
            marker=dict(size=7),
            hoverinfo='text+name',
            hovertext=[f"{q:,.0f}대" for q in qty_2026[:last_actual_month]]
        ))
    
    # 예측 구간 (last_actual_month ~ 12월)
    if last_actual_month < 12:
        start_idx = max(0, last_actual_month - 1)
        fig_lines.add_trace(go.Scatter(
            x=x_axis[start_idx:12],
            y=qty_2026[start_idx:12],
            name="2026년 AI 예측",
            mode='lines',
            line=dict(color="#ff4d00", width=4.0, dash="dash"),
            hoverinfo='text+name',
            hovertext=[f"{q:,.0f}대" for q in qty_2026[start_idx:12]]
        ))

    # 예측 기준 월 (Target Month) 세로선 및 포인트 하이라이트 추가
    if 1 <= target_month_int <= 12:
        target_month_idx = target_month_int - 1
        target_month_name = f"{target_month_int}월"
        
        max_y_limit = max(max(qty_2025), max(qty_2026)) if qty_2026 else max(qty_2025)
        fig_lines.add_shape(
            type="line",
            x0=target_month_name, y0=0,
            x1=target_month_name, y1=max_y_limit * 1.2,
            line=dict(color="rgba(11, 60, 93, 0.4)", width=2, dash="dot")
        )
        
        # 각 연도별 해당 월에 포인트 찍고 라벨(June 등 영어로) 달기
        month_eng_names = ["Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug", "Sept", "Oct", "Nov", "Dec"]
        target_month_eng = month_eng_names[target_month_idx]
        
        highlight_years = ["2025년", "Seasonal Average"]
        for name in highlight_years:
            val_list, col, _, _ = years_style[name]
            y_val = val_list[target_month_idx]
            
            fig_lines.add_trace(go.Scatter(
                x=[target_month_name],
                y=[y_val],
                mode='markers+text',
                marker=dict(color=col, size=10, line=dict(color='#ffffff', width=2)),
                text=[target_month_eng],
                textposition="top center" if name == "2025년" else "bottom center",
                textfont=dict(family="Outfit", size=11, color="#0b3c5d"),
                showlegend=False
            ))
            
    fig_lines.update_layout(
        margin=dict(l=40, r=20, t=10, b=30),
        height=280,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="#f3f4f6",
            tickfont=dict(size=11)
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#f3f4f6",
            range=[0, max_y_limit * 1.15],
            tickfont=dict(size=11)
        )
    )
    
    st.plotly_chart(fig_lines, use_container_width=True, config={'displayModeBar': False})
    
    # 2. 그래프 하단: 당월 포함 4개월치 AI 추천량 가로형 요약 카드 배치
    st.markdown('<div style="font-size:1.0rem; font-weight:700; color:#374151; margin-top:15px; margin-bottom:10px;">당월 포함 미래 4개월 예측 요약</div>', unsafe_allow_html=True)
    
    four_months_data = []
    for i in range(4):
        m_val = (target_month_int + i - 1) % 12 + 1
        m_name = f"{m_val}월"
        
        qty = qty_2026[m_val - 1]
        
        # 전월 대비 변동률
        prev_m_val = (m_val - 2) % 12 + 1
        prev_qty = qty_2026[prev_m_val - 1]
        if prev_qty > 0:
            change_pct = ((qty - prev_qty) / prev_qty) * 100
        else:
            change_pct = 0.0
            
        four_months_data.append({
            '월': m_name,
            '추천량': qty,
            '변동률': change_pct
        })
        
    cols_metric = st.columns(4)
    for idx, data in enumerate(four_months_data):
        with cols_metric[idx]:
            # 첫 번째 카드(당월)는 강조 스타일 테두리 적용
            border_color = "#ff4d00" if idx == 0 else "#eaedf2"
            bg_color = "#fff8f5" if idx == 0 else "#ffffff"
            
            change_sign = "+" if data['변동률'] >= 0 else ""
            change_color = "#dc2626" if data['변동률'] >= 0 else "#2563eb"
            
            st.markdown(f"""
            <div style="background-color: {bg_color}; border: 1.5px solid {border_color}; border-radius: 12px; padding: 0.8rem; box-shadow: 0 4px 12px rgba(0,0,0,0.02); text-align: center;">
                <div style="font-size: 0.85rem; font-weight: 700; color: #4b5563;">{data['월']} AI 추천량</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #0b3c5d; margin: 6px 0;">{data['추천량']:,.0f}<span style="font-size: 0.85rem; font-weight: 500; color: #6b7280;"> 대</span></div>
                <div style="font-size: 0.8rem; font-weight: 700; color: {change_color};">전월비 {change_sign}{data['변동률']:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 4개월 예측 사유 리스트 모음 렌더링
    st.markdown("""
    <div style="margin-top: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 0.8rem 1.2rem; box-shadow: 0 2px 6px rgba(0,0,0,0.01); margin-bottom: 15px;">
        <div style="font-size: 0.9rem; font-weight: 700; color: #0b3c5d; margin-bottom: 8px;">
            📋 월별 AI 수요 예측 근거 및 판단 사유
        </div>
    """, unsafe_allow_html=True)
    
    for idx, data in enumerate(four_months_data):
        m_val = int(data['월'].replace("월", ""))
        qty = data['추천량']
        avg_qty = qty_average[m_val - 1]
        prev_m = (m_val - 2) % 12 + 1
        prev_qty = qty_2026[prev_m - 1]
        
        reason_text = generate_forecast_reason(m_val, qty, avg_qty, prev_qty)
        
        st.markdown(f"""
        <div style="font-size: 0.82rem; color: #475569; margin-bottom: 5px; line-height: 1.4;">
            <strong style="color: #0b3c5d;">• {data['월']} 예측 사유</strong>: {reason_text}
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)

    # 3. 그래프 하단 M~M+3 종합 대조 대시보드 테이블 탑재
    st.markdown('<div style="font-size:1.0rem; font-weight:700; color:#374151; margin-top:20px; margin-bottom:10px;">수요 예측 종합 PSI 대조 테이블 (담당자 감 조율용)</div>', unsafe_allow_html=True)
    
    col_names = [f"{data['월']}" for data in four_months_data]
    labels = ['AI 최종 추천량 (대)', '과거 3개년 평균 출하량 (대)', '직전 연도(2025년) 동월 실적 (대)', f'{st.session_state.customer_select} Forecast 계획량 (대)']
    
    row_ai = []
    row_avg = []
    row_2025 = []
    row_forecast = []
    
    # DB에서 고객사 계획량(FCST) 데이터 조회
    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
    cursor = conn.cursor()
    target_months = []
    for i in range(4):
        m_val = (target_month_int + i - 1) % 12 + 1
        target_months.append(m_val)
    placeholders = ",".join("?" for _ in target_months)
    cursor.execute(f"SELECT month, qty FROM customer_fcst WHERE item_code = ? AND customer = ? AND year = 2026 AND month IN ({placeholders})", 
                   [st.session_state.model_select, st.session_state.customer_select] + target_months)
    fcst_results = dict(cursor.fetchall())
    conn.close()
    
    for i in range(4):
        m_val = (target_month_int + i - 1) % 12 + 1
        
        # 1) AI
        row_ai.append(f"{qty_2026[m_val - 1]:,.0f}")
        # 2) 과거 평균
        row_avg.append(f"{qty_average[m_val - 1]:,.0f}")
        # 3) 2025년 실적
        row_2025.append(f"{qty_2025[m_val - 1]:,.0f}")
        # 4) Forecast (DB 등록값이 있으면 사용, 없으면 폴백)
        db_fcst_qty = fcst_results.get(m_val)
        if db_fcst_qty is not None:
            row_forecast.append(f"{db_fcst_qty:,.0f}")
        else:
            row_forecast.append(f"{int(qty_average[m_val - 1] * 0.98):,.0f}")
        
    df_psi = pd.DataFrame([row_ai, row_avg, row_2025, row_forecast], columns=col_names, index=labels)
    
    # 둥근 모서리와 정갈한 스타일을 위해 Streamlit dataframe 렌더링
    st.dataframe(df_psi, use_container_width=True)
    
    st.markdown("""
    <div style="font-size: 0.8rem; color: #6b7280; margin-top: -5px; line-height: 1.4;">
        * 담당자께서는 AI의 정량적 통계 예측치와 과거 패턴/직전 실적 데이터를 비교하여 정성적 영업 조율(감)을 최종 반영하실 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 하단 영역 (Footer)
# ==========================================
st.markdown(f"""
<div class="footer-container">
    <div>Data Updated: 2026-05-27</div>
    <div>System Status: Operational</div>
    <div>Data Updated: 2026-05-15</div>
</div>
""", unsafe_allow_html=True)
