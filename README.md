# [코웨이 영업] 데이터 기반 수요 예측 분석기 & DB 검증 시스템

본 프로젝트는 로컬에 분산되어 관리되는 과거 3개년 매출 실적 엑셀 자료를 SQLite 데이터베이스로 자동 이관하고, 최첨단 시계열 머신러닝 알고리즘(Facebook Prophet)을 활용하여 미래 수요를 다이내믹하게 시뮬레이션 및 예측하는 대시보드 시스템입니다.

---

## 🎨 주요 특징 및 기능 (Features)

1. **자동화된 엑셀-DB 동기화 (Sync)**
   - 로컬 엑셀 파일들(`23년~26년 매출 실적.xlsx`)의 최종 수정시각(`mtime`)을 감지하여, 엑셀 파일이 업데이트되었을 때만 SQLite DB(`actual_sales` 테이블)로 데이터를 백그라운드에서 자동 재적재합니다.
   - 매번 대용량 엑셀을 로드할 필요가 없어 **1초 미만의 강력한 대시보드 로딩 속도**를 자랑합니다.

2. **한글 깨짐 없는 정밀 데이터 클렌징**
   - 엑셀 시트 내의 한글 깨짐 현상과 무관하게, 정규식 필터링(`^[A-Za-z0-9\-_()/ ]+$`)을 적용하여 중복 집계를 유발하는 요약 행(소계, 합계)을 원천 배제하고 **순수 개별 품목(모델명)의 실적 데이터만 안전하게 적재**합니다.

3. **다이내믹 예측 시점 제어 (Predictive 분계선)**
   - 사용자가 대시보드 상에서 예측 기준 월($M$)을 선택하면, 직전 월($M-1$)까지는 정확한 2026년 실제 출하량(실선)으로 표현하고, 기준 월($M$)부터는 AI 예측값(점선)으로 시각화합니다.
   - 예측 시점 변경 시 Prophet 시계열 학습 범위도 해당 시점으로 실시간 제한되어 보다 신뢰도 높은 시뮬레이션이 가능합니다.

4. **종합 PSI 대조 및 영업 감(感) 조율 기능**
   - 당월 포함 4개월의 **AI 최종 추천량**, **과거 3개년 동월 평균 출하량**, **직전 연도(2025년) 동월 실적**, **고객사 Forecast 계획량(수동 입력 및 엑셀 업로드 지원)**을 한눈에 비교할 수 있는 대규모 대조 테이블을 제공합니다.

5. **정량적 AI 예측 판단 사유 제공**
   - 기계적인 성수기/비수기 룰성 코멘트 대신, **전월비(MoM) 변동률** 및 **과거 3개년 동월 평균 출하량 대비 상·하회 격차**를 정량적으로 분석하여 실무용 판단 근거로 렌더링합니다.

---

## 📁 프로젝트 구조 (Directory Structure)

```text
영업팀 실적파일/
│
├── app.py                      # Streamlit 웹 대시보드 메인 소스 코드
├── prediction_engine.py         # Prophet 기반 시계열 예측 연산 엔진
├── sales_forecast.db           # SQLite 로컬 데이터베이스
│
├── 23년 매출 실적.xlsx          # 2023년 실적 데이터 소스 (시트명: 23년(세부_실적))
├── 24년 매출 실적.xlsx          # 2024년 실적 데이터 소스 (시트명: 24년(세부_실적))
├── 25년 매출 실적.xlsx          # 2025년 실적 데이터 소스 (시트명: 25년(세부_실적))
├── 26년 매출 실적.xlsx          # 2026년 실적 데이터 소스 (시트명: 26년(세부_실적))
│
├── requirements.txt            # 파이썬 실행 필수 패키지 목록
└── README.md                   # 시스템 사용 설명서 (본 파일)
```

---

## 🛠️ 기술 스택 (Tech Stack)

- **Language**: Python 3.8+
- **Frontend**: Streamlit (Premium Custom CSS 및 레이아웃 설계)
- **Analytics & ML**: Facebook Prophet, Pandas, NumPy
- **Database**: SQLite3 (로컬 파일형 초경량 RDBMS)
- **Visualization**: Plotly Graph Objects (인터랙티브 시각화 차트)
- **Excel Handler**: OpenPyXL

---

## 🚀 시작하기 (How to Run)

### 1. 패키지 설치
로컬 PC의 터미널(CMD 또는 PowerShell)을 열고, 프로젝트 폴더 경로로 이동하여 아래 명령어를 통해 필수 패키지를 설치합니다.
```bash
pip install -r requirements.txt
```

### 2. 대시보드 실행
설치가 완료되면 다음 명령어로 Streamlit 로컬 서버를 기동합니다.
```bash
streamlit run app.py
```
서버가 켜지면 크롬 등 기본 브라우저에 대시보드 화면(`http://localhost:8501`)이 자동으로 나타납니다.

---

## 🗄️ 데이터베이스 스키마 (Database Schema)

로컬 `sales_forecast.db` 파일 내부에는 총 4개의 테이블이 정의되어 실적 보관 및 동기화 상태를 추적합니다.

### 1. `actual_sales` (3개년 실제 출하 실적)
- **컬럼**: `id` (PK), `item_code` (품목명), `year` (연도), `month` (월), `qty` (출하 수량), `amount` (매출 금액)
- **제약**: `UNIQUE(item_code, year, month)` 적용으로 중복 적재 방지.

### 2. `customer_fcst` (고객사 Forecast 계획량)
- **컬럼**: `item_code` (품목명), `year` (연도), `month` (월), `qty` (계획 수량)
- **제약**: `PRIMARY KEY(item_code, year, month)` 적용.

### 3. `submissions` (PSI 예측 최종 승인 제출 이력)
- **컬럼**: `id` (PK), `item_code`, `target_month`, `lme_price`, `exchange_rate`, `price_change_rate`, `operating_profit_rate`, `ai_recommendation`, `submitted_at`
- **목적**: LME 가격이나 환율 등의 원가 변수가 배제됨에 따라 현재는 `0.0` 상수로 마스킹하여 AI 최종 추천량과 함께 이력을 안전하게 로깅합니다.

### 4. `sync_meta` (엑셀 동기화 메타 데이터)
- **컬럼**: `key` (식별키, 예: `'last_mtime'`), `val` (엑셀 파일들의 수정시각 누적합)
