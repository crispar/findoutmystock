import logging
import sys

def setup_logger():
    """
    애플리케이션의 기본 로거를 설정합니다.
    - 레벨: INFO
    - 포맷: [시간] [로그레벨] 메시지
    - 핸들러: 콘솔 출력 (stdout)
    """
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        stream=sys.stdout,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def get_logger(name):
    """지정된 이름으로 로거 인스턴스를 가져옵니다."""
    return logging.getLogger(name)