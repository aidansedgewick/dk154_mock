import logging
import sys
from pathlib import Path

stream_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    handlers=[stream_handler],
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%y-%m-%d %H:%M:%S",
)

stream_handler = logging.StreamHandler(sys.stdout)

base_path = Path(__file__).parent
