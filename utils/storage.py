import json
import os
from datetime import datetime

def load_cache():
    if os.path.exists("cache.json"):
        with open("cache.json", "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open("cache.json", "w") as f:
        json.dump(cache, f, indent=4)