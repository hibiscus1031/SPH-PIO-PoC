#!/usr/bin/env python3
"""Rebuild S08 from frozen public evidence."""
from pathlib import Path
import subprocess
import sys

builder = Path(__file__).resolve().parents[2] / "00_style" / "build_supplementary_figures.py"
raise SystemExit(subprocess.call([sys.executable, str(builder), "--figure", "S08"]))
