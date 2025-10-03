import bs4
from urllib.request import Request, urlopen
import urllib.error
import datetime as dt
import pandas as pd
import ssl
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

class NaverFinanceScraper:
    """
    Naver Finance에서 주식 데이터를 스크래핑하는 객체.
    KOSPI 또는 KOSDAQ 시장을 지원하며, 동시성을 활용하여 데이터를 효율적으로 수집합니다.
    """
    BASE_URL = "https://finance.naver.com"
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}

    def __init__(self, market_type='KOSPI'):
        if market_type.upper() not in ['KOSPI', 'KOSDAQ']:
            raise ValueError("market_type은 'KOSPI' 또는 'KOSDAQ'이어야 합니다.")
        self.market_code = '0' if market_type.upper() == 'KOSPI' else '1'
        self.ssl_context = ssl._create_unverified_context()

    def _make_request(self, url):
        """지정된 URL에 HTTP 요청을 보내고 BeautifulSoup 객체를 반환합니다."""
        time.sleep(random.uniform(0.2, 0.8))  # Polite delay
        req = Request(url, headers=self.HEADERS)
        try:
            with urlopen(req, context=self.ssl_context, timeout=10) as response:
                encoding = 'euc-kr' if 'sise_market_sum' in url else 'utf-8'
                return bs4.BeautifulSoup(response.read().decode(encoding, 'replace'), 'lxml')
        except Exception as e:
            print(f"--> 요청 실패 {url}: {e}")
            return None

    def get_top_stocks(self, num_stocks=10):
        """시가총액 상위 종목 목록을 스크래핑합니다."""
        print(f"시가총액 상위 {num_stocks}개 종목을 가져옵니다...")
        top_ranks = {}
        page_n = 1
        last_page = 1 # Start with 1, will be updated

        while len(top_ranks) < num_stocks and page_n <= last_page:
            url = f"{self.BASE_URL}/sise/sise_market_sum.naver?sosok={self.market_code}&page={page_n}"
            soup = self._make_request(url)
            if not soup: break

            stock_table = soup.find('table', class_='type_2')
            if not stock_table: break

            for link in stock_table.find_all('a', class_='tltle'):
                name = link.text.strip()
                if not name or any(k in name for k in ['스팩', 'KODEX', 'TIGER', 'ARIRANG']): continue

                href = link.get('href')
                if href and 'code=' in href:
                    top_ranks[name] = href.split('code=')[1]
                if len(top_ranks) >= num_stocks: break

            if page_n == 1: # Get last page number only once
                pgRR = soup.find('td', class_='pgRR')
                last_page = int(re.search(r'page=(\d+)', pgRR.find('a')['href']).group(1)) if pgRR and pgRR.find('a') else page_n

            page_n += 1
        return top_ranks

    def get_stock_details_sequentially(self, stock_codes):
        """여러 종목의 상세 정보를 순차적으로 가져옵니다."""
        print("\n종목 상세 정보를 가져옵니다 (순차 처리)...")
        results = {}
        for code in stock_codes:
            info = self.get_stock_info(code)
            if info:
                results[code] = info
        return results

    def get_stock_info(self, stock_code):
        """단일 종목의 발행 주식 수, 유동 주식 비율 등 부가 정보를 가져옵니다."""
        url = f"https://companyinfo.stock.naver.com/company/c1010001.aspx?cmp_cd={stock_code}"
        soup = self._make_request(url)
        if not soup: return None
        try:
            # 이름 정보는 더 이상 여기서 가져오지 않음.
            tmp = soup.find(id='cTB11').find_all('tr')[6].td.text.replace('\r', '').replace('\n', '').replace('\t', '')
            tmp_split = re.split('/', tmp)
            if len(tmp_split) < 2: return None

            return {
                'outstanding_shares': int(tmp_split[0].replace(',', '').replace('주', '').strip()),
                'floating_ratio': float(tmp_split[1].replace('%', '').strip())
            }
        except Exception as e:
            print(f"--> (정보) 부가 정보 파싱 오류 {stock_code}: {e}")
            return None

    def get_historical_data_concurrently(self, stock_codes, start_date, end_date):
        """여러 종목의 과거 시세 데이터를 동시에 가져옵니다."""
        print("\n과거 시세 데이터를 가져옵니다 (동시 처리)...")
        results = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_code = {executor.submit(self.get_historical_prices, code, start_date, end_date): code for code in stock_codes}
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    results[code] = future.result()
                except Exception as e:
                    print(f"--> 과거 데이터 조회 중 오류 발생 {code}: {e}")
        return {k: v for k, v in results.items() if v}

    def get_historical_prices(self, stock_code, start_date, end_date):
        """단일 종목의 과거 시세 데이터를 스크래핑합니다."""
        historical_prices = {}
        page_n = 1
        while True:
            url = f"{self.BASE_URL}/item/sise_day.naver?code={stock_code}&page={page_n}"
            soup = self._make_request(url)
            if not soup: break

            dates = soup.find_all('span', class_='tah p10 gray03')
            prices_raw = soup.find_all('td', class_='num')
            if not dates: break

            for i, date_tag in enumerate(dates):
                date = dt.datetime.strptime(date_tag.text, '%Y.%m.%d').date()
                if date < start_date: return historical_prices
                if date > end_date: continue

                try:
                    price_data = {
                        '종가': float(prices_raw[i*5].text.strip().replace(',', '')),
                        '시가': float(prices_raw[i*5+2].text.strip().replace(',', '')),
                        '고가': float(prices_raw[i*5+3].text.strip().replace(',', '')),
                        '저가': float(prices_raw[i*5+4].text.strip().replace(',', ''))
                    }
                    historical_prices[date] = price_data
                except (ValueError, IndexError):
                    continue

            if soup.find('td', class_='pgRR') and soup.find('td', class_='pgRR').find('a')['href'].endswith(f'page={page_n}'):
                break # Last page
            page_n += 1
        return historical_prices

