"""Where the core is, for the tests: the one place that knows how deep `tests/unit/` sits.

A test that reads a file of the core, puts a folder of scripts on `sys.path` or reads the captures of
another folder writes that path from `CORE` (`CORE / "scripts/audits"`,
`CORE / "tests/unit/social_media/tiktok/fixtures"`): it can move to the folder of the code it tests and
its paths stay true. What a test reads in its own folder stays written from its own file
(`Path(__file__).parent / "fixtures"`): it moves with the test.

Imported as `unit.paths` (the `tests` folder is on the path of every pytest run, as the package of
`tests/unit/conftest.py`). The path is the one pytest sees, a link left unresolved: the guards of
`conftest.py` compare module paths as text.
"""

import os
from pathlib import Path

CORE = Path(os.path.abspath(__file__)).parents[2]
