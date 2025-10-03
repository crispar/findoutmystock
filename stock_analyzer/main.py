import argparse
import datetime as dt
import pandas as pd
from scraper.naver_finance_scraper import NaverFinanceScraper
from analysis.stock_analyzer import StockAnalyzer

def main():
    """
    메인 실행 함수. CLI 인자를 처리하고, 스크래핑과 분석을 조율합니다.
    """
    parser = argparse.ArgumentParser(description="Naver Finance 주식 분석기. 52주 최저가에 근접한 종목을 찾습니다.")
    parser.add_argument('--market', type=str, default='KOSPI', choices=['KOSPI', 'KOSDAQ'], help="분석할 시장 (KOSPI 또는 KOSDAQ)")
    parser.add_argument('--num-stocks', type=int, default=10, help="분석할 시가총액 상위 종목의 수 (기본값: 10)")

    args = parser.parse_args()

    # --- 실행 ---
    scraper = NaverFinanceScraper(market_type=args.market)

    # 1. 시가총액 상위 종목 가져오기
    top_stocks = scraper.get_top_stocks(num_stocks=args.num_stocks)
    if not top_stocks:
        print("치명적 오류: 시가총액 상위 종목을 가져오지 못했습니다.")
        exit()

    stock_codes = list(top_stocks.values())

    # 2. 상세 정보 및 과거 데이터 가져오기
    today = dt.date.today()
    start_day = today - dt.timedelta(days=366)

    stock_details = scraper.get_stock_details_sequentially(stock_codes)
    historical_data = scraper.get_historical_data_concurrently(stock_codes, start_day, today)

    if not historical_data:
        print("치명적 오류: 과거 시세 데이터를 가져오지 못했습니다.")
        exit()

    # 3. 데이터 분석
    analyzer = StockAnalyzer(top_stocks, stock_details, historical_data)
    final_report = analyzer.run_analysis()

    # 4. 결과 출력
    if final_report is not None:
        print("\n--- 최종 분석 리포트 ---")
        pd.options.display.max_rows = None
        pd.options.display.width = 1000
        print(final_report)
    else:
        print("\n분석 후 표시할 결과가 없습니다.")

if __name__ == '__main__':
    main()