"""Печатает версию приложения из nivalis/config.py (для скриптов сборки)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from nivalis.config import APP_VERSION  # noqa: E402

print(APP_VERSION)
