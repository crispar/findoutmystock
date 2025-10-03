#-*-coding:utf-8
import bs4
from urllib.request import Request, urlopen
import urllib.error
import datetime as dt
import pandas as pd
import collections
import ssl
import re
import time
import random

# --- Global Dictionaries & Headers ---
k50_outstanding = {}
k50_floating = {}
k50_name = {}
historical_prices_global = {}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}

def make_request(url):
    """Makes a request with a browser User-Agent and returns a BeautifulSoup object."""
    time.sleep(random.uniform(0.5, 1.5)) # Polite delay
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, context=ssl._create_unverified_context(), timeout=10) as response:
            return bs4.BeautifulSoup(response.read(), 'lxml')
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"--> Warning: Request failed for {url}. Error: {e}")
        return None

def stock_info(stock_cd):
    """Fetches basic stock information."""
    url_float = f'https://companyinfo.stock.naver.com/company/c1010001.aspx?cmp_cd={str(stock_cd)}'
    soup = make_request(url_float)
    if not soup:
        k50_name.setdefault(stock_cd, f"Failed info for {stock_cd}")
        return

    try:
        name_element = soup.find(id='pArea')
        k50_name[stock_cd] = name_element.find('span').text if name_element else f"Name not found for {stock_cd}"

        tmp = soup.find(id='cTB11').find_all('tr')[6].td.text
        tmp = tmp.replace('\r', '').replace('\n', '').replace('\t', '')
        tmp_split = re.split('/', tmp)

        if len(tmp_split) < 2:
            print(f"--> Warning: Unexpected format for stock info {stock_cd}: {tmp}")
            return

        k50_outstanding[stock_cd] = int(tmp_split[0].replace(',', '').replace('주', '').replace(' ', ''))
        k50_floating[stock_cd] = float(tmp_split[1].replace(' ', '').replace('%', ''))

    except (IndexError, AttributeError) as e:
        print(f"--> Warning: Could not parse info for {stock_cd}. Error: {e}")

def top_rank_stocks(num, top_ranks, page_n=1, last_page=0):
    """Recursively scrapes top-ranked stocks."""
    url_float = f'https://finance.naver.com/sise/sise_market_sum.naver?page={str(page_n)}'
    soup = make_request(url_float)
    if not soup: return top_ranks

    stock_table = soup.find('table', class_='type_2')
    if not stock_table: return top_ranks

    for stock_link in stock_table.find_all('a', class_='tltle'):
        stock_name_text = stock_link.text.strip()
        if not stock_name_text or any(k in stock_name_text for k in ['HANARO', 'KINDEX', 'ARIRANG', 'KODEX', 'TIGER', 'KBSTAR', 'SOL']):
            continue

        href = stock_link.get('href')
        if href and 'code=' in href:
            top_ranks[stock_name_text] = href.split('code=')[1]
        if len(top_ranks) >= num: return top_ranks

    if last_page == 0:
        pgRR = soup.find('td', class_='pgRR')
        last_page = int(re.search(r'page=(\d+)', pgRR.find('a')['href']).group(1)) if pgRR and pgRR.find('a') else page_n

    if page_n < last_page:
        top_rank_stocks(num, top_ranks, page_n + 1, last_page)
    return top_ranks

def date_time(d_str):
    """Converts string to date object."""
    yyyy, mm, dd = map(int, str(d_str).replace('-', '.').split('.')[:3])
    return dt.date(yyyy, mm, dd)

