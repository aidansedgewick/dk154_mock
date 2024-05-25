import logging
import sys

stream_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    handlers=[stream_handler],
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%y-%m-%d %H:%M:%S",
)

stream_handler = logging.StreamHandler(sys.stdout)
