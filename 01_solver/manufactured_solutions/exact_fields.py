"""Uniform access to the two Stage 01F exact field families."""

from __future__ import annotations
from types import ModuleType
from manufactured_solutions import mms_a_translating_density_wave as mms_a,mms_b_deforming_vortex as mms_b


def solution_module(name:str)->ModuleType:
    normalized=name.upper().replace("-","_")
    if normalized in ("A","MMS_A"): return mms_a
    if normalized in ("B","MMS_B"): return mms_b
    raise ValueError(f"unknown manufactured solution {name}")
