"""Data ingestion pipeline for Echo Madrid."""

from pathlib import Path
import sys

_API_DIR = Path(__file__).resolve().parent.parent / "api"
_api_path = str(_API_DIR)
if _api_path not in sys.path:
    sys.path.insert(0, _api_path)