def historical_index_naver_domestic(index_cd, start_date, end_date, page_n=1, last_page=0):
    """Recursively scrapes daily historical price data."""
    global historical_prices_global
    if page_n == 1: historical_prices_global = {}

    naver_index_url = f'https://finance.naver.com/item/sise_day.naver?code={index_cd}&page={page_n}'
    soup = make_request(naver_index_url)
    if not soup: return historical_prices_global

    dates = soup.find_all('span', class_='tah p10 gray03')
    prices_raw = soup.find_all('td', class_='num')
    prices = [p.text.strip().replace(',', '') for p in prices_raw]

    if not dates: return historical_prices_global

    for n, date_tag in enumerate(dates):
        try:
            this_date = date_time(date_tag.text)
            if not (date_time(start_date) <= this_date <= date_time(end_date)): continue
            if (n * 5 + 4) < len(prices):
                price_data = {
                    '종가': float(prices[n*5]), '시가': float(prices[n*5 + 2]),
                    '고가': float(prices[n*5 + 3]), '저가': float(prices[n*5 + 4])}
                for key in ['시가', '고가', '저가']:
                    if price_data[key] == 0: price_data[key] = price_data['종가']
                historical_prices_global[this_date] = price_data
        except (ValueError, IndexError):
            continue

    if last_page == 0:
        pgRR = soup.find('td', class_='pgRR')
        last_page = int(re.search(r'page=(\d+)', pgRR.find('a')['href']).group(1)) if pgRR and pgRR.find('a') else page_n

    if page_n < last_page and dates:
        historical_index_naver_domestic(index_cd, start_date, end_date, page_n + 1, last_page)

    return historical_prices_global

# --- Main Execution ---
print("Fetching top 3 KOSPI stocks for verification...")
top_ranks = top_rank_stocks(3, collections.OrderedDict())
if not top_ranks:
    print("Fatal: Failed to fetch top rank stocks. Exiting.")
    exit()

print(f"Found stocks: {list(top_ranks.keys())}")
k50_component = list(top_ranks.values())

print("\nFetching stock info...")
for stock_cd in k50_component: stock_info(stock_cd)

print("\nFetching historical prices...")
k50_historical_prices = {}
today = dt.date.today()
start_day = today - dt.timedelta(days=366)
start_date_str = start_day.strftime('%Y-%m-%d')
end_date_str = today.strftime('%Y-%m-%d')

for stock_cd in k50_component:
    print(f" -> Fetching for {k50_name.get(stock_cd, stock_cd)} ({stock_cd})")
    prices = historical_index_naver_domestic(stock_cd, start_date_str, end_date_str)
    if prices: k50_historical_prices[stock_cd] = prices

if not k50_historical_prices:
    print("\nFatal: Could not retrieve any historical data. Exiting.")
    exit()

# --- Data Processing and Analysis ---
all_data = [{'date': date, 'stock_code': code, **data} for code, prices in k50_historical_prices.items() for date, data in prices.items()]
if not all_data:
    print("\nFatal: No valid data to process. Exiting.")
    exit()

df = pd.DataFrame(all_data).set_index(['date', 'stock_code']).unstack()
df = df.reindex(pd.date_range(start=start_day, end=today, freq='D'))
df.ffill(inplace=True); df.bfill(inplace=True)

results = []
for stock_code in df.columns.get_level_values(1).unique():
    stock_df = df.xs(stock_code, level=1, axis=1).dropna()
    if stock_df.empty or '저가' not in stock_df or len(stock_df) < 2: continue

    min_52_date = stock_df['저가'].idxmin()
    min_52_price = stock_df['저가'].min()
    yesterday_price = stock_df.iloc[-2]['종가']
    today_price = stock_df.iloc[-1]['종가']
    gap = yesterday_price - min_52_price
    gap_percentage = ((yesterday_price / min_52_price) - 1) * 100 if min_52_price != 0 else 0

    results.append({
        'Name': k50_name.get(stock_code, "N/A"),
        'Min_52_Date': min_52_date.strftime('%Y-%m-%d'),
        'Min_52': min_52_price, 'Yesterday_price': yesterday_price, 'Gap': gap,
        'Gap_Percentage': f"{gap_percentage:.1f}%", 'Today_price': today_price,
        'Volume_Rank': list(top_ranks.values()).index(stock_code) + 1 if stock_code in top_ranks.values() else 'N/A'})

if not results:
    print("\nFatal: No stocks to display after analysis. Exiting.")
    exit()

result_df = pd.DataFrame(results).sort_values(by="Gap_Percentage", key=lambda col: col.str.replace('%', '').astype(float))
print("\n--- Analysis Results ---")
print(result_df)