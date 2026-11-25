
import sys
from pathlib import Path

# Add the main project folder to Python's import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db import check_connection

ok, message = check_connection()
print(message)

raise SystemExit(0 if ok else 1)
