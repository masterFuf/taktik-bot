__version__ = '1.1.3'
__author__ = 'masterFuf'

import logging
import os

os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/taktik.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('taktik')
