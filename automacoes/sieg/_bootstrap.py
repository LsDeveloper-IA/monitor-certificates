import sys
from pathlib import Path

RAIZ = str(Path(__file__).resolve().parents[1])
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
