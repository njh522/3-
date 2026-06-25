import streamlit as st
import pandas as pd
from prophet import Prophet
import plotly.express as px
import plotly.graph_objects as go
import datetime
import data_processor as dp
import importlib
importlib.reload(dp)
import sys
import os

# 1. 앱 제목 및 페이지 설정
st.set_page_config(page_title="영업팀 판매량 예측기", layout="wide", page_icon="🏭", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"]  { font-family: 'Inter', 'Noto Sans KR', sans-serif; }
div[data-testid="metric-container"] {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-radius: 15px;
    padding: 20px;
    transition: transform 0.2s;
}
div[data-testid="metric-container"]:hover { transform: translateY(-5px); border: 1px solid rgba(255, 255, 255, 0.3); }
.stTabs [data-baseweb="tab-list"] { gap: 15px; }
.stTabs [data-baseweb="tab"] { border-radius: 5px 5px 0px 0px; padding: 10px 20px; background-color: transparent; border-bottom: 2px solid transparent; }
.stTabs [aria-selected="true"] { border-bottom: 2px solid #FF3366; color: #FF3366 !important; font-weight:bold; }
h1, h2, h3 { color: #F8F9FA; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("📈 영업팀 판매량 예측기: Rolling Forecast (V5.0)")
st.markdown("<p style='color:#A0AEC0; font-size:1.1rem;'>과거 3개년의 출하 실적 분석과 고객사 Forecast를 결합하여 최종 수요 계획을 수립함으로써 예측의 신뢰도를 극대화합니다.<br>데이터 기반의 체계적인 AI 분석으로 미래 물동량을 전망하여 영업담당자의 소극적인 물량 반영을 보완하고, 공급 부족(결품) 리스크 최소화 및 과재고 방지를 동시에 달성하는 의사결정 지원 플랫폼입니다.</p>", unsafe_allow_html=True)

base_dir = r"C:\Users\power\OneDrive\바탕 화면\영업팀 실적파일"

# 우선 거래선 목록 (상단 노출)
PRIORITY_CUSTOMERS = ['Coway']

@st.cache_data
def load_dashboard_v5():
    sales_df = dp.load_and_merge_data(base_dir)
    if sales_df is None or sales_df.empty:
        return None, None, None
    analysis_df = dp.analyze_models(sales_df)
    inv_df = dp.extract_inventory(base_dir)
    return sales_df, analysis_df, inv_df

sales_df, analysis_df, inv_df = load_dashboard_v5()

if sales_df is None:
    st.error(f"데이터를 불러오지 못했습니다. 경로 확인: {base_dir}")
    st.stop()

# --- 사이드바: 고객사 FCST 업로드 및 동기화 ---
st.sidebar.markdown("### 📥 고객사 FCST 업로드")
uploaded_fcst = st.sidebar.file_uploader("고객사 FCST 엑셀 파일 (.xlsx)", type=["xlsx"])
if uploaded_fcst is not None:
    fcst_save_path = os.path.join(base_dir, "12주_FCST.xlsx")
    try:
        with open(fcst_save_path, "wb") as f:
            f.write(uploaded_fcst.getbuffer())
        st.sidebar.success("✅ 고객사 FCST 업로드 및 동기화 완료!")
    except Exception as e:
        st.sidebar.error(f"❌ 파일 저장 실패: {e}")
st.sidebar.markdown("---")

# --- 사이드바: 거래선 필터 ---
st.sidebar.markdown("### 🏢 거래선 필터")
all_customers = sorted(sales_df['customer'].unique())

# 우선 거래선을 맨 위로
priority_present = [c for c in PRIORITY_CUSTOMERS if c in all_customers]
other_customers = [c for c in all_customers if c not in PRIORITY_CUSTOMERS]
ordered_customers = priority_present + other_customers

# 기본값: Coway만 선택
filter_mode = st.sidebar.radio("보기 모드", ["🎯 우선 거래선만 (Coway)", "📋 전체 거래선", "🔧 직접 선택"], index=0)

if filter_mode == "🎯 우선 거래선만 (Coway)":
    selected_customers = priority_present
elif filter_mode == "📋 전체 거래선":
    selected_customers = all_customers
else:
    selected_customers = st.sidebar.multiselect("거래선 선택", ordered_customers, default=priority_present)

# 필터된 데이터
filtered_sales = sales_df[sales_df['customer'].isin(selected_customers)]
filtered_analysis = analysis_df[analysis_df['업체(거래선)'].isin(selected_customers)]

# --- 상단 메트릭 ---
st.markdown("### 📊 거래선 기질 및 재고 요약")
filter_label = ", ".join(selected_customers) if len(selected_customers) <= 3 else f"{len(selected_customers)}개 거래선"
st.caption(f"📌 현재 필터: **{filter_label}**")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("등록 모델 수", f"{filtered_analysis['model'].nunique()} 종")
with col2:
    vol_cnt = len(filtered_analysis[filtered_analysis['불규칙오더(변동성) 등급'].str.contains('극심')])
    st.metric("🚨 긴급오더 요주의 모델", f"{vol_cnt:,} 종")
with col3:
    season_cnt = len(filtered_analysis[~filtered_analysis['역대 데이터 성수기 패턴'].str.contains('부족|균등|없음')])
    st.metric("⏰ 계절성 보유 모델", f"{season_cnt:,} 종")

st.markdown("---")

tab1, tab2, tab3 = st.tabs([
    "🎯 [메인] 4개월 롤링 Forecast",
    "🏢 오더 습성 전체 목록",
    "🔍 단일 품목 연도별 비교 & AI 인사이트"
])

# 1. 생판회의용
with tab1:
    st.subheader("🎯 M ~ M+3 Rolling Forecast 조달 계획")
    st.markdown("당월(M)부터 향후 3개월(M+3)까지 총 4개월간의 수요를 종합하여 최적의 조달 물량을 수립합니다. 각 모델의 **오더 변동성(버퍼율)**을 실시간 연산하여 **최종 추천 조달량**을 산출합니다.")

    st.markdown("---")
    st.markdown("#### ⚙️ 생판 반영물량 산출 설정")
    forecast_base = st.radio(
        "수요 및 조달 계획 계산 기준",
        [
            "🤖 Prophet AI 예측치 (기존 출하 통계 기반)",
            "📦 2주 선행 생산 반영 물량 (고객사 FCST 기반 + 4개월차 AI 대체)"
        ],
        index=0,
        help="고객사 FCST 연동 시, 제공된 주간 및 일간 데이터를 월별로 합산하고 2주(14일) 선행 시프트하여 생산 반영물량을 도출합니다. 데이터가 부족한 4개월차는 AI 예측치로 자동 대체됩니다."
    )
    st.markdown("---")

    if st.button("🚀 전체 모델 4개월물량 AI 계산 추출", type="primary"):
        pred_df, tgt_months = dp.load_rolling_forecast_cache(base_dir)

        if pred_df is not None and len(pred_df) > 0:
            st.success("💾 오프라인 AI 예측 캐시를 로드하였습니다. (0.1초 소요)")
        else:
            st.warning("⚠️ 캐시 없음. 실시간 Prophet AI 예측 연산을 시작합니다. (수 분 소요)")
            with st.spinner("한국 공휴일 반영 및 4개월치 Forecast Rolling 연산 중..."):
                pred_df, tgt_months = dp.generate_rolling_4m_forecast(filtered_sales)
                import os
                try:
                    pred_df.to_csv(os.path.join(base_dir, "rolling_forecast_cache.csv"), index=False, encoding='utf-8-sig')
                except Exception:
                    pass

        # 고객사 FCST 데이터 파싱 및 연동
        fcst_df = None
        if "2주 선행 생산" in forecast_base:
            fcst_file_path = os.path.join(base_dir, "12주_FCST.xlsx")
            if os.path.exists(fcst_file_path):
                mapping = dp.extract_code_model_mapping(base_dir)
                fcst_df = dp.parse_customer_fcst(fcst_file_path, mapping)
                if fcst_df is not None and not fcst_df.empty:
                    st.success(f"🔗 고객사 FCST 엑셀 연동에 성공했습니다. (매칭된 코드 수: {fcst_df['model'].nunique()}종)")
                else:
                    st.warning("⚠️ 고객사 FCST 파일 파싱 실패 또는 데이터가 비어있습니다. AI 예측치로 대체합니다.")
            else:
                st.warning("⚠️ 고객사 FCST 파일이 존재하지 않습니다. 사이드바에서 파일을 업로드해 주세요. AI 예측치로 대체합니다.")

        # 선택된 거래선만 필터
        pred_df = pred_df[pred_df['업체(거래선)'].isin(selected_customers)]

        # 만약 FCST 연동에 성공했고, 데이터가 있다면 pred_df 값 대체
        if fcst_df is not None and not fcst_df.empty:
            for mon in tgt_months:
                col_name = f"{mon.year}년 {mon.month}월"
                if col_name in pred_df.columns:
                    fcst_mon_df = fcst_df[fcst_df['month'] == mon]
                    if not fcst_mon_df.empty:
                        # 2주 선행 생산량으로 대체
                        prod_map = dict(zip(fcst_mon_df['model'], fcst_mon_df['prod_qty']))
                        pred_df[col_name] = pred_df['model'].map(prod_map).fillna(pred_df[col_name]).round().astype(int)
            
            # 4개월 총합계(자재준비) 재계산
            month_cols = [f"{mon.year}년 {mon.month}월" for mon in tgt_months if f"{mon.year}년 {mon.month}월" in pred_df.columns]
            pred_df['4개월 총합계(자재준비)'] = pred_df[month_cols].sum(axis=1)

        final_df = pred_df.merge(filtered_analysis, how='left', on=['업체(거래선)', 'model'])

        if inv_df is not None and not inv_df.empty:
            final_df = final_df.merge(inv_df, how='left', on='model')
        else:
            final_df['inventory'] = 0

        # 고객 요구량 및 생산선행량 총합 합산 열 추가
        if fcst_df is not None and not fcst_df.empty:
            fcst_sum = fcst_df.groupby('model')['fcst_qty'].sum().reset_index()
            fcst_sum.columns = ['model', '고객 요구량 합계(3개월)']
            final_df = final_df.merge(fcst_sum, how='left', on='model').fillna({'고객 요구량 합계(3개월)': 0})
            
            prod_sum = fcst_df.groupby('model')['prod_qty'].sum().reset_index()
            prod_sum.columns = ['model', '생산 선행량 합계(3개월)']
            final_df = final_df.merge(prod_sum, how='left', on='model').fillna({'생산 선행량 합계(3개월)': 0})

        final_df = dp.calculate_net_requirements(final_df)

        month_cols = [f"{mon.year}년 {mon.month}월" for mon in tgt_months]
        cols = [
            '업체(거래선)', 'model', '불규칙오더(변동성) 등급'
        ] + month_cols

        cols += ['4개월 총합계(자재준비)', '최종 추천 조달량']

        # 존재하는 컬럼만 선택
        cols = [c for c in cols if c in final_df.columns]
        show_final = final_df[cols].sort_values(by='최종 추천 조달량', ascending=False).reset_index(drop=True)

        # tab2 오더 습성 정렬 연동을 위해 모델 순서를 session_state에 저장
        st.session_state['model_order'] = show_final['model'].tolist()

        # 📊 요약 메트릭 배치
        st.markdown("#### 📊 이번 달 롤링 조달 계획 요약")
        sum_col1, sum_col2, sum_col3 = st.columns(3)
        total_req = show_final['4개월 총합계(자재준비)'].sum() if '4개월 총합계(자재준비)' in show_final.columns else 0
        total_net = show_final['순소요량'].sum() if '순소요량' in show_final.columns else 0
        total_proc = show_final['최종 추천 조달량'].sum() if '최종 추천 조달량' in show_final.columns else 0
        
        with sum_col1:
            st.metric("총 4개월 예측량", f"{int(total_req):,} 개")
        with sum_col2:
            st.metric("총 순소요량", f"{int(total_net):,} 개")
        with sum_col3:
            st.metric("총 추천 조달량", f"{int(total_proc):,} 개")

        st.markdown("#### 📋 조달 세부 계획 테이블")
        st.dataframe(show_final, use_container_width=True, height=600)

        csv = show_final.to_csv(index=False).encode('utf-8-sig')
        st.download_button("생판회의 결과 엑셀 반출 (CSV)", data=csv, file_name="영업회의_4m_Rolling_Forecast_kr.csv")

# 2. 고객사 분석
with tab2:
    st.subheader("🏢 업체별 오더 습성 및 기질 파노라마")
    st.markdown("특정 업체가 FCST 관리를 잘 안 하고 갑자기 들이닥치는지(극심), 혹은 매달 꼬박꼬박 가져가는 안정형 효자(안정)인지 3년 치 표준편차를 기반으로 점수화(CV 등급)한 표입니다.")

    tab2_df = filtered_analysis[['업체(거래선)', 'model', '불규칙오더(변동성) 등급', '가이던스(액션플랜)', '역대 데이터 성수기 패턴']].copy()

    # tab1의 최종 추천 조달량 기준 정렬 순서와 연동
    if 'model_order' in st.session_state:
        model_order = st.session_state['model_order']
        tab2_df['_sort_key'] = tab2_df['model'].apply(
            lambda m: model_order.index(m) if m in model_order else len(model_order)
        )
        tab2_df = tab2_df.sort_values('_sort_key').drop(columns=['_sort_key']).reset_index(drop=True)

    st.dataframe(tab2_df, use_container_width=True, height=500)

# 3. 단일 품목 딥 분석
with tab3:
    st.subheader("🔍 단일 품목 연도별 비교 분석 & AI 예측 인사이트")
    st.markdown("선택한 품목의 **연도별 월 출하 패턴**을 한눈에 비교하고, AI가 예측한 **향후 전망**과 그 근거를 확인하세요.")

    colA, colB = st.columns(2)
    with colA:
        # 우선 거래선을 맨 위에 배치
        cust_list_tab3 = priority_present + [c for c in sorted(filtered_sales['customer'].unique()) if c not in PRIORITY_CUSTOMERS]
        selected_cust = st.selectbox("1. 업체(거래선) 선택", cust_list_tab3)
    with colB:
        # 해당 거래선의 모델을 활성 수량 기준으로 정렬
        cust_models_df = filtered_sales[filtered_sales['customer'] == selected_cust]
        model_totals = cust_models_df.groupby('model')['y'].sum().sort_values(ascending=False)
        active_models = model_totals[model_totals > 0].index.tolist()
        inactive_models = model_totals[model_totals == 0].index.tolist()
        model_list = active_models + inactive_models
        selected_model = st.selectbox("2. 분석할 모델 선택 (활성 수량순)", model_list) if model_list else None

    if selected_model:
        model_df = filtered_sales[(filtered_sales['customer'] == selected_cust) & (filtered_sales['model'] == selected_model)].sort_values(by='ds')
        
        # 모델의 단가 정보 가져오기
        model_meta = filtered_analysis[(filtered_analysis['업체(거래선)'] == selected_cust) & (filtered_analysis['model'] == selected_model)]
        unit_price = model_meta['단가(원)'].values[0] if not model_meta.empty and '단가(원)' in model_meta.columns else 0
        
        # 올해 누적 매출액 계산
        now = datetime.datetime.now()
        current_year = now.year
        current_month = now.month
        
        this_year_sales = model_df[model_df['ds'].dt.year == current_year]
        this_year_amount = this_year_sales['amount'].sum() if 'amount' in this_year_sales.columns else 0.0
        
        # 📌 상단에 모델 단가 및 매출액 정보 표시
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.info(f"💵 **평균 단가**: {int(unit_price):,} 원 / 개")
        with col_m2:
            st.success(f"📈 **{current_year}년 누적 매출액**: {this_year_amount:.2f} 백만 원")

        m_df_run = model_df.groupby('ds')['y'].sum().reset_index()

        m_df_run['year'] = m_df_run['ds'].dt.year
        m_df_run['month'] = m_df_run['ds'].dt.month
        past_data = m_df_run[m_df_run['ds'] < datetime.datetime(current_year, current_month, 1)]
        available_years = sorted(past_data['year'].unique())

        # --- 1. 연도별 월 오버레이 비교 차트 ---
        st.markdown("#### 📊 연도별 월 출하량 비교 차트")

        year_colors = {
            2023: '#6B7280',
            2024: '#60A5FA',
            2025: '#34D399',
            2026: '#FF3366',
            2027: '#F59E0B',
        }
        month_labels = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월']

        fig = go.Figure()

        for yr in available_years:
            yr_data = past_data[past_data['year'] == yr]
            if yr_data.empty or yr_data['y'].sum() == 0:
                continue
            color = year_colors.get(yr, '#9CA3AF')
            is_current = (yr == current_year)

            fig.add_trace(go.Scatter(
                x=yr_data['month'],
                y=yr_data['y'],
                mode='lines+markers',
                name=f'{yr}년' + (' (올해)' if is_current else ''),
                line=dict(
                    color=color,
                    width=3.5 if is_current else 1.8,
                    dash='solid' if is_current else 'dot'
                ),
                marker=dict(size=8 if is_current else 5, symbol='circle'),
                opacity=1.0 if is_current else 0.7
            ))

        # --- Prophet 예측 ---
        forecast_added = False
        if len(past_data) >= 6:
            try:
                import logging
                logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

                train_df = past_data[['ds', 'y']].copy()
                prophet_m = Prophet(yearly_seasonality=True, daily_seasonality=False,
                           weekly_seasonality=False, uncertainty_samples=200)
                prophet_m.add_country_holidays(country_name='KR')
                prophet_m.fit(train_df)

                future = prophet_m.make_future_dataframe(periods=7, freq='MS')
                fc = prophet_m.predict(future)

                forecast_start = datetime.datetime(current_year, current_month, 1)
                fc_future = fc[fc['ds'] >= forecast_start].copy()
                fc_future['month'] = fc_future['ds'].dt.month
                fc_future['fc_year'] = fc_future['ds'].dt.year

                fc_this_year = fc_future[fc_future['fc_year'] == current_year]

                if not fc_this_year.empty:
                    fc_months = fc_this_year['month'].values
                    yhat_upper = fc_this_year['yhat_upper'].clip(lower=0).values
                    yhat_lower = fc_this_year['yhat_lower'].clip(lower=0).values
                    yhat = fc_this_year['yhat'].clip(lower=0).values

                    fig.add_trace(go.Scatter(
                        x=list(fc_months) + list(fc_months[::-1]),
                        y=list(yhat_upper) + list(yhat_lower[::-1]),
                        fill='toself',
                        fillcolor='rgba(255, 51, 102, 0.12)',
                        line=dict(color='rgba(255,255,255,0)'),
                        name='AI 예측 신뢰구간 (80%)',
                        showlegend=True, hoverinfo='skip'
                    ))

                    fig.add_trace(go.Scatter(
                        x=fc_months, y=yhat,
                        mode='lines+markers',
                        name=f'{current_year}년 AI 예측',
                        line=dict(color='#FF3366', width=3, dash='dashdot'),
                        marker=dict(size=7, symbol='diamond', line=dict(width=1.5, color='white')),
                        opacity=0.9
                    ))
                    forecast_added = True

                    yr_actual = past_data[past_data['year'] == current_year]
                    if not yr_actual.empty:
                        last_m = yr_actual['month'].max()
                        last_v = yr_actual[yr_actual['month'] == last_m]['y'].values[0]
                        fig.add_trace(go.Scatter(
                            x=[last_m, fc_months[0]], y=[last_v, yhat[0]],
                            mode='lines', line=dict(color='#FF3366', width=2, dash='dashdot'),
                            showlegend=False, opacity=0.5
                        ))
            except Exception:
                pass

        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickmode='array', tickvals=list(range(1, 13)), ticktext=month_labels,
                       title='월', gridcolor='rgba(255,255,255,0.06)', range=[0.5, 12.5]),
            yaxis=dict(title='출하량 (개)', gridcolor='rgba(255,255,255,0.06)'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5, font=dict(size=12)),
            height=480, margin=dict(t=60, b=40), hovermode='x unified'
        )
        fig.add_vline(x=current_month - 0.5, line_dash="dot", line_color="rgba(255,255,255,0.3)",
                      annotation_text="현재", annotation_position="top")

        st.plotly_chart(fig, use_container_width=True)

        # --- 2. AI 분석 인사이트 카드 ---
        st.markdown("---")
        st.markdown("#### 🧠 AI 분석 인사이트")

        model_analysis = analysis_df[
            (analysis_df['업체(거래선)'] == selected_cust) &
            (analysis_df['model'] == selected_model)
        ]
        active_months = past_data[past_data['y'] > 0]
        total_months_cnt = len(past_data)
        active_count = len(active_months)

        col_i1, col_i2, col_i3 = st.columns(3)

        with col_i1:
            st.markdown("""<div style='background: linear-gradient(135deg, rgba(255,51,102,0.15), rgba(255,51,102,0.05));
                border-radius:12px; padding:20px; border-left: 4px solid #FF3366;'>
                <h4 style='margin:0 0 12px 0; color:#FF3366;'>📈 변동성 분석</h4>""", unsafe_allow_html=True)
            if not model_analysis.empty:
                st.markdown(f"**등급**: {model_analysis.iloc[0]['불규칙오더(변동성) 등급']}")
                st.markdown(f"**CV 지수**: {model_analysis.iloc[0]['12개월 평점(CV)']:.2f}")
                st.markdown(f"**권장 조치**: {model_analysis.iloc[0]['가이던스(액션플랜)']}")
            else:
                st.markdown("분석 데이터 없음")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_i2:
            st.markdown("""<div style='background: linear-gradient(135deg, rgba(96,165,250,0.15), rgba(96,165,250,0.05));
                border-radius:12px; padding:20px; border-left: 4px solid #60A5FA;'>
                <h4 style='margin:0 0 12px 0; color:#60A5FA;'>🌊 계절성 & 패턴</h4>""", unsafe_allow_html=True)
            if not model_analysis.empty:
                st.markdown(f"**성수기 패턴**: {model_analysis.iloc[0]['역대 데이터 성수기 패턴']}")
            if not past_data.empty and active_count > 0:
                monthly_avg = past_data.groupby('month')['y'].mean()
                if monthly_avg.sum() > 0:
                    peak_month = monthly_avg.idxmax()
                    overall_avg = monthly_avg.mean()
                    if overall_avg > 0:
                        st.markdown(f"**최대 출하월**: {int(peak_month)}월 (평균 대비 {monthly_avg.max()/overall_avg:.1f}배)")
                    low_vals = monthly_avg[monthly_avg > 0]
                    if not low_vals.empty:
                        st.markdown(f"**최소 출하월**: {int(low_vals.idxmin())}월")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_i3:
            st.markdown("""<div style='background: linear-gradient(135deg, rgba(52,211,153,0.15), rgba(52,211,153,0.05));
                border-radius:12px; padding:20px; border-left: 4px solid #34D399;'>
                <h4 style='margin:0 0 12px 0; color:#34D399;'>🎯 예측 근거 요약</h4>""", unsafe_allow_html=True)
            if not past_data.empty:
                st.markdown(f"**학습 기간**: {past_data['ds'].min().strftime('%Y.%m')} ~ {past_data['ds'].max().strftime('%Y.%m')}")
            st.markdown(f"**총 데이터**: {total_months_cnt}개월 (활성 {active_count}개월)")
            if total_months_cnt >= 12:
                st.markdown("**예측 방식**: Prophet 시계열 AI")
                st.markdown("**반영 요소**: 한국 공휴일, 연간 계절성, 장기 추세")
            elif total_months_cnt >= 3:
                st.markdown("**예측 방식**: 최근 3개월 이동평균")
            else:
                st.markdown("**예측 방식**: 판단 불가 (데이터 부족)")
            st.markdown("</div>", unsafe_allow_html=True)

        # --- 3. 상세 수치 테이블 ---
        st.markdown("")
        with st.expander("📋 연도별 월 출하량 상세 수치 테이블", expanded=False):
            if not past_data.empty:
                pivot = past_data.pivot_table(index='year', columns='month', values='y', aggfunc='sum', fill_value=0)
                pivot.columns = [f'{int(m)}월' for m in pivot.columns]
                pivot.index = [f'{int(y)}년' for y in pivot.index]
                pivot['연합계'] = pivot.sum(axis=1)
                st.dataframe(pivot, use_container_width=True)

        # --- 4. 전년 동기 비교 ---
        if current_year in available_years and (current_year - 1) in available_years:
            this_yr = past_data[(past_data['year'] == current_year) & (past_data['month'] <= current_month - 1)]
            last_yr = past_data[(past_data['year'] == current_year - 1) & (past_data['month'] <= current_month - 1)]
            this_total = this_yr['y'].sum()
            last_total = last_yr['y'].sum()
            if last_total > 0:
                growth = (this_total - last_total) / last_total * 100
                growth_icon = "📈" if growth > 0 else "📉"
                growth_color = "#34D399" if growth > 0 else "#FF3366"
                st.markdown(f"""
                <div style='background: rgba(255,255,255,0.03); border-radius:12px; padding:16px 24px;
                    margin-top:8px; border: 1px solid rgba(255,255,255,0.08);'>
                    <span style='font-size:1.1rem;'>{growth_icon} <strong>전년 동기 대비</strong> (1~{current_month-1}월):
                    올해 <strong>{int(this_total):,}</strong> vs 작년 <strong>{int(last_total):,}</strong>
                    <span style='color:{growth_color}; font-weight:bold; font-size:1.2rem;'>{growth:+.1f}%</span></span>
                </div>
                """, unsafe_allow_html=True)
