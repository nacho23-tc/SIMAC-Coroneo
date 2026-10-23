from pathlib import Path

TEMP_ROOT = Path(__file__).resolve().parents[2]/'tmp'
TEMP_ROOT.mkdir(exist_ok=True)
