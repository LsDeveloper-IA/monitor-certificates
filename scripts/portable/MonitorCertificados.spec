# -*- mode: python ; coding: utf-8 -*-
"""Gera o executavel unico do pacote portatil."""

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)


RAIZ = Path(SPECPATH).resolve().parents[1]
BACKEND = RAIZ / "certificados-monitor"
RECURSOS = RAIZ / "build" / "portable"

hiddenimports = []
for pacote in ("src", "config", "automation_engine"):
    hiddenimports += collect_submodules(pacote, filter=lambda nome: ".tests" not in nome)

for pacote in ("waitress", "googleapiclient", "google_auth_oauthlib", "google.auth", "google.oauth2"):
    hiddenimports += collect_submodules(pacote)

hiddenimports += [
    "flask_cors",
    "flask_sqlalchemy",
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "pyodbc",
    "openpyxl",
    "PIL",
    "PIL.Image",
    "docx",
    "cryptography",
    "schedule",
]

datas = [
    (str(RECURSOS / "web"), "web"),
    (str(RECURSOS / ".env.example"), "."),
]
datas += collect_data_files("reportlab")

a = Analysis(
    [str(RAIZ / "scripts" / "portable" / "entrypoint.py")],
    pathex=[str(RAIZ), str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pytest",
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "IPython",
        "notebook",
        "playwright",
        "automacoes",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MonitorCertificados",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
