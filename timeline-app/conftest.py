"""timeline-app を sys.path に追加して絶対インポートを有効にする。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
