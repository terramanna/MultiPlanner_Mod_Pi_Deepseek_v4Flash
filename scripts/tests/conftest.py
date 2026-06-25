"""Put scripts/ on sys.path so tests can `import check_file_size_policy`.

The tooling scripts are plain modules under scripts/, not an installed package,
so the suite imports them by adding their directory to the path here rather than
relying on the (deliberately empty) root package.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
