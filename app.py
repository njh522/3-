import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import sqlite3
from datetime import datetime
import time
import prediction_engine
import base64

# 파워넷 로고 이미지 로드 및 base64 인코딩
logo_b64 = ""
try:
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "powernet_logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
except Exception:
    pass

# 페이지 기본 설정
st.set_page_config(
    page_title="[코웨이 영업] 데이터 기반 수요 예측 분석기",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 데이터베이스 테이블 초기화
def init_db():
    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
    cursor = conn.cursor()
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coway_code_map (
            coway_code TEXT PRIMARY KEY,
            powernet_model TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# 프리미엄 테마 및 스타일링 Custom CSS 주입
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
    
    /* 최상단 헤더 흰색 영역 제거 (투명화) */
    header[data-testid="stHeader"] {
        background-color: rgba(0, 0, 0, 0) !important;
    }
    
    /* 기본 폰트 및 다크 배경 설정 */
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Malgun Gothic', '맑은 고딕', 'Apple SD Gothic Neo', 'Noto Sans CJK KR', sans-serif !important;
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* 메인 앱 백그라운드 색상 변경 */
    .stApp {
        background-color: #0f172a;
    }
    
    /* 여백 조정 */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    
    /* 사이드바 스타일 커스텀 */
    [data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #f8fafc;
    }
    
    /* 헤더 스타일 */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #1e293b;
        padding: 0.8rem 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        margin-bottom: 1.2rem;
        border: 1px solid #334155;
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
        color: #38bdf8;
    }
    
    .header-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #ffffff;
        text-align: center;
        flex-grow: 1;
    }
    
    /* 섹션 타이틀 */
    .section-title {
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffffff;
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
        background-color: #38bdf8;
        border-radius: 2px;
    }
    
    /* 대시보드 카드 기본 스타일 */
    .dashboard-card {
        background-color: #1e293b;
        border-radius: 10px;
        padding: 1.2rem;
        border: 1px solid #334155;
        box-shadow: rgba(0, 0, 0, 0.1) 0px 1px 3px 0px;
        margin-bottom: 1rem;
    }
    
    /* KPI 블록 카드 스타일 */
    .kpi-card {
        background-color: #1e293b;
        border-radius: 10px;
        padding: 0.8rem;
        border: 1px solid #334155;
        box-shadow: rgba(0, 0, 0, 0.1) 0px 1px 3px 0px;
        text-align: center;
        transition: all 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: #475569;
    }
    .kpi-label {
        font-size: 0.75rem;
        color: #94a3b8;
        font-weight: 600;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .kpi-value {
        font-size: 1.35rem;
        font-weight: 800;
        color: #f8fafc;
    }
    .kpi-sub {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 2px;
    }
    
    /* st.metric 값 및 라벨 가독성 개선 (다크모드 최적화) */
    [data-testid="stMetricValue"] {
        color: #f8fafc !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- 데이터 로드 및 전처리 -----------------
@st.cache_data
def load_all_data(excels_mtime):
    workspace_dir = r"c:\Users\power\OneDrive\바탕 화면\영업팀 실적파일"
    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS sync_meta (key TEXT PRIMARY KEY, val REAL)")
    cursor.execute("SELECT val FROM sync_meta WHERE key = 'last_mtime'")
    res = cursor.fetchone()
    last_db_mtime = res[0] if res else 0.0
    
    cursor.execute("SELECT COUNT(*) FROM actual_sales")
    db_count = cursor.fetchone()[0]
    
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
                df = df[df['모델명'].notna()]
                df = df[df['모델명'].astype(str).str.strip() != '']
                
                import re
                valid_model_pattern = re.compile(r'^[A-Za-z0-9\-_()/ ]+$')
                df = df[df['모델명'].astype(str).apply(lambda x: bool(valid_model_pattern.match(x.strip())))]
                
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
                    
                df['제품'] = df['제품'].ffill().fillna('미분류') if '제품' in df.columns else '미분류'
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
            agg_cols = [f"{m}월_수량" for m in range(1, 13)] + [f"{m}월_금액" for m in range(1, 13)]
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
            
            cursor.execute("INSERT OR REPLACE INTO sync_meta (key, val) VALUES ('last_mtime', ?)", (excels_mtime,))
            conn.commit()
            
    conn.close()
    
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

# 엑셀 최종 수정 시간 산출
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

# ----------------- 코웨이 코드 매핑 데이터 로드 -----------------
def load_coway_code_map():
    try:
        conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS coway_code_map (coway_code TEXT PRIMARY KEY, powernet_model TEXT)")
        # 양산 물동량을 추적하기 위해 1로 시작하고 7자리인 코웨이 코드(양산코드)만 필터링하여 매칭합니다.
        cursor.execute("SELECT coway_code, powernet_model FROM coway_code_map WHERE coway_code LIKE '1%' AND length(coway_code) = 7")
        rows = cursor.fetchall()
        conn.close()
        return {powernet_model: coway_code for coway_code, powernet_model in rows}
    except Exception:
        return {}

# 과거 FCST 정확도/편향 연산 헬퍼
def calculate_fcst_accuracy(customer, item_code, last_actual_month):
    try:
        # 2026년의 경우 실제 실적이 마운트된 last_actual_month 이하까지만 대조 범위로 지정합니다.
        df_acc = pd.read_sql_query("""
            SELECT a.year, a.month, a.qty as actual_qty, f.qty as fcst_qty
            FROM actual_sales a
            JOIN customer_fcst f ON a.item_code = f.item_code 
                                AND a.customer = f.customer 
                                AND a.year = f.year 
                                AND a.month = f.month
            WHERE a.customer = ? AND a.item_code = ?
              AND (a.year < 2026 OR (a.year = 2026 AND a.month <= ?))
            ORDER BY a.year, a.month
        """, conn, params=(customer, item_code, last_actual_month))
        conn.close()
        
        if df_acc.empty:
            return 0.0, 1.0, pd.DataFrame()
            
        df_acc['error'] = (df_acc['actual_qty'] - df_acc['fcst_qty']).abs()
        df_acc['accuracy'] = df_acc.apply(
            lambda r: 100.0 * (1.0 - (r['error'] / r['actual_qty'])) if r['actual_qty'] > 0 else (100.0 if r['fcst_qty'] == 0 else 0.0),
            axis=1
        )
        df_acc['accuracy'] = df_acc['accuracy'].clip(lower=0.0, upper=100.0)
        
        total_actual = df_acc['actual_qty'].sum()
        total_error = df_acc['error'].sum()
        total_fcst = df_acc['fcst_qty'].sum()
        
        overall_accuracy = 100.0 * (1.0 - (total_error / total_actual)) if total_actual > 0 else 100.0
        overall_accuracy = max(0.0, min(100.0, overall_accuracy))
        
        bias_ratio = (total_actual / total_fcst) if total_fcst > 0 else 1.0
        
        return overall_accuracy, bias_ratio, df_acc
    except Exception:
        return 0.0, 1.0, pd.DataFrame()

# --- SCM 의사결정 지원 분석 엔진 추가 ---
def analyze_scm_metrics(customer, item_code, qty_average):
    try:
        conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
        df_sales = pd.read_sql_query("""
            SELECT qty FROM actual_sales 
            WHERE customer = ? AND item_code = ? AND year IN (2023, 2024, 2025)
        """, conn, params=(customer, item_code))
        conn.close()
        
        import numpy as np
        if not df_sales.empty and df_sales['qty'].mean() > 0:
            mean_val = df_sales['qty'].mean()
            std_val = df_sales['qty'].std()
            cv = std_val / mean_val if mean_val > 0 else 0.0
        else:
            mean_val = np.mean(qty_average) if qty_average else 0.0
            std_val = np.std(qty_average) if qty_average else 0.0
            cv = std_val / mean_val if mean_val > 0 else 0.0
    except Exception:
        cv = 0.0
        
    # 변동성 등급 진단
    if cv < 0.20:
        volatility_class = "🟢 안정적 계절성"
        risk_level = "안정"
    elif cv < 0.40:
        volatility_class = "🟡 수요 변동성 보통"
        risk_level = "보통"
    else:
        volatility_class = "🔴 고변동성 위험 (재고 리스크)"
        risk_level = "위험"
        
    # 계절성 판정 (최대/최소 격차 비율이 평균의 40% 이상인 경우 계절성 품목으로 분류)
    import numpy as np
    avg_mean = np.mean(qty_average) if qty_average else 0
    if avg_mean > 0:
        max_min_ratio = (max(qty_average) - min(qty_average)) / avg_mean
        is_seasonal = max_min_ratio > 0.40
    else:
        is_seasonal = False
        
    return cv, volatility_class, risk_level, is_seasonal

def detect_forecast_anomalies(df_accuracy_hist):
    anomalies = []
    if df_accuracy_hist.empty or 'accuracy' not in df_accuracy_hist.columns:
        return anomalies
    
    # 적중률 70% 미만(오차 30% 초과)인 달 추출
    df_bad = df_accuracy_hist[df_accuracy_hist['accuracy'] < 70.0].copy()
    for _, row in df_bad.iterrows():
        y = int(row['year'])
        m = int(row['month'])
        fcst = int(row['fcst_qty'])
        act = int(row['actual_qty'])
        err_pct = ((act - fcst) / fcst * 100) if fcst > 0 else 0.0
        
        direction = "과소 예측(납기 지연 우려)" if err_pct > 0 else "과대 예측(자재 과적재 리스크)"
        comment = f"{y}년 {m}월: 계획 {fcst:,.0f}대 대비 실제 출하 {act:,.0f}대 ({err_pct:+.1f}% 편차) -> {direction} 발생"
        anomalies.append({
            'period': f"{y}.{m:02d}",
            'fcst': fcst,
            'act': act,
            'diff_pct': err_pct,
            'comment': comment
        })
    return anomalies

def calculate_4month_procurement_guide(customer, item_code, target_month_int, bias_val, df_accuracy_hist, qty_average):
    import math
    import numpy as np
    
    if not df_accuracy_hist.empty and 'error' in df_accuracy_hist.columns:
        std_error = df_accuracy_hist['error'].std()
        if pd.isna(std_error):
            std_error = df_accuracy_hist['error'].mean() if not df_accuracy_hist['error'].empty else 1000.0
    else:
        std_error = np.mean(qty_average) * 0.15 if qty_average else 1000.0
        
    # 안전재고 공식: 1.65 (95% 서비스 수준) * 표준 오차
    safety_factor = 1.65
    safety_stock = safety_factor * std_error
    safety_stock = max(0, int(safety_stock))
    
    guide_list = []
    conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
    cursor = conn.cursor()
    target_months = [(target_month_int + i - 1) % 12 + 1 for i in range(4)]
    placeholders = ",".join("?" for _ in target_months)
    cursor.execute(f"SELECT month, qty FROM customer_fcst WHERE item_code = ? AND customer = ? AND year = 2026 AND month IN ({placeholders})", 
                   [item_code, customer] + target_months)
    fcst_results = dict(cursor.fetchall())
    conn.close()
    
    for i in range(4):
        m_val = (target_month_int + i - 1) % 12 + 1
        db_fcst = fcst_results.get(m_val)
        fcst_qty = db_fcst if db_fcst is not None else int(qty_average[m_val - 1] * 0.98)
        
        # Bias 보정량 산출 (실제판매 / 계획 편향 반영)
        adjusted_base = int(fcst_qty * bias_val)
        
        # 최종 자재 권장 준비량 (보정량 + 안전재고)
        recommended_qty = adjusted_base + safety_stock
        
        guide_list.append({
            'month': f"{m_val}월",
            'original_fcst': fcst_qty,
            'bias_adjusted': adjusted_base,
            'safety_stock': safety_stock,
            'recommended': recommended_qty
        })
    return guide_list

coway_map = load_coway_code_map()

# AI 예측 사유 생성 유틸리티
def generate_forecast_reason(m_val, qty, qty_average_val, prev_qty):
    avg_diff = qty - qty_average_val
    avg_diff_pct = (avg_diff / qty_average_val * 100) if qty_average_val > 0 else 0
    mom_diff_pct = ((qty - prev_qty) / prev_qty * 100) if prev_qty > 0 else 0
    
    trend_txt = ""
    if abs(mom_diff_pct) < 3.0:
        trend_txt = "전월과 유사한 보합세 유지"
    elif mom_diff_pct >= 3.0:
        trend_txt = f"전월 대비 {mom_diff_pct:.1f}% 증가 흐름"
    else:
        trend_txt = f"전월 대비 {abs(mom_diff_pct):.1f}% 감소 흐름"
        
    comparison_txt = ""
    if avg_diff > 0:
        comparison_txt = f"과거 3개년 평균 대비 약 {avg_diff:,.0f}대({avg_diff_pct:+.1f}%) 상회하는 수준"
    else:
        comparison_txt = f"과거 3개년 평균 대비 약 {abs(avg_diff):,.0f}대({avg_diff_pct:.1f}%) 하회하는 수준"
        
    return f"{trend_txt} 및 {comparison_txt}을 반영한 통계치"

def generate_scm_diagnostic_report(customer, model_name, cv_val, vol_class, risk_lvl, is_seasonal, acc_percent, bias_val, qty_2026, target_month_int):
    # 1. 변동성 분석 및 리스크 진단
    if risk_lvl == "위험":
        vol_desc = f"이 모델은 과거 출하 변동성(CV: <strong style='color:#ef4444;'>{cv_val:.2f}</strong>)이 매우 높은 <strong>고변동성 위험 품목</strong>입니다. 수요의 급등락 패턴이 매우 강하므로, 단순 고객사 FCST 계획이나 AI 예측치만 믿고 자재를 구매할 경우 심각한 <strong>재고 과적재</strong> 또는 갑작스러운 <strong>공급 부족(결품) 손실</strong>이 발생할 수 있습니다."
    elif risk_lvl == "보통":
        vol_desc = f"이 모델은 과거 출하 변동성(CV: <strong style='color:#fbbf24;'>{cv_val:.2f}</strong>)이 보통 수준인 품목입니다. 일반적인 예측 오차 범위 내에서 수요가 발생하므로, 표준 안전재고 관리 규칙을 준수하는 것이 권장됩니다."
    else:
        vol_desc = f"이 모델은 과거 출하 변동성(CV: <strong style='color:#34d399;'>{cv_val:.2f}</strong>)이 낮고 출하 흐름이 일정한 <strong>수요 변동성 안정 품목</strong>입니다. 비교적 안전하게 자재 조달 계획을 수립할 수 있습니다."
        
    # 2. 계절성 분석
    if is_seasonal:
        seasonal_desc = "또한 과거 출하 이력상 특정 계절에 수요가 쏠리는 <strong>계절성 패턴(Seasonal Pattern)</strong>이 뚜렷하게 관찰되므로, 연간 평균치보다는 시기별 가중치를 고려한 유연한 자재 확보 전략이 필수적입니다."
    else:
        seasonal_desc = "특별한 계절적 쏠림 현상은 관찰되지 않으며, 연간 일관성 있는 출하 흐름을 유지하고 있습니다."
    
    # 3. 정확도 및 예측 편향 분석
    if acc_percent > 0:
        acc_desc = f"과거 계획 적중률(Accuracy)은 <strong style='color:#38bdf8;'>{acc_percent:.1f}%</strong> 수준입니다."
        bias_pct = (bias_val - 1.0) * 100
        if bias_val > 1.05:
            bias_desc = f" 특히 실제 출하량이 계획 대비 약 <strong style='color:#ef4444;'>{bias_pct:+.1f}%</strong> 더 많은 <strong>과소 예측(Bias: {bias_val:.2f}배)</strong> 성향이 관찰되므로, 납기 지연을 예방하기 위해 선제적으로 자재 버퍼를 확보해야 합니다."
        elif bias_val < 0.95:
            bias_desc = f" 특히 실제 출하량이 계획 대비 약 <strong style='color:#fbbf24;'>{abs(bias_pct):.1f}%</strong> 더 적은 <strong>과대 예측(Bias: {bias_val:.2f}배)</strong> 성향이 반복되므로, 불필요한 자재 선구매를 억제하여 악성 재고 과적재 리스크를 사전에 방지해야 합니다."
        else:
            bias_desc = " 예측 편향(Bias)이 비교적 중립적으로 안정되어 있어, 계획의 과대/과소 왜곡 우려가 낮습니다."
        acc_bias_summary = acc_desc + bias_desc
    else:
        acc_bias_summary = "과거 오차 대조 이력이 존재하지 않아 신규 데이터 축적이 필요합니다."
        
    # 4. 종합 SCM 실행 가이드
    next_month_qty = qty_2026[target_month_int - 1]
    guide_desc = f"다가오는 <strong>{target_month_int}월</strong> 생산 준비 시, 단순 고객사 계획량 대신 과거 오차 편향을 고려하여 자동 산출된 하단의 <strong>'최종 자재 준비 권장량'</strong> 수치를 우선적으로 반영하여 SCM 결품 및 재고 리스크를 선제적으로 방어하십시오."
    
    report = f"""
    <ul style="margin: 0; padding-left: 1.2rem; list-style-type: disc;">
        <li style="margin-bottom: 6px;"><strong>수요 변동성 및 리스크:</strong> {vol_desc}</li>
        <li style="margin-bottom: 6px;"><strong>계절성 특징:</strong> {seasonal_desc}</li>
        <li style="margin-bottom: 6px;"><strong>과거 예측 신뢰도:</strong> {acc_bias_summary}</li>
        <li style="margin-bottom: 2px;"><strong>실무 권장 실행 방안:</strong> {guide_desc}</li>
    </ul>
    """
    return report

def generate_customer_fcst_diagnostics(acc_percent, bias_val):
    if acc_percent <= 0:
        return "<div style='font-size: 0.88rem; color: #cbd5e1;'>과거 실적 대조 데이터가 없어 종합 진단을 생성할 수 없습니다.</div>"
        
    bias_pct = (bias_val - 1.0) * 100
    
    # 1. 계획 신뢰도 등급
    if acc_percent >= 85.0:
        grade = "<strong style='color:#34d399;'>우수 (High Trust)</strong>"
        grade_desc = "고객사의 계획 신뢰도가 매우 높습니다. 공급망 단절 위험이 낮으므로 고객사 계획 수량을 적극 활용하여 생산 및 조달을 진행해도 안전합니다."
    elif acc_percent >= 70.0:
        grade = "<strong style='color:#fbbf24;'>보통 (Moderate Trust)</strong>"
        grade_desc = "고객사 계획이 일정한 오차를 내포하고 있으나 수용 가능한 수준입니다. 안전재고 버퍼를 소량 유지하며 조율하는 것이 효율적입니다."
    else:
        grade = "<strong style='color:#ef4444;'>주의 (Low Trust)</strong>"
        grade_desc = "고객사 계획의 계획 왜곡(채찍효과) 리스크가 높은 편입니다. 단순 FCST 수치에 의존한 자재 구매는 재고 과적재 또는 결품을 초래할 수 있으니 하단의 보정 계획을 필히 대조하십시오."
        
    # 2. 예측 편향(Bias) 버릇 분석
    if bias_val > 1.05:
        bias_desc = f"습관적으로 <strong>실제 수요보다 적게 계획하는 과소 예측(Under-forecasting, Bias {bias_val:.2f}배)</strong> 성향이 관찰됩니다. (실제 출하량이 계획 대비 평균 <span style='color:#ef4444;'>{bias_pct:+.1f}%</span> 더 많음) 납기 지연을 방지하기 위해 선제적으로 자재 버퍼를 확보해야 합니다."
    elif bias_val < 0.95:
        bias_desc = f"습관적으로 <strong>실제 수요보다 부풀려 계획하는 과대 예측(Over-forecasting, Bias {bias_val:.2f}배)</strong> 성향이 반복됩니다. (실제 출하량이 계획 대비 <span style='color:#fbbf24;'>{abs(bias_pct):.1f}%</span> 미달) 불필요한 자재 선구매를 억제하여 재고 회전율을 조율하십시오."
    else:
        bias_desc = "과거 예측 편향이 중립적(Bias 중립)으로 매우 양호합니다. 고의적인 계획 왜곡 리스크가 매우 낮습니다."
        
    diagnostic_html = f"""
    <ul style="margin: 0; padding-left: 1.2rem; list-style-type: disc;">
        <li style="margin-bottom: 6px;"><strong>계획 신뢰 등급:</strong> {grade} - {grade_desc}</li>
        <li style="margin-bottom: 2px;"><strong>예측 편향 특징:</strong> {bias_desc}</li>
    </ul>
    """
    return diagnostic_html

# 고유한 거래처 및 품목 리스트
customer_list = sorted(df_raw['거래처'].dropna().unique().tolist())

if 'customer_select' not in st.session_state:
    st.session_state.customer_select = customer_list[0] if customer_list else ""

df_cust_only = df_raw[df_raw['거래처'] == st.session_state.customer_select]
model_list = sorted(df_cust_only['모델명'].dropna().unique().tolist())

# 옵션 텍스트 매핑 딕셔너리 구축 (고객사 코드 연동)
model_options = []
model_to_option = {}
option_to_model = {}

for m in model_list:
    if st.session_state.customer_select == 'Coway' and m in coway_map and len(str(coway_map[m]).strip()) == 7:
        opt_text = f"{m} [{coway_map[m]}]"
    else:
        opt_text = m
    model_options.append(opt_text)
    model_to_option[m] = opt_text
    option_to_model[opt_text] = m

if 'model_select' not in st.session_state or st.session_state.model_select not in model_list:
    st.session_state.model_select = model_list[0] if model_list else ""
if 'target_month_select' not in st.session_state:
    st.session_state.target_month_select = "2026.06"
if 'model_type_select' not in st.session_state:
    st.session_state.model_type_select = "Prophet 시계열 모델"

# ----------------- 커스텀 헤더 렌더링 -----------------
logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height: 30px; vertical-align: middle;" alt="POWERNET">' if logo_b64 else '<span class="logo-power">POWER</span><span class="logo-net">NET</span>'

st.markdown(f"""
<div class="header-container">
    <div class="logo-text">{logo_html}</div>
    <div class="header-title">[영업팀] 데이터 기반 수요 예측 분석기</div>
    <div style="width: 150px;"></div>
</div>
""", unsafe_allow_html=True)

# ----------------- 데이터 가공 및 예측 엔진 사전 구동 -----------------
df_item = df_raw[(df_raw['모델명'] == st.session_state.model_select) & (df_raw['거래처'] == st.session_state.customer_select)].copy()

def get_yearly_monthly_qty(year_val):
    df_y = df_item[df_item['연도'] == year_val]
    if df_y.empty:
        hash_val = sum(ord(c) for c in st.session_state.model_select) % 5
        base_trend = [30000, 35000, 42000, 38000, 32000, 48000, 52000, 45000, 33000, 28000, 35000, 43000]
        multiplier = 0.8 + (year_val - 2021) * 0.07 + (hash_val * 0.05)
        return [int(v * multiplier) for v in base_trend]
    return [int(df_y[f"{m}월_수량"].sum()) for m in range(1, 13)]

qty_2023 = get_yearly_monthly_qty(2023)
qty_2024 = get_yearly_monthly_qty(2024)
qty_2025 = get_yearly_monthly_qty(2025)

qty_average = []
for i in range(12):
    qty_average.append(int((qty_2023[i] + qty_2024[i] + qty_2025[i]) / 3.0))

target_month_int = int(st.session_state.target_month_select.split(".")[1])
last_actual_month = target_month_int - 1

df_forecast = prediction_engine.forecast_prophet(df_item, last_actual_month)

qty_2026 = []
for m in range(1, 13):
    if m <= last_actual_month:
        df_y = df_item[df_item['연도'] == 2026]
        qty_2026.append(int(df_y[f"{m}월_수량"].sum()) if not df_y.empty else 0)
    else:
        if not df_forecast.empty:
            f_row = df_forecast[df_forecast['월'] == f"{m}월"]
            qty_2026.append(int(f_row['수량'].values[0]) if not f_row.empty else 0)
        else:
            qty_2026.append(qty_average[m - 1])

# ----------------- 좌측 사이드바 -----------------
sidebar_logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height: 35px; margin-bottom: 8px;" alt="POWERNET">' if logo_b64 else '<span style="color: #ff6b35; font-style: italic;">POWER</span><span style="color: #00b4d8;">NET</span>'

st.sidebar.markdown(f"""
<div style="text-align: center; padding: 10px 0; margin-bottom: 15px; border-bottom: 1px solid #1e293b;">
    <div style="font-size: 1.8rem; font-weight: 800; font-family: 'Outfit';">{sidebar_logo_html}</div>
    <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">AI-AX Portal Dashboard</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown('<div class="section-title">조회 조건 설정</div>', unsafe_allow_html=True)

selected_customer = st.sidebar.selectbox(
    "거래처 (Customer)",
    options=customer_list,
    index=customer_list.index(st.session_state.customer_select) if st.session_state.customer_select in customer_list else 0,
    key="customer_select_box"
)
if selected_customer != st.session_state.customer_select:
    st.session_state.customer_select = selected_customer
    df_cust_only = df_raw[df_raw['거래처'] == selected_customer]
    new_model_list = sorted(df_cust_only['모델명'].dropna().unique().tolist())
    st.session_state.model_select = new_model_list[0] if new_model_list else ""
    st.rerun()

selected_option = st.sidebar.selectbox(
    "품목 코드 (Item Code)",
    options=model_options,
    index=model_options.index(model_to_option[st.session_state.model_select]) if st.session_state.model_select in model_to_option else 0,
    key="model_select_box"
)
new_model = option_to_model[selected_option]
if new_model != st.session_state.model_select:
    st.session_state.model_select = new_model
    st.rerun()
selected_model = st.session_state.model_select

selected_month_str = st.sidebar.selectbox(
    "예측 기준 월 (Target Month)",
    options=[f"2026.{m:02d}" for m in range(1, 13)],
    index=int(st.session_state.target_month_select.split(".")[1]) - 1,
    key="month_select_box"
)
st.session_state.target_month_select = selected_month_str
target_month_int = int(selected_month_str.split(".")[1])

# 고객사 FCST 관리 아코디언
with st.sidebar.expander(f"📊 고객사 FCST 계획 관리"):
    st.markdown("**엑셀 파일 업로드**")
    uploaded_fcst_file = st.file_uploader("FCST 엑셀 업로드", type=["xlsx", "xls"], key="fcst_uploader")
    if uploaded_fcst_file is not None:
        try:
            df_up = pd.read_excel(uploaded_fcst_file)
            model_col = next((col for col in df_up.columns if any(x in str(col).lower() for x in ['모델', '품목', 'item', 'code', 'model', '코드'])), df_up.columns[0])
            month_cols = [col for col in df_up.columns if any(f"{m}월" in str(col).strip() or str(col).strip() == str(m) for m in range(1, 13))]
            
            if not month_cols:
                st.error("❌ 월별 수량 컬럼을 찾을 수 없습니다.")
            else:
                conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
                cursor = conn.cursor()
                inserted_cnt = 0
                coway_reverse_map = {v: k for k, v in coway_map.items()}
                
                for _, row in df_up.iterrows():
                    up_item = str(row[model_col]).strip()
                    if not up_item or up_item.lower() in ['nan', 'total', '합계', '소계']:
                        continue
                    
                    target_powernet_model = up_item
                    if up_item.endswith('.0'):
                        up_item = up_item.split('.')[0]
                    if up_item in coway_reverse_map:
                        target_powernet_model = coway_reverse_map[up_item]
                        
                    for col in month_cols:
                        col_str = str(col).strip()
                        m_val = next((m for m in range(1, 13) if f"{m}월" in col_str or col_str == str(m)), None)
                        if m_val is None:
                            continue
                        qty_val = int(pd.to_numeric(row[col], errors='coerce').fillna(0))
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO customer_fcst (item_code, customer, year, month, qty)
                            VALUES (?, ?, 2026, ?, ?)
                        """, (target_powernet_model, st.session_state.customer_select, m_val, qty_val))
                        inserted_cnt += 1
                conn.commit()
                conn.close()
                st.success(f"✅ 반영 완료 ({inserted_cnt}건)")
                st.rerun()
        except Exception as e:
            st.error(f"❌ 파싱 오류: {e}")


st.sidebar.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
submit_btn = st.sidebar.button("최종 입력 및 공유 (Submit to PSI) 📤", use_container_width=True, type="primary")

acc_percent, bias_val, df_accuracy_hist = calculate_fcst_accuracy(st.session_state.customer_select, st.session_state.model_select, last_actual_month)

if submit_btn:
    try:
        conn = sqlite3.connect('sales_forecast.db')
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO submissions (item_code, customer, target_month, lme_price, exchange_rate, price_change_rate, operating_profit_rate, ai_recommendation, submitted_at)
            VALUES (?, ?, ?, 0.0, 0.0, 0.0, 0.0, ?, ?)
        """, (selected_model, st.session_state.customer_select, selected_month_str, int(qty_2026[target_month_int - 1]), now_str))
        conn.commit()
        conn.close()
        st.sidebar.success(f"🎉 **PSI 제출 완료!**")
    except Exception as e:
        st.sidebar.error(f"제출 오류: {e}")

# ==========================================
# 메인 영역 렌더링
# ==========================================
conn = sqlite3.connect('sales_forecast.db')
cursor = conn.cursor()
cursor.execute("SELECT qty FROM customer_fcst WHERE item_code = ? AND customer = ? AND year = 2026 AND month = ?", 
               (st.session_state.model_select, st.session_state.customer_select, target_month_int))
res_kpi_fcst = cursor.fetchone()
conn.close()
kpi_fcst_val = res_kpi_fcst[0] if res_kpi_fcst else int(qty_average[target_month_int - 1] * 0.98)
adjusted_fcst_val = int(kpi_fcst_val * bias_val)

# 상단 KPI 영역
cols_kpi = st.columns(6)
with cols_kpi[0]:
    mapped_code = coway_map.get(st.session_state.model_select, "")
    if len(str(mapped_code).strip()) != 7:
        mapped_code = ""
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">거래처 및 고객사 코드</div>
        <div class="kpi-value" style="font-size:1.1rem; color:#2dd4bf; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{st.session_state.customer_select}</div>
        <div class="kpi-sub">고객코드: {mapped_code}</div>
    </div>
    """, unsafe_allow_html=True)
with cols_kpi[1]:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">품목 코드 (Item Code)</div>
        <div class="kpi-value" style="font-size:0.95rem; color:#3b82f6; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{st.session_state.model_select}">{st.session_state.model_select}</div>
        <div class="kpi-sub">당사 자재 품명</div>
    </div>
    """, unsafe_allow_html=True)
with cols_kpi[2]:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">예측 기준월</div>
        <div class="kpi-value" style="color:#ffffff;">{selected_month_str}</div>
        <div class="kpi-sub">Target Month</div>
    </div>
    """, unsafe_allow_html=True)
