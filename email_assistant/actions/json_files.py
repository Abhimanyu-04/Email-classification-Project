import json
import logging
import os

logger = logging.getLogger(__name__)

def read_json_list(path: str) -> list:
    """Reads a JSON array from *path*; returns [] if the file does not exist."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def write_json_list(path: str, items: list) -> None:
    """Writes *items* to *path* as a pretty-printed JSON array, creating directories."""
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
