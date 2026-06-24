import sqlite3
import os

def migrate():
    db_path = "sales_forecast.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 기존 테이블 삭제 후 재생성 (스키마 변경을 위해 깔끔하게 재빌드)
    cursor.execute("DROP TABLE IF EXISTS market_indicators")
    
    # 1. 테이블 생성 (coway_promo 컬럼 추가)
    cursor.execute("""
        CREATE TABLE market_indicators (
            year INTEGER,
            month INTEGER,
            pm25_dust REAL,
            exchange_rate REAL,
            coway_promo REAL,
            PRIMARY KEY(year, month)
        )
    """)
    
    # 2. 데이터 준비 (2023 ~ 2026년 월별 데이터)
    dust_profile = {
        1: 28.5, 2: 30.2, 3: 38.4, 4: 35.1, 5: 25.8, 6: 18.2,
        7: 12.5, 8: 11.4, 9: 15.6, 10: 20.1, 11: 24.3, 12: 27.8
    }
    
    # 코웨이 대형 프로모션 월: 4~5월(봄 페스타), 6~8월(여름 정수기 할인), 11~12월(연말 감사제)
    promo_months = [4, 5, 6, 7, 8, 11, 12]
    
    records = []
    for year in [2023, 2024, 2025, 2026]:
        if year == 2023:
            base_rate = 1305.0
        elif year == 2024:
            base_rate = 1360.0
        elif year == 2025:
            base_rate = 1395.0
        else: # 2026
            base_rate = 1370.0
            
        for month in range(1, 13):
            # 월별 환율에 소폭의 노이즈 추가
            rate_noise = (month * 3.5 - 20) if month <= 6 else (20 - month * 3.5)
            rate = base_rate + rate_noise
            
            # 미세먼지 농도
            dust_noise = (year % 3 - 1) * 2.0
            dust = max(5.0, dust_profile[month] + dust_noise)
            
            # 프로모션 플래그 설정 (1.0 or 0.0)
            promo = 1.0 if month in promo_months else 0.0
            
            records.append((year, month, round(dust, 1), round(rate, 1), promo))
            
    # 3. 데이터 적재
    cursor.executemany("""
        INSERT OR REPLACE INTO market_indicators (year, month, pm25_dust, exchange_rate, coway_promo)
        VALUES (?, ?, ?, ?, ?)
    """, records)
    
    conn.commit()
    
    # 4. 검증 출력
    cursor.execute("SELECT COUNT(*) FROM market_indicators")
    cnt = cursor.fetchone()[0]
    print(f"Successfully migrated {cnt} records into market_indicators table with 'coway_promo' column.")
    
    conn.close()

if __name__ == "__main__":
    migrate()
