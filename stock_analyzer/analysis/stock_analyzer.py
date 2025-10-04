import pandas as pd
import datetime as dt
import logging

logger = logging.getLogger(__name__)

class StockAnalyzer:
    """수집된 주식 데이터를 분석하고 리포트를 생성하는 객체."""
    def __init__(self, top_stocks, stock_details, historical_data):
        self.top_stocks = top_stocks
        self.stock_details = stock_details
        self.historical_data = historical_data
        self.df = None

    def _prepare_dataframe(self):
        """데이터를 분석에 적합한 Pandas DataFrame으로 변환하고 정제합니다."""
        if not self.historical_data:
            logger.error("Historical data is empty. Cannot prepare DataFrame.")
            return False

        all_data = []
        for code, prices in self.historical_data.items():
            for date, data in prices.items():
                all_data.append({'date': date, 'stock_code': code, **data})

        if not all_data:
            logger.error("No data to process into DataFrame.")
            return False

        df = pd.DataFrame(all_data).set_index(['date', 'stock_code']).unstack()
        today = dt.date.today()
        start_day = today - dt.timedelta(days=366)
        df = df.reindex(pd.date_range(start=start_day, end=today, freq='D'))
        df.ffill(inplace=True); df.bfill(inplace=True)
        self.df = df
        return True

    def run_analysis(self):
        """52주 최저가 및 관련 지표를 계산합니다."""
        logger.info("Starting stock analysis...")
        if not self._prepare_dataframe():
            logger.error("DataFrame preparation failed. Aborting analysis.")
            return None

        results = []
        stock_codes = self.df.columns.get_level_values(1).unique()

        code_to_name = {v: k for k, v in self.top_stocks.items()}

        for code in stock_codes:
            stock_df = self.df.xs(code, level=1, axis=1).dropna()
            if stock_df.empty or '저가' not in stock_df or len(stock_df) < 2:
                logger.warning(f"Skipping analysis for {code} due to insufficient data.")
                continue

            min_52_date = stock_df['저가'].idxmin()
            min_52_price = stock_df['저가'].min()
            yesterday_price = stock_df.iloc[-2]['종가']

            gap = yesterday_price - min_52_price
            gap_percentage = ((yesterday_price / min_52_price) - 1) * 100 if min_52_price != 0 else 0

            stock_name = code_to_name.get(code, "이름 조회 실패")
            rank = list(self.top_stocks.values()).index(code) + 1 if code in self.top_stocks.values() else 'N/A'

            results.append({
                'Name': stock_name, 'Rank': rank,
                'Min_52_Date': min_52_date.strftime('%Y-%m-%d'),
                'Min_52_Price': min_52_price, 'Yesterday_Price': yesterday_price,
                'Gap_Percentage': f"{gap_percentage:.1f}%"
            })

        if not results:
            logger.warning("No results to display after analysis.")
            return None

        logger.info("Stock analysis complete.")
        return pd.DataFrame(results).sort_values(by="Gap_Percentage", key=lambda col: col.str.replace('%', '').astype(float))