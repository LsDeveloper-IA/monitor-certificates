"""Compatibilidade temporária para backends iniciados antes da mudança de pasta."""

import os
import runpy
from pathlib import Path


PASTA_AUTO_NC = Path(__file__).resolve().parent.parent
os.environ["GOOGLE_DRIVE_TOKEN"] = str(PASTA_AUTO_NC / "token.json")
os.environ.setdefault(
    "GOOGLE_DRIVE_CREDENTIALS",
    str(PASTA_AUTO_NC / "credentials.json"),
)

runpy.run_path(str(PASTA_AUTO_NC / "main.py"), run_name="__main__")
