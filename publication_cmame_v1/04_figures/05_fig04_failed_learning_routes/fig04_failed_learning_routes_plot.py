#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

builder = Path(__file__).resolve().parents[1] / '00_style' / 'build_main_figures.py'
subprocess.run([sys.executable, str(builder), '--figure', 'fig04'], check=True)
