import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
import sqlite3

# 페이지 설정
st.set_page_config(
    page_title="Coway 영업 실적 대시보드 & DB 검증 시스템",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 프리미엄 디자인을 위한 Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif;
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #4D96FF 0%, #FF6B6B 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .sub-title {
        font-size: 1.1rem;
        color: #7f8c8d;
        margin-bottom: 2rem;
    }
    
    /* 카드 디자인 */
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #e9ecef;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .metric-label {
        font-size: 0.95rem;
        color: #6c757d;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #212529;
    }
    
    .metric-unit {
        font-size: 1rem;
        color: #6c757d;
        font-weight: 400;
    }
</style>
""", unsafe_allow_html=True)

# 23년~26년 데이터 로드 및 정제 함수
@st.cache_data
def load_all_data():
    workspace_dir = r"c:\Users\power\OneDrive\바탕 화면\영업팀 실적파일"
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
                
            # 헤더 설정 및 상단 메타데이터 행 제외
            df.columns = [str(x).strip() for x in df.iloc[header_idx]]
            df = df.iloc[header_idx + 1:].reset_index(drop=True)
            
            # 컬럼명 표준화
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
                
            # 병합 셀(거래처명) ffill 채우기
            df['거래처'] = df['거래처'].ffill()
            
            # 소계, 합계 등 요약 행 제거
            invalid_keywords = '소계|합계|TOTAL|Total|소 계'
            df = df[~df['모델명'].astype(str).str.contains(invalid_keywords, na=False)]
            df = df[~df['거래처'].astype(str).str.contains(invalid_keywords, na=False)]
            
            # 코웨이(Coway) 필터링
            df_coway = df[df['거래처'].astype(str).str.contains('코웨이|Coway', case=False, na=False)].copy()
            
            # 컬럼명 변환 (1월 -> 1월_수량, 그 다음 nan -> 1월_금액 등)
            cols = list(df_coway.columns)
            new_cols = []
            for i, col in enumerate(cols):
                if col in ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월', '년계', '1분기', '2분기', '3분기', '4분기', '상반기', '하반기']:
                    new_cols.append(col + "_수량")
                elif i > 0 and new_cols[-1].endswith("_수량") and col == 'nan':
                    base = new_cols[-1].split("_")[0]
                    new_cols.append(base + "_금액")
                else:
                    new_cols.append(col)
            df_coway.columns = new_cols
            
            # 숫자 데이터 포맷 변환 및 결측치 0 처리
            num_cols = [c for c in df_coway.columns if c.endswith('_수량') or c.endswith('_금액')]
            for col in num_cols:
                df_coway[col] = pd.to_numeric(df_coway[col], errors='coerce').fillna(0)
                
            # 제품군(구분) 컬럼 표준화
            if '제품' in df_coway.columns:
                df_coway['제품'] = df_coway['제품'].ffill().fillna('미분류')
            else:
                df_coway['제품'] = '미분류'
                
            df_coway['연도'] = y
            
            # 필요한 열만 명확하게 추출하여 중복 컬럼(예: 다중 nan 컬럼 등)으로 인한 concat 에러 방지
            target_cols = ['연도', '거래처', '제품', '모델명', '년계_수량', '년계_금액']
            for m in range(1, 13):
                target_cols.extend([f'{m}월_수량', f'{m}월_금액'])
                
            # 존재하지 않는 타겟 컬럼은 0으로 생성
            for col in target_cols:
                if col not in df_coway.columns:
                    if col == '연도':
                        df_coway['연도'] = y
                    elif col == '제품':
                        df_coway['제품'] = '미분류'
                    else:
                        df_coway[col] = 0
            
            df_coway_clean = df_coway[target_cols].copy()
            dfs.append(df_coway_clean)
        except Exception as e:
            st.error(f"{y}년 데이터 로드 실패: {e}")
            
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

# 월별/시계열 데이터로 멜팅(Melt) 처리
def get_melted_data(df):
    if df.empty:
        return pd.DataFrame()
        
    months = [f"{m}월" for m in range(1, 13)]
    
    # 수량 멜팅
    melt_qty = pd.melt(
        df,
        id_vars=['연도', '거래처', '제품', '모델명'],
        value_vars=[f'{m}_수량' for m in months],
        var_name='월',
        value_name='수량'
    )
    melt_qty['월'] = melt_qty['월'].apply(lambda x: int(x.replace('_수량', '').replace('월', '')))
    
    # 금액 멜팅
    melt_amt = pd.melt(
        df,
        id_vars=['연도', '거래처', '제품', '모델명'],
        value_vars=[f'{m}_금액' for m in months],
        var_name='월',
        value_name='금액'
    )
    melt_amt['월'] = melt_amt['월'].apply(lambda x: int(x.replace('_금액', '').replace('월', '')))
    
    # 수량 & 금액 병합
    melted = pd.merge(melt_qty, melt_amt, on=['연도', '거래처', '제품', '모델명', '월'])
    return melted

# 데이터 로드
with st.spinner("엑셀 실적 파일을 분석 및 정제 중입니다..."):
    df_raw = load_all_data()

if df_raw.empty:
    st.error("❌ 영업팀 실적파일 폴더에서 데이터를 로드하지 못했습니다. 경로와 파일명을 확인해주세요.")
    st.stop()

# ----------------- UI 레이아웃 구성 -----------------
st.markdown('<div class="main-title">Coway 실적 대시보드 & DB 검증</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">바탕화면 실적 데이터 실시간 모니터링 및 데이터베이스 입력 정합성 자동 검증 솔루션</div>', unsafe_allow_html=True)

# 사이드바 필터
st.sidebar.header("🎛️ 데이터 필터링")
selected_years = st.sidebar.multiselect("연도 선택", options=sorted(df_raw['연도'].unique()), default=sorted(df_raw['연도'].unique()))
selected_products = st.sidebar.multiselect("제품군 선택", options=sorted(df_raw['제품'].dropna().unique()), default=sorted(df_raw['제품'].dropna().unique()))

# 필터링 적용
df_filtered = df_raw[df_raw['연도'].isin(selected_years) & df_raw['제품'].isin(selected_products)]

# 메인 탭 구성
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 종합 실적 현황", "📅 월별 매출 분석", "📋 정제 데이터 조회", "🔗 DB 적재 및 정합성 검증", "🔮 월별 물량 예측"])

# ----------------- Tab 1: 종합 실적 현황 -----------------
with tab1:
    if df_filtered.empty:
        st.warning("선택된 필터에 해당하는 데이터가 없습니다.")
    else:
        # 상단 메트릭 카드
        total_qty = df_filtered['년계_수량'].sum()
        total_amt = df_filtered['년계_금액'].sum()
        unique_models = df_filtered['모델명'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">총 매출 금액</div>
                <div class="metric-value">{total_amt:,.2f} <span class="metric-unit">K-USD</span></div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">총 매출 수량</div>
                <div class="metric-value">{total_qty:,.0f} <span class="metric-unit">개</span></div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">판매 모델 가짓수</div>
                <div class="metric-value">{unique_models} <span class="metric-unit">종</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        
        # 차트 영역
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            st.subheader("📈 연도별 매출 트렌드")
            # 연도별 수량 및 금액 집계
            yearly_summary = df_filtered.groupby('연도')[['년계_수량', '년계_금액']].sum().reset_index()
            
            fig = go.Figure()
            # 금액 Bar
            fig.add_trace(go.Bar(
                x=yearly_summary['연도'].astype(str),
                y=yearly_summary['년계_금액'],
                name='매출 금액 (K-USD)',
                marker_color='#4D96FF',
                yaxis='y1'
            ))
            # 수량 Line
            fig.add_trace(go.Scatter(
                x=yearly_summary['연도'].astype(str),
                y=yearly_summary['년계_수량'],
                name='매출 수량 (개)',
                mode='lines+markers+text',
                text=[f"{q:,.0f}" for q in yearly_summary['년계_수량']],
                textposition="top center",
                line=dict(color='#FF6B6B', width=3),
                yaxis='y2'
            ))
            
            fig.update_layout(
                title="연도별 매출 금액 & 수량 비교",
                yaxis=dict(title="매출 금액 (K-USD)", side="left"),
                yaxis2=dict(title="매출 수량 (개)", side="right", overlaying="y", showgrid=False),
                legend=dict(x=0.01, y=0.99),
                template="plotly_white",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with col_c2:
            st.subheader("🍕 제품군별 매출 비중")
            product_summary = df_filtered.groupby('제품')['년계_금액'].sum().reset_index()
            fig_pie = px.pie(
                product_summary,
                values='년계_금액',
                names='제품',
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_layout(
                title="제품군별 매출 금액 비중",
                template="plotly_white",
                height=400
            )
            st.plotly_chart(fig_pie, use_container_width=True)

# ----------------- Tab 2: 월별 매출 분석 -----------------
with tab2:
    if df_filtered.empty:
        st.warning("선택된 필터에 해당하는 데이터가 없습니다.")
    else:
        # 월별 멜팅 데이터 생성
        df_melted = get_melted_data(df_filtered)
        
        col_t1, col_t2 = st.columns([3, 1])
        with col_t2:
            st.markdown("##### 🔍 월별 조회 설정")
            target_year = st.selectbox("분석 대상 연도 선택", options=sorted(selected_years), index=len(selected_years)-1 if selected_years else 0)
            
        # 해당 연도 필터링
        df_year_melted = df_melted[df_melted['연도'] == target_year]
        monthly_trend = df_year_melted.groupby('월')[['수량', '금액']].sum().reset_index()
        
        with col_t1:
            st.subheader(f"📅 {target_year}년 월별 매출 추이")
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=monthly_trend['월'].astype(str) + "월",
                y=monthly_trend['금액'],
                name='매출액 (K-USD)',
                marker_color='#4D96FF'
            ))
            fig_trend.add_trace(go.Scatter(
                x=monthly_trend['월'].astype(str) + "월",
                y=monthly_trend['수량'],
                name='판매량 (개)',
                mode='lines+markers',
                line=dict(color='#FF6B6B', width=2),
                yaxis='y2'
            ))
            fig_trend.update_layout(
                yaxis=dict(title="매출 금액 (K-USD)"),
                yaxis2=dict(title="수량 (개)", overlaying="y", side="right", showgrid=False),
                legend=dict(x=0.01, y=0.99),
                template="plotly_white",
                height=400
            )
            st.plotly_chart(fig_trend, use_container_width=True)
            
        st.markdown("---")
        
        # 모델별 Top 10
        st.subheader(f"🏆 {target_year}년 베스트셀러 모델 Top 10")
        model_rank = df_year_melted.groupby('모델명')[['금액', '수량']].sum().sort_values(by='금액', ascending=False).head(10).reset_index()
        
        fig_rank = px.bar(
            model_rank,
            x='금액',
            y='모델명',
            orientation='h',
            text='금액',
            color='금액',
            color_continuous_scale='Blues',
            labels={'금액': '매출액 (K-USD)', '모델명': '모델 ID'}
        )
        fig_rank.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            template="plotly_white",
            height=400
        )
        fig_rank.update_traces(texttemplate='%{text:,.2f}', textposition='outside')
        st.plotly_chart(fig_rank, use_container_width=True)

# ----------------- Tab 3: 정제 데이터 조회 -----------------
with tab3:
    st.subheader("🔍 실적 데이터 마스터 테이블 (코웨이 전담)")
    st.markdown("엑셀에서 헤더 불일치, 중합 및 공백 이슈를 클렌징한 최종 정제 데이터입니다.")
    
    # 텍스트 검색 기능
    search_query = st.text_input("모델명 또는 제품군 검색", "")
    df_view = df_filtered.copy()
    if search_query:
        df_view = df_view[df_view['모델명'].astype(str).str.contains(search_query, case=False) | 
                          df_view['제품'].astype(str).str.contains(search_query, case=False)]
        
    st.dataframe(df_view, use_container_width=True)
    
    # CSV 다운로드
    csv_data = df_view.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 정제 데이터 CSV 다운로드",
        data=csv_data,
        file_name="coway_sales_cleaned.csv",
        mime="text/csv"
    )

# ----------------- Tab 4: DB 적재 및 정합성 검증 -----------------
with tab4:
    st.subheader("🔗 데이터베이스 정합성 실시간 검증")
    st.markdown("""
    정제된 엑셀 실적 데이터가 데이터베이스(DB)에 정확하게 들어갔는지 자동으로 확인하는 시스템입니다.
    아래 **[DB 입력 및 정합성 검증 시작]** 버튼을 클릭하면, Pandas 메모리 데이터와 가상의 SQLite 데이터베이스 적재값을 비교 대조합니다.
    """)
    
    # 세션 상태에 DB 연결 객체 설정
    if 'db_conn' not in st.session_state:
        st.session_state.db_conn = sqlite3.connect(':memory:', check_same_thread=False)
        
    if st.button("🚀 DB 입력 및 정합성 검증 시작", type="primary"):
        conn = st.session_state.db_conn
        
        # 1. 멜팅된 정밀 데이터를 DB 테이블로 적재
        df_melted_all = get_melted_data(df_filtered)
        
        if df_melted_all.empty:
            st.error("적재할 데이터가 존재하지 않습니다.")
        else:
            with st.spinner("DB 테이블 생성 및 데이터 적재(INSERT) 중..."):
                # SQLite에 to_sql을 통해 적재 실행
                df_melted_all.to_sql('sales_records', conn, if_exists='replace', index=False)
                
            st.info("📦 데이터베이스 적재 완료! (Table: `sales_records` 생성됨)")
            
            # --- 검증 시작 ---
            st.markdown("### 🔍 정합성 검사 프로세스 작동")
            
            # 1단계: 행(Row) 건수 비교
            pandas_count = len(df_melted_all)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sales_records")
            db_count = cursor.fetchone()[0]
            
            st.markdown("#### 1. 건수 검증 (Row Count Validation)")
            if pandas_count == db_count:
                st.success(f"✅ **건수 검증 통과 (일치)**: Pandas ({pandas_count}건) == Database ({db_count}건)")
            else:
                st.error(f"❌ **건수 검증 실패 (불일치)**: Pandas ({pandas_count}건) != Database ({db_count}건)")
                
            # 2단계: 핵심 수치 합계 비교
            pandas_qty_sum = df_melted_all['수량'].sum()
            pandas_amt_sum = df_melted_all['금액'].sum()
            
            cursor.execute("SELECT SUM(수량), SUM(금액) FROM sales_records")
            db_qty_sum, db_amt_sum = cursor.fetchone()
            db_qty_sum = db_qty_sum or 0
            db_amt_sum = db_amt_sum or 0
            
            st.markdown("#### 2. 수치 합계 검증 (Aggregated Sum Validation)")
            qty_match = abs(pandas_qty_sum - db_qty_sum) < 0.01
            amt_match = abs(pandas_amt_sum - db_amt_sum) < 0.01
            
            if qty_match:
                st.success(f"✅ **수량 합계 검증 통과**: Pandas ({pandas_qty_sum:,.1f}개) == Database ({db_qty_sum:,.1f}개)")
            else:
                st.error(f"❌ **수량 합계 검증 실패**: Pandas ({pandas_qty_sum:,.1f}개) != Database ({db_qty_sum:,.1f}개)")
                
            if amt_match:
                st.success(f"✅ **금액 합계 검증 통과**: Pandas ({pandas_amt_sum:,.2f} K-USD) == Database ({db_amt_sum:,.2f} K-USD)")
            else:
                st.error(f"❌ **금액 합계 검증 실패**: Pandas ({pandas_amt_sum:,.2f} K-USD) != Database ({db_amt_sum:,.2f} K-USD)")
                
            # 3단계: 무작위 샘플링 검증 (Spot Check / Random Sampling)
            st.markdown("#### 3. 무작위 샘플 매칭 검증 (Random Spot Check)")
            samples = df_melted_all.sample(n=min(3, len(df_melted_all)))
            
            sample_results = []
            for _, row in samples.iterrows():
                y = row['연도']
                model = row['모델명']
                m = row['월']
                p_qty = row['수량']
                p_amt = row['금액']
                
                # DB에서 해당 값 1:1 쿼리
                cursor.execute(
                    "SELECT 수량, 금액 FROM sales_records WHERE 연도=? AND 모델명=? AND 월=?",
                    (y, model, m)
                )
                db_res = cursor.fetchone()
                
                if db_res:
                    db_qty, db_amt = db_res
                    match = (abs(p_qty - db_qty) < 0.01) and (abs(p_amt - db_amt) < 0.01)
                    status = "✅ 일치" if match else "❌ 불일치"
                else:
                    db_qty, db_amt = 0, 0
                    status = "❌ DB 미검색"
                    
                sample_results.append({
                    "연도": y,
                    "모델명": model,
                    "월": f"{m}월",
                    "Pandas 수량": p_qty,
                    "DB 수량": db_qty,
                    "Pandas 금액": p_amt,
                    "DB 금액": db_amt,
                    "검증 상태": status
                })
                
            st.table(pd.DataFrame(sample_results))
            
            # 최종 정합성 판정
            if pandas_count == db_count and qty_match and amt_match and all(r['검증 상태'] == "✅ 일치" for r in sample_results):
                st.success("🎉 **데이터베이스 정합성 검증 완료**: 데이터 누락 및 위변조 없이 안전하게 적재되었습니다.")
            else:
                st.warning("⚠️ **정합성 경고**: 일부 검증 단계에서 오차가 식별되었습니다. 원본 데이터 소스를 체크하세요.")

# ----------------- Tab 5: 월별 물량 예측 -----------------
with tab5:
    st.subheader("🔮 2026년 월별 물량 및 매출 예측")
    st.markdown("""
    과거 3개년(2023~2025) 데이터의 계절성 패턴과 2026년 현재까지 축적된 실제 데이터를 바탕으로,
    2026년 전체 및 남은 월의 예상 판매량과 매출액을 예측합니다.
    """)
    
    # 1. 예측 대상 필터링
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        st.markdown("##### ⚙️ 예측 옵션 설정")
        # 모델 선택
        model_type = st.radio(
            "예측 모델 선택",
            options=["계절성 지수 모델 (Seasonal Index)", "Prophet 시계열 ML 모델 (Prophet)"]
        )
        
        # 품목 세부 필터
        pred_product = st.selectbox(
            "예측 대상 제품군",
            options=["전체"] + sorted(df_raw['제품'].dropna().unique().tolist())
        )
        
        # 선택한 제품군의 모델명들 리스트업
        if pred_product == "전체":
            model_options = sorted(df_raw['모델명'].dropna().unique().tolist())
        else:
            model_options = sorted(df_raw[df_raw['제품'] == pred_product]['모델명'].dropna().unique().tolist())
            
        pred_model = st.selectbox(
            "예측 대상 상세 모델 (선택)",
            options=["전체 모델 합계"] + model_options
        )
        
    # 데이터 필터 적용
    df_pred_source = df_raw.copy()
    if pred_product != "전체":
        df_pred_source = df_pred_source[df_pred_source['제품'] == pred_product]
    if pred_model != "전체 모델 합계":
        df_pred_source = df_pred_source[df_pred_source['모델명'] == pred_model]
        
    if df_pred_source.empty:
        st.warning("선택된 필터에 해당하는 예측 분석 대상 데이터가 없습니다.")
    else:
        # 엔진 임포트 및 예측 수행
        import prediction_engine
        
        # 2026년 실제 데이터 마지막 월 동적 감지
        last_m = prediction_engine.get_last_actual_month_2026(df_raw)
        
        # 예측 데이터 프레임 생성
        with st.spinner("예측 모델을 학습하고 결과를 계산 중입니다..."):
            if "Seasonal" in model_type:
                df_forecast = prediction_engine.forecast_seasonal_index(df_pred_source, None, last_m)
                is_prophet = False
            else:
                df_forecast = prediction_engine.forecast_prophet(df_pred_source, last_m)
                is_prophet = True
                
        if df_forecast.empty:
            st.error("예측을 수행하기에 과거 데이터가 충분하지 않거나 형식이 올바르지 않습니다.")
        else:
            # 2. 시각화 그래프 생성
            with col_p2:
                # 차트 그리기
                fig_forecast = go.Figure()
                
                # 실제 실적 영역 (1월 ~ last_m)
                df_actual = df_forecast.iloc[:last_m]
                df_pred = df_forecast.iloc[last_m-1:] # 끊김 없이 그리도록 마지막 실제월부터 예측 시작
                
                # 수량 차트
                fig_forecast.add_trace(go.Scatter(
                    x=df_actual['월'],
                    y=df_actual['수량'],
                    name='실제 수량 (개)',
                    mode='lines+markers',
                    line=dict(color='#4D96FF', width=3)
                ))
                
                fig_forecast.add_trace(go.Scatter(
                    x=df_pred['월'],
                    y=df_pred['수량'],
                    name='예측 수량 (개)',
                    mode='lines+markers',
                    line=dict(color='#FF6B6B', width=3, dash='dash')
                ))
                
                # Prophet일 경우 신뢰구간 추가
                if is_prophet and '수량_최소' in df_forecast.columns:
                    fig_forecast.add_trace(go.Scatter(
                        x=df_forecast['월'],
                        y=df_forecast['수량_최대'],
                        fill=None,
                        mode='lines',
                        line_color='rgba(255, 107, 107, 0.1)',
                        showlegend=False
                    ))
                    fig_forecast.add_trace(go.Scatter(
                        x=df_forecast['월'],
                        y=df_forecast['수량_최소'],
                        fill='tonexty',
                        mode='lines',
                        line_color='rgba(255, 107, 107, 0.1)',
                        fillcolor='rgba(255, 107, 107, 0.1)',
                        name='신뢰 구간 (수량)',
                        showlegend=True
                    ))
                    
                fig_forecast.update_layout(
                    title=f"📅 2026년 월별 물량(수량) 예측 트렌드 ({pred_product} / {pred_model})",
                    xaxis_title="월",
                    yaxis_title="수량 (개)",
                    template="plotly_white",
                    height=450,
                    legend=dict(x=0.01, y=0.99)
                )
                st.plotly_chart(fig_forecast, use_container_width=True)
                
            # 3. 상세 분석 지표 및 테이블
            st.markdown("---")
            st.markdown("### 📊 2026년 월별 예측 상세 수치")
            
            # 메트릭 카드 영역
            tot_qty_2026 = df_forecast['수량'].sum()
            tot_amt_2026 = df_forecast['금액'].sum()
            
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric(
                    label="2026년 연간 누적+예측 총 수량",
                    value=f"{tot_qty_2026:,.0f} 개",
                    delta=f"실제치({last_m}월까지): {df_forecast.iloc[:last_m]['수량'].sum():,.0f} 개"
                )
            with col_m2:
                st.metric(
                    label="2026년 연간 누적+예측 총 매출",
                    value=f"{tot_amt_2026:,.2f} K-USD",
                    delta=f"실제치({last_m}월까지): {df_forecast.iloc[:last_m]['금액'].sum():,.2f} K-USD"
                )
            with col_m3:
                st.metric(
                    label="예측 기준 시점",
                    value=f"2026년 {last_m}월 실적 기준",
                    delta=f"예측 대상: {last_m+1}월 ~ 12월"
                )
                
            # 예측 상세 테이블 표시
            df_table_show = df_forecast.copy()
            
            # 수치 형식 변환 적용
            df_table_show['수량'] = df_table_show['수량'].map('{:,.1f}'.format)
            df_table_show['금액'] = df_table_show['금액'].map('{:,.2f}'.format)
            if '수량_최소' in df_table_show.columns:
                df_table_show['수량_최소'] = df_table_show['수량_최소'].map('{:,.1f}'.format)
                df_table_show['수량_최대'] = df_table_show['수량_최대'].map('{:,.1f}'.format)
                
            st.dataframe(df_table_show, use_container_width=True)
            
            # 예측 결과 CSV 다운로드
            pred_csv = df_forecast.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 2026년 예측 데이터 CSV 다운로드",
                data=pred_csv,
                file_name=f"forecast_2026_{pred_product}_{pred_model}.csv",
                mime="text/csv"
            )
