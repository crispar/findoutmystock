import bs4
from urllib.request import Request, urlopen
import urllib.error
import datetime as dt
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
        url = f"https://comp.wisereport.co.kr/company/c1010001.aspx?cmp_cd={stock_code}"
        soup = self._make_request(url)
        if not soup: return None
        try:
            # 헤더 텍스트를 기반으로 데이터를 찾아 안정성을 높임
            header = soup.find('th', string=re.compile(r'발행주식수/유동주식비율'))
            if not header:
                print(f"--> (정보) '발행주식수' 헤더를 찾지 못했습니다 {stock_code}")
                return None

            data_cell = header.find_next_sibling('td')
            if not data_cell:
                print(f"--> (정보) 데이터 셀을 찾지 못했습니다 {stock_code}")
                return None

            text_content = data_cell.get_text(strip=True)
            tmp_split = text_content.split('/')
            if len(tmp_split) < 2:
                print(f"--> (정보) 부가 정보 포맷 오류 {stock_code}: {text_content}")
                return None

            outstanding_shares_str = tmp_split[0].replace('주', '').replace(',', '').strip()
            floating_ratio_str = tmp_split[1].replace('%', '').strip()

            return {
                'outstanding_shares': int(outstanding_shares_str),
                'floating_ratio': float(floating_ratio_str)
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