__version__ = '1.9.9'
__author__ = 'masterFuf'

import logging

# The journal lives in the data folder (AppData, or the folder of TAKTIK_DB_PATH), looked up
# when its first line is written rather than at this import.
from taktik.core.shared.app_paths import DataFolderLogFile

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        DataFolderLogFile('taktik.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('taktik')
