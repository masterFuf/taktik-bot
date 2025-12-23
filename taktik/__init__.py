__version__ = '1.2.1'
__author__ = 'masterFuf'

import logging
import os

# Use AppData folder for logs to avoid permission issues
_app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
_logs_dir = os.path.join(_app_data, 'taktik-desktop', 'logs')
os.makedirs(_logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(_logs_dir, 'taktik.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('taktik')