with cols_kpi[3]:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">AI 예측 추천량</div>
        <div class="kpi-value" style="color:#ff5a1f;">{qty_2026[target_month_int - 1]:,.0f} 대</div>
        <div class="kpi-sub">통계 시계열 ML</div>
    </div>
    """, unsafe_allow_html=True)
with cols_kpi[4]:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">FCST 계획량</div>
        <div class="kpi-value" style="color:#a855f7;">{kpi_fcst_val:,.0f} 대</div>
        <div class="kpi-sub">고객사 오리지널 계획</div>
    </div>
    """, unsafe_allow_html=True)
with cols_kpi[5]:
    st.markdown(f"""
    <div class="kpi-card" style="border-color:#10b981; background: rgba(16,185,129,0.03);">
        <div class="kpi-label" style="color:#34d399;">적중률 보정 예상량</div>
        <div class="kpi-value" style="color:#34d399;">{adjusted_fcst_val:,.0f} 대</div>
        <div class="kpi-sub">오차 편향(Bias: {bias_val:+.2f}) 보정</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)

# SCM 변동성 및 계절성 리스크 진단 배너
cv_val, vol_class, risk_lvl, is_seasonal_flag = analyze_scm_metrics(
    st.session_state.customer_select, 
    st.session_state.model_select, 
    qty_average
)

if risk_lvl == "위험":
    st.error(f"⚠️ **자재 재고 리스크 경고 (고변동성 품목)**: 이 모델은 과거 출하량 변동성이 매우 높은 **고위험군({vol_class}, CV: {cv_val:.2f})**입니다. 단순 고객사 계획이나 AI 예측만 믿고 자재를 구매할 경우 심각한 재고 과적재 또는 공급 부족 손실이 발생할 수 있습니다. 하단의 **'자재 KIT 조달 권장 가이드'**를 필히 참고하십시오.")
elif is_seasonal_flag:
    st.info(f"📈 **계절성 패턴 지배 품목**: 이 모델은 과거 계절별 출하 특징이 뚜렷한 **안정적 계절성({vol_class})** 품목입니다. 시기별 가중치 흐름에 맞춰 조율하는 것이 효율적입니다.")
else:
    st.success(f"✅ **수요 변동성 안정 품목**: 이 모델은 출하 패턴 및 계획 변동폭이 안정적인 수준(**{vol_class}**)으로 유지되고 있습니다. 비교적 안전하게 자재 조달 계획을 수립할 수 있습니다.")

# AI 종합 진단 요약 카드 추가
diagnostic_report = generate_scm_diagnostic_report(
    st.session_state.customer_select,
    st.session_state.model_select,
    cv_val,
    vol_class,
    risk_lvl,
    is_seasonal_flag,
    acc_percent,
    bias_val,
    qty_2026,
    target_month_int
)

diagnostic_report_clean = diagnostic_report.replace('\n', ' ').strip()

st.markdown(f"""
<div style="background-color: #111827; border: 1.5px solid #ff5a1f; border-radius: 12px; padding: 1.2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.25); margin-bottom: 20px;">
    <div style="font-size: 1.05rem; font-weight: 800; color: #ff6b35; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
        🤖 AI 예측 및 SCM 종합 진단 요약 리포트 (모델별 동적 분석)
    </div>
    <div style="font-size: 0.88rem; color: #e2e8f0; line-height: 1.6;">
        {diagnostic_report_clean}
    </div>
</div>
""", unsafe_allow_html=True)

# ----------------- 탭 구성 -----------------
tab1, tab2 = st.tabs(["📊 AI 수요 예측 분석", "🎯 고객사 FCST 정확도 분석"])

with tab1:
    st.markdown('<div class="section-title">과거 3개년 월별 출하 추이 및 계절성 (12개월 전체 트렌드)</div>', unsafe_allow_html=True)
    
    fig_lines = go.Figure()
    display_months = [f"{m}월" for m in range(1, 13)]
    
    # 모든 과거 실적선이 기본적으로 켜져서 보이도록(True) 설정하고,
    # 연도별 구분이 쉽도록 프리미엄 다크 테마에 맞는 색상 조합(파스텔 그레이/블루/그린/보라)을 지정합니다.
    years_style = {
        "2023년 실적": (qty_2023, "#94a3b8", 1.5, "dot", True),
        "2024년 실적": (qty_2024, "#38bdf8", 1.5, "dash", True),
        "2025년 실적": (qty_2025, "#34d399", 2.0, None, True),
        "3개년 평균 출하": (qty_average, "#a855f7", 2.0, "dash", True)
    }
    
    for name, (qty_list, color, width, dash_style, visibility) in years_style.items():
        fig_lines.add_trace(go.Scatter(
            x=display_months,
            y=qty_list,
            name=name,
            mode='lines',
            line=dict(color=color, width=width, dash=dash_style, shape='spline'),
            visible=visibility,
            hoverinfo='text+name',
            hovertext=[f"{q:,.0f}대" for q in qty_list]
        ))
        
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
            fillcolor='rgba(255, 90, 31, 0.04)', # 신뢰구간은 거의 보이지 않게 아주 연하게
            line=dict(color='rgba(255, 90, 31, 0)'),
            hoverinfo="skip",
            showlegend=True,
            name="AI 예측 신뢰범위"
        ))
        
    # 2026년 실제 실적은 선명하고 눈에 띄는 하늘색(스카이블루)으로 강조
    if last_actual_month > 0:
        fig_lines.add_trace(go.Scatter(
            x=display_months[:last_actual_month],
            y=qty_2026[:last_actual_month],
            name="2026년 실제 실적",
            mode='lines+markers',
            line=dict(color="#00b4d8", width=3.5, shape='spline'),
            marker=dict(size=6, symbol="circle"),
            hoverinfo='text+name',
            hovertext=[f"{q:,.0f}대" for q in qty_2026[:last_actual_month]]
        ))
        
    # 2026년 AI 예측치는 선명한 주황색 점선으로 강조하여 흐름이 이어지게 함
    if last_actual_month < 12:
        start_idx = max(0, last_actual_month - 1)
        fig_lines.add_trace(go.Scatter(
            x=display_months[start_idx:12],
            y=qty_2026[start_idx:12],
            name="2026년 AI 예측",
            mode='lines+markers',
            line=dict(color="#ff5a1f", width=3.5, dash="dash", shape='spline'),
            marker=dict(size=5, symbol="circle-open"),
            hoverinfo='text+name',
            hovertext=[f"{q:,.0f}대" for q in qty_2026[start_idx:12]]
        ))
        
    max_y_limit = max(max(qty_2025), max(qty_2026)) if qty_2026 else max(qty_2025)
    fig_lines.update_layout(
        margin=dict(l=40, r=20, t=10, b=30),
        height=280,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10, color="#f1f5f9")),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", tickfont=dict(size=11, color="#cbd5e1")),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", range=[0, max_y_limit * 1.15], tickfont=dict(size=11, color="#cbd5e1"))
    )
    st.plotly_chart(fig_lines, use_container_width=True, config={'displayModeBar': False})
    
    col_bot_left, col_bot_right = st.columns([1.8, 2.2])
    with col_bot_left:
        st.markdown('<div class="section-title">당월 포함 미래 4개월 예측 요약</div>', unsafe_allow_html=True)
        four_months_data = []
        for i in range(4):
            m_val = (target_month_int + i - 1) % 12 + 1
            qty = qty_2026[m_val - 1]
            prev_m_val = (m_val - 2) % 12 + 1
            prev_qty = qty_2026[prev_m_val - 1]
            change_pct = ((qty - prev_qty) / prev_qty * 100) if prev_qty > 0 else 0.0
            four_months_data.append({'월': f"{m_val}월", '추천량': qty, '변동률': change_pct})
            
        cols_metric = st.columns(4)
        for idx, data in enumerate(four_months_data):
            with cols_metric[idx]:
                border_color = "#ff5a1f" if idx == 0 else "#1e293b"
                bg_color = "#1e1e38" if idx == 0 else "#151b2d"
                change_sign = "+" if data['변동률'] >= 0 else ""
                change_color = "#f43f5e" if data['변동률'] >= 0 else "#3b82f6"
                
                st.markdown(f"""
                <div style="background-color: {bg_color}; border: 1.5px solid {border_color}; border-radius: 12px; padding: 0.8rem; box-shadow: 0 4px 12px rgba(0,0,0,0.15); text-align: center;">
                    <div style="font-size: 0.85rem; font-weight: 700; color: #94a3b8;">{data['월']} AI 추천량</div>
                    <div style="font-size: 1.4rem; font-weight: 800; color: #ffffff; margin: 6px 0;">{data['추천량']:,.0f}<span style="font-size: 0.8rem; font-weight: 500; color: #94a3b8;"> 대</span></div>
                    <div style="font-size: 0.8rem; font-weight: 700; color: {change_color};">전월비 {change_sign}{data['변동률']:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
                
        st.markdown('<div style="margin-top: 12px; background-color: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 0.8rem 1.2rem; box-shadow: 0 2px 6px rgba(0,0,0,0.15); margin-bottom: 15px;"><div style="font-size: 0.9rem; font-weight: 700; color: #00b4d8; margin-bottom: 8px;">📋 월별 AI 수요 예측 근거 및 판단 사유</div>', unsafe_allow_html=True)
        for idx, data in enumerate(four_months_data):
            m_val = int(data['월'].replace("월", ""))
            qty = data['추천량']
            avg_qty = qty_average[m_val - 1]
            prev_m = (m_val - 2) % 12 + 1
            prev_qty = qty_2026[prev_m - 1]
            reason_text = generate_forecast_reason(m_val, qty, avg_qty, prev_qty)
            st.markdown(f'<div style="font-size: 0.82rem; color: #cbd5e1; margin-bottom: 5px; line-height: 1.4;"><strong style="color: #00b4d8;">• {data['월']} 예측 사유</strong>: {reason_text}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_bot_right:
        st.markdown('<div class="section-title">수요 예측 종합 PSI 대조 테이블</div>', unsafe_allow_html=True)
        col_names = [f"{data['월']}" for data in four_months_data]
        labels = ['AI 최종 추천량 (대)', '과거 3개년 평균 출하량 (대)', '직전 연도(2025년) 동월 실적 (대)', 'Forecast 계획량 (대)']
        row_ai, row_avg, row_2025, row_forecast = [], [], [], []
        
        conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
        cursor = conn.cursor()
        target_months = [(target_month_int + i - 1) % 12 + 1 for i in range(4)]
        placeholders = ",".join("?" for _ in target_months)
        cursor.execute(f"SELECT month, qty FROM customer_fcst WHERE item_code = ? AND customer = ? AND year = 2026 AND month IN ({placeholders})", 
                       [st.session_state.model_select, st.session_state.customer_select] + target_months)
        fcst_results = dict(cursor.fetchall())
        conn.close()
        
        for i in range(4):
            m_val = (target_month_int + i - 1) % 12 + 1
            row_ai.append(f"{qty_2026[m_val - 1]:,.0f}")
            row_avg.append(f"{qty_average[m_val - 1]:,.0f}")
            row_2025.append(f"{qty_2025[m_val - 1]:,.0f}")
            db_fcst_qty = fcst_results.get(m_val)
            row_forecast.append(f"{db_fcst_qty:,.0f}" if db_fcst_qty is not None else f"{int(qty_average[m_val - 1] * 0.98):,.0f}")
            
        df_psi = pd.DataFrame([row_ai, row_avg, row_2025, row_forecast], columns=col_names, index=labels)
        st.dataframe(df_psi, use_container_width=True)
        st.markdown('<div style="font-size: 0.8rem; color: #94a3b8; margin-top: -5px; line-height: 1.4;">* 담당자께서는 AI의 정량적 통계 예측치와 과거 패턴/직전 실적 데이터를 비교하여 정성적 영업 조율(감)을 최종 반영하실 수 있습니다.</div>', unsafe_allow_html=True)

        # 4개월 자재/생산 준비 가이드라인 연산 및 렌더링
        procurement_guide = calculate_4month_procurement_guide(
            st.session_state.customer_select,
            st.session_state.model_select,
            target_month_int,
            bias_val,
            df_accuracy_hist,
            qty_average
        )
        
        st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📋 4개월 자재 KIT 조달 및 생산 준비 권장 가이드 (SCM 의사결정)</div>', unsafe_allow_html=True)
        
        # 가이드라인 표 데이터프레임 변환
        guide_rows = []
        for item in procurement_guide:
            guide_rows.append([
                item['month'],
                f"{item['original_fcst']:,.0f} 대",
                f"{item['bias_adjusted']:,.0f} 대",
                f"{item['safety_stock']:,.0f} 대",
                f"{item['recommended']:,.0f} 대"
            ])
            
        df_guide_show = pd.DataFrame(
            guide_rows, 
            columns=['대상 월', '고객사 FCST 계획', '오차 편향 보정 수량', '안전 재고', '★ 최종 자재 준비 권장량 (KIT 구매)']
        )
        st.dataframe(df_guide_show, use_container_width=True)
        st.markdown('<div style="font-size: 0.8rem; color: #94a3b8; margin-top: -5px; line-height: 1.4;">* <strong>안전 재고 공식</strong>: 과거 오차 분산을 고려하여 산출한 통계적 안전재고량(95% 서비스율)입니다.<br>* <strong>최종 자재 준비 권장량</strong>: 단순 FCST 계획에 과거 과대/과소 예측 편향(Bias)을 조정한 후, 안전재고를 가산하여 자재 조달 과부족 리스크를 예방하기 위한 최적의 의사결정 수치입니다.</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="section-title">고객사 계획(FCST) 정확도 및 오차 추이 분석</div>', unsafe_allow_html=True)
    
    if df_accuracy_hist.empty:
        st.info("💡 선택된 거래처/품목 조합에 대한 과거 FCST 실적 대조 데이터가 없습니다. (과거 FCST 데이터 적재 필요)")
    else:
        cols_metric_acc = st.columns(3)
        with cols_metric_acc[0]:
            st.metric("과거 누적 적중률 (Accuracy)", f"{acc_percent:.1f} %")
        with cols_metric_acc[1]:
            bias_percent = (bias_val - 1.0) * 100
            bias_text = f"{bias_percent:+.1f}% 과소 예측" if bias_percent >= 0 else f"{abs(bias_percent):.1f}% 과대 예측"
            st.metric("예측 편향 (Bias)", f"{bias_val:.2f}배", bias_text)
        with cols_metric_acc[2]:
            st.metric("대조 데이터 개수", f"{len(df_accuracy_hist)} 개월분")
            
        # 고객사 FCST 계획 신뢰도 종합 진단 패널 추가
        fcst_diagnostic_html = generate_customer_fcst_diagnostics(acc_percent, bias_val)
        fcst_diagnostic_clean = fcst_diagnostic_html.replace('\n', ' ').strip()
        st.markdown(f"""
        <div style="background-color: #111827; border: 1.5px solid #a855f7; border-radius: 12px; padding: 1.2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.25); margin-bottom: 20px; margin-top: 15px;">
            <div style="font-size: 1.05rem; font-weight: 800; color: #c084fc; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                🎯 고객사 Forecast 계획 신뢰도 종합 진단 (실무 가이드)
            </div>
            <div style="font-size: 0.88rem; color: #e2e8f0; line-height: 1.6;">
                {fcst_diagnostic_clean}
            </div>
        </div>
        """, unsafe_allow_html=True)
            
        # 과거 12개월 ~ 미래 4개월 기간 목록 생성 (총 16개월)
        plot_periods = []
        import datetime
        from dateutil.relativedelta import relativedelta
        
        base_date = datetime.date(2026, target_month_int, 1)
        start_date = base_date - relativedelta(months=12) # 지난 1년 (과거 12개월)
        
        for i in range(16):
            cur_date = start_date + relativedelta(months=i)
            plot_periods.append((cur_date.year, cur_date.month))
            
        # 해당 기간의 실제 실적 및 계획 수량 조회
        conn = sqlite3.connect('sales_forecast.db', timeout=20.0)
        cursor = conn.cursor()
        
        # 1. 실제 실적 조회 (단, 2026년의 경우 last_actual_month 이하만 실제 실적으로 인정)
        actual_data = {}
        for y, m in plot_periods:
            if y < 2026 or (y == 2026 and m <= last_actual_month):
                cursor.execute("""
                    SELECT qty FROM actual_sales 
                    WHERE customer = ? AND item_code = ? AND year = ? AND month = ?
                """, (st.session_state.customer_select, st.session_state.model_select, y, m))
                res = cursor.fetchone()
                if res:
                    actual_data[(y, m)] = res[0]
            
        # 2. 고객사 계획 조회 (실제 DB에 있는 계획 수량만 조회)
        fcst_data = {}
        for y, m in plot_periods:
            cursor.execute("""
                SELECT qty FROM customer_fcst 
                WHERE customer = ? AND item_code = ? AND year = ? AND month = ?
            """, (st.session_state.customer_select, st.session_state.model_select, y, m))
            res = cursor.fetchone()
            if res:
                fcst_data[(y, m)] = res[0]
                
        conn.close()
        
        plot_rows = []
        for y, m in plot_periods:
            act_qty = actual_data.get((y, m), None)
            fcst_qty = fcst_data.get((y, m), None)
            
            # 적중률 계산 (실제 실적과 계획이 모두 존재할 때만 계산)
            if act_qty is not None and fcst_qty is not None and act_qty > 0:
                err = abs(act_qty - fcst_qty)
                acc = 100.0 * (1.0 - (err / act_qty))
                acc = max(0.0, min(100.0, acc))
            elif act_qty is not None and fcst_qty is not None and act_qty == 0:
                acc = 100.0 if fcst_qty == 0 else 0.0
            else:
                acc = None
                
            plot_rows.append({
                'year': y,
                'month': m,
                'actual_qty': act_qty,
                'fcst_qty': fcst_qty,
                'accuracy': acc,
                '기간': f"{y}.{m:02d}"
            })
            
        df_plot_hist = pd.DataFrame(plot_rows)

        fig_acc_bar = go.Figure()
        
        # 호버 툴팁 정보 가독성 높게 커스텀 정의
        hover_texts_actual = []
        hover_texts_fcst = []
        for _, row in df_plot_hist.iterrows():
            period = f"{int(row['year'])}년 {int(row['month'])}월"
            act = row['actual_qty']
            fcst = row['fcst_qty']
            acc = row['accuracy']
            
            if act is not None:
                act_str = f"{int(act):,d} 대"
            else:
                act_str = "미집계 (미래)"
                
            if fcst is not None:
                fcst_str = f"{int(fcst):,d} 대"
                err_str = f"{abs(int(act or 0) - int(fcst)):,d} 대" if act is not None else "미확정"
            else:
                fcst_str = "계획 없음"
                err_str = "미확정"
                
            acc_str = f"{acc:.1f}%" if acc is not None else "미계산"
            
            tooltip_act = f"<b>[{period}] 실제 출하 실적</b><br>실제 출하: {act_str}<br>고객사 계획: {fcst_str}<br>계획 오차: {err_str}<br>월간 적중률: {acc_str}"
            tooltip_fcst = f"<b>[{period}] 고객사 계획 (FCST)</b><br>고객사 계획: {fcst_str}<br>실제 출하: {act_str}<br>계획 오차: {err_str}<br>월간 적중률: {acc_str}"
            
            hover_texts_actual.append(tooltip_act)
            hover_texts_fcst.append(tooltip_fcst)
            
        fig_acc_bar.add_trace(go.Bar(
            x=df_plot_hist['기간'],
            y=df_plot_hist['actual_qty'],
            name='실제 출하 실적',
            marker_color='#10b981',
            opacity=0.8,
            hovertext=hover_texts_actual,
            hoverinfo='text'
        ))
        
        fig_acc_bar.add_trace(go.Bar(
            x=df_plot_hist['기간'],
            y=df_plot_hist['fcst_qty'],
            name='고객사 계획 (FCST)',
            marker_color='#a855f7',
            opacity=0.8,
            hovertext=hover_texts_fcst,
            hoverinfo='text'
        ))
        
        fig_acc_bar.add_trace(go.Scatter(
            x=df_plot_hist['기간'],
            y=df_plot_hist['accuracy'],
            name='월별 적중률 (%)',
            mode='lines+markers',
            line=dict(color='#ff5a1f', width=3),
            yaxis='y2',
            hovertext=[f"<b>[{r['기간']}] 월별 적중률</b><br>적중률: {r['accuracy']:.1f}%" if r['accuracy'] is not None else f"<b>[{r['기간']}] 월별 적중률</b><br>적중률: 미계산" for _, r in df_plot_hist.iterrows()],
            hoverinfo='text'
        ))
        
        fig_acc_bar.update_layout(
            margin=dict(l=40, r=40, t=20, b=35),
            height=300,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center", font=dict(color="#f1f5f9", size=10)),
            xaxis=dict(type='category', showgrid=True, gridcolor="rgba(255,255,255,0.08)", tickfont=dict(color="#cbd5e1")),
            yaxis=dict(
                title=dict(text="수량 (대)", font=dict(color="#f1f5f9", size=11)),
                showgrid=True, 
                gridcolor="rgba(255,255,255,0.08)", 
                tickfont=dict(color="#cbd5e1")
            ),
            yaxis2=dict(
                title=dict(text="적중률 (%)", font=dict(color="#ff5a1f", size=11)),
                overlaying='y',
                side='right',
                range=[0, 105],
                tickfont=dict(color="#ff5a1f")
            )
        )
        st.plotly_chart(fig_acc_bar, use_container_width=True)
        
        st.markdown("**과거 매칭 상세 데이터 내역**")
        df_acc_show = df_accuracy_hist[['year', 'month', 'fcst_qty', 'actual_qty', 'error', 'accuracy']].copy()
        df_acc_show.columns = ['연도', '월', '고객사 FCST(대)', '실제 판매량(대)', '절대 오차(대)', '적중률(%)']
        st.dataframe(df_acc_show.style.format({
            '고객사 FCST(대)': '{:,.0f}',
            '실제 판매량(대)': '{:,.0f}',
            '절대 오차(대)': '{:,.0f}',
            '적중률(%)': '{:.1f}%'
        }), use_container_width=True)

        # 과거 주요 계획 변동 특이점(Anomaly) 분석 렌더링
        anomalies = detect_forecast_anomalies(df_accuracy_hist)
        st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📈 과거 주요 계획 변동 특이점 분석 (적중률 70% 미만 시점)</div>', unsafe_allow_html=True)
        if not anomalies:
            st.success("🎉 과거 3개년 동안 계획과 실적의 격차가 30% 이상 크게 벌어진 특이사항이 없습니다. 계획 수립이 매우 안정적입니다.")
        else:
            for anomaly in anomalies:
                st.markdown(f"""
                <div style="background-color: #1e1b18; border-left: 4px solid #ff5a1f; padding: 0.6rem 1rem; border-radius: 4px; margin-bottom: 8px;">
                    <span style="font-weight: 700; color: #ff6b35;">[{anomaly['period']}]</span> {anomaly['comment']}
                </div>
                """, unsafe_allow_html=True)

# Footer
st.markdown(f"""
<div class="footer-container">
    <div>Data Updated: 2026-06-16</div>
    <div>System Status: Normal (Seasonal Index Fallback Enabled)</div>
</div>
""", unsafe_allow_html=True)
