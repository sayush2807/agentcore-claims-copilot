import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "legacy_api"))
sys.path.insert(0, str(ROOT / "app" / "agent"))
