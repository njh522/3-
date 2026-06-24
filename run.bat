@echo off
chcp 65001 > nul
title [코웨이 영업] 수요 예측 대시보드 실행
echo ===================================================
echo   [코웨이 영업] 데이터 기반 수요 예측 대시보드
echo ===================================================
echo.
echo Streamlit 대시보드 서버를 시작합니다...
echo 브라우저 창이 자동으로 열리지 않으면 http://localhost:8501 에 접속해 주세요.
echo.
python -m streamlit run app.py
pause