class StockAnalyzer:
    """수집된 주식 데이터를 분석하고 리포트를 생성하는 객체."""
    def __init__(self, top_stocks, stock_details, historical_data):
        self.top_stocks = top_stocks
        self.stock_details = stock_details
        self.historical_data = historical_data
        self.df = None

    def _prepare_dataframe(self):
        """데이터를 분석에 적합한 Pandas DataFrame으로 변환하고 정제합니다."""
        if not self.historical_data: return False

        all_data = []
        for code, prices in self.historical_data.items():
            for date, data in prices.items():
                all_data.append({'date': date, 'stock_code': code, **data})

        if not all_data: return False

        df = pd.DataFrame(all_data).set_index(['date', 'stock_code']).unstack()
        today = dt.date.today()
        start_day = today - dt.timedelta(days=366)
        df = df.reindex(pd.date_range(start=start_day, end=today, freq='D'))
        df.ffill(inplace=True); df.bfill(inplace=True)
        self.df = df
        return True

    def run_analysis(self):
        """52주 최저가 및 관련 지표를 계산합니다."""
        if not self._prepare_dataframe():
            print("분석할 데이터가 없습니다.")
            return None

        results = []
        stock_codes = self.df.columns.get_level_values(1).unique()

        # 안정적인 이름 조회를 위해 code:name 역방향 맵 생성
        code_to_name = {v: k for k, v in self.top_stocks.items()}

        for code in stock_codes:
            stock_df = self.df.xs(code, level=1, axis=1).dropna()
            if stock_df.empty or '저가' not in stock_df or len(stock_df) < 2: continue

            min_52_date = stock_df['저가'].idxmin()
            min_52_price = stock_df['저가'].min()
            yesterday_price = stock_df.iloc[-2]['종가']

            gap = yesterday_price - min_52_price
            gap_percentage = ((yesterday_price / min_52_price) - 1) * 100 if min_52_price != 0 else 0

            # 시가총액 목록에서 가져온 이름을 기본으로 사용
            stock_name = code_to_name.get(code, "이름 조회 실패")
            rank = list(self.top_stocks.values()).index(code) + 1 if code in self.top_stocks.values() else 'N/A'

            results.append({
                'Name': stock_name, 'Rank': rank,
                'Min_52_Date': min_52_date.strftime('%Y-%m-%d'),
                'Min_52_Price': min_52_price, 'Yesterday_Price': yesterday_price,
                'Gap_Percentage': f"{gap_percentage:.1f}%"
            })

        if not results: return None
        return pd.DataFrame(results).sort_values(by="Gap_Percentage", key=lambda col: col.str.replace('%', '').astype(float))

import argparse

if __name__ == '__main__':
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

    # 2. 상세 정보 및 과거 데이터 병렬로 가져오기
    today = dt.date.today()
    start_day = today - dt.timedelta(days=366)

    stock_details = scraper.get_stock_details_sequentially(stock_codes) # 순차 처리로 변경
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