# 설계서

## 1. 개요
이 문서는 Naver 금융에서 주식 데이터를 스크래핑하고 분석하는 시스템의 기술적인 설계에 대해 설명합니다. 이 시스템은 두 개의 Jupyter Notebook 파일(`examples-rename.ipynb`, `examples-rename-kosdaq.ipynb`)로 구성되어 있으며, 각각 KOSPI와 KOSDAQ 시장을 분석합니다.

## 2. 시스템 구성 요소

### 2.1. 주요 라이브러리
- **`bs4` (BeautifulSoup)**: HTML 파싱을 통해 웹 페이지에서 필요한 데이터를 추출하는 데 사용됩니다.
- **`urllib.request`**: 지정된 URL에 HTTP 요청을 보내 웹 페이지의 소스 코드를 가져오는 데 사용됩니다.
- **`pandas`**: 수집된 데이터를 구조화하고 분석하기 위한 핵심 라이브러리입니다. 데이터는 주로 DataFrame 형태로 관리됩니다.
- **`datetime`**: 날짜 및 시간 관련 데이터를 처리하는 데 사용됩니다.
- **`re` (정규 표현식)**: 텍스트에서 특정 패턴(예: 주식 코드)을 찾거나 문자열을 분리하는 데 사용됩니다.
- **`ssl`**: SSL/TLS 통신을 처리합니다. KOSPI 스크립트에서는 SSL 인증서 검증 오류를 우회하기 위해 `ssl._create_unverified_context()`가 사용됩니다.

### 2.2. 핵심 함수

- **`stock_info(stock_cd)`**:
    - **입력**: 주식 코드(예: '005930').
    - **기능**: Naver 금융의 기업 정보 페이지(`https://companyinfo.stock.naver.com`)에 접근하여 특정 종목의 발행 주식 수, 유동 주식 비율, 회사명을 스크래핑합니다.
    - **출력**: 전역 딕셔너리(`k50_outstanding`, `k50_floating`, `k50_name`)에 스크래핑한 정보를 저장합니다.

- **`top_rank_stocks(num, top_ranks, ...)`**:
    - **입력**: 가져올 종목 수(`num`), 결과를 저장할 딕셔너리(`top_ranks`).
    - **기능**: Naver 금융의 시가총액 페이지(`https://finance.naver.com/sise/sise_market_sum.nhn`)를 순회하며 시가총액 상위 종목의 이름과 코드를 수집합니다. ETF나 우선주 등 특정 종목을 필터링하는 로직이 포함되어 있습니다.
    - **URL 파라미터**: KOSDAQ 시장을 분석할 때는 URL에 `sosok=1` 파라미터가 추가됩니다.
    - **출력**: 회사명을 키로, 주식 코드를 값으로 하는 딕셔너리(`top_ranks`)를 반환합니다.

- **`historical_index_naver_domestic(index_cd, ...)`**:
    - **입력**: 주식 코드(`index_cd`), 조회 시작일, 조회 종료일.
    - **기능**: Naver 금융의 일별 시세 페이지(`https://finance.naver.com/item/sise_day.nhn`)에서 특정 종목의 지정된 기간 동안의 일별 시가, 고가, 저가, 종가 데이터를 수집합니다.
    - **출력**: 날짜를 키로, 가격 정보를 값으로 하는 딕셔너리(`historical_prices`)를 반환합니다.

### 2.3. 데이터 흐름 및 구조
1. **종목 선정**: `top_rank_stocks` 함수가 호출되어 시가총액 상위 N개 종목의 리스트(`top_ranks`)를 생성합니다.
2. **상세 정보 수집**: `top_ranks`의 각 종목 코드에 대해 `stock_info` 함수가 호출되어 발행 주식 수, 유동 주식 비율 등의 상세 정보를 수집합니다.
3. **과거 데이터 수집**: 각 종목 코드에 대해 `historical_index_naver_domestic` 함수가 호출되어 지난 1년간의 시세 데이터를 수집합니다.
4. **데이터프레임 생성**: 모든 종목의 과거 시세 데이터는 하나의 Pandas DataFrame(`k50_historical_prices`)으로 통합됩니다. 결측치는 `fillna` 메소드를 사용하여 이전 또는 다음 값으로 채워집니다.
5. **분석 및 계산**: 생성된 DataFrame을 기반으로 각 종목의 52주 최저가(`k50_min`), 최저가 기록일(`K50_min_date`), 현재가와의 갭(`K50_gap`), 갭 비율(`gap_percentage`) 등을 계산합니다.
6. **최종 리포트**: 계산된 모든 지표와 수집된 상세 정보가 `k50_info`라는 최종 DataFrame으로 결합됩니다. 이 DataFrame은 'Gap_Percentage' 열을 기준으로 정렬되어 사용자에게 표시됩니다.

## 3. 알려진 문제점 및 개선 사항

### 3.1. KOSDAQ 스크립트의 SSL 인증 오류
- `examples-rename-kosdaq.ipynb` 파일의 `stock_info` 및 `historical_index_naver_domestic` 함수 내에서 `urlopen`을 호출할 때 SSL 컨텍스트가 설정되지 않았습니다.
- 이로 인해 `[SSL: CERTIFICATE_VERIFY_FAILED]` 오류가 발생하여 스크립트 실행이 중단됩니다.
- **해결 방안**: KOSPI 스크립트(`examples-rename.ipynb`)에서와 같이 `urlopen` 호출 시 `context = ssl._create_unverified_context()` 인자를 추가해야 합니다.

### 3.2. 하드코딩된 로직
- 삼성전자 주식의 액면 분할(2018년 5월 4일)에 대한 처리 로직이 코드 내에 하드코딩되어 있습니다. 이는 다른 종목의 액면 분할이나 병합 이벤트에 대응할 수 없게 만듭니다.
- **개선 방안**: 액면 분할과 같은 이벤트를 동적으로 감지하고 처리할 수 있는 일반화된 로직을 구현하는 것이 좋습니다.

### 3.3. 코드 중복
- KOSPI와 KOSDAQ 스크립트는 URL의 `sosok` 파라미터를 제외하고 거의 동일한 코드를 포함하고 있습니다.
- **개선 방안**: 중복된 코드를 하나의 함수나 클래스로 통합하고, 시장(KOSPI/KOSDAQ)을 파라미터로 받아 처리하도록 리팩토링하여 유지보수성을 높일 수 있습니다.