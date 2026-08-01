"""Reciprocal cutoff-crossing event detection from saved trajectory states."""

from __future__ import annotations
import numpy as np

def pair_ratios(positions:np.ndarray,support:float,domain_length:float=2.0)->np.ndarray:
    delta=positions[:,None,:]-positions[None,:,:];delta=np.remainder(delta+.5*domain_length,domain_length)-.5*domain_length
    return np.linalg.norm(delta,axis=-1)/support

def topology_events(times:np.ndarray,positions:np.ndarray,support:float)->list[dict[str,float|int|bool]]:
    events=[];count=positions.shape[1]
    ratios=[pair_ratios(value,support) for value in positions]
    for k in range(len(times)-1):
        before,after=ratios[k],ratios[k+1]
        for i in range(count):
            for j in range(i+1,count):
                inside_before=before[i,j]<1.;inside_after=after[i,j]<1.
                if inside_before!=inside_after:
                    denominator=after[i,j]-before[i,j];fraction=(1.-before[i,j])/denominator if denominator else .5
                    events.append({"particle_i":i,"particle_j":j,"time_before":float(times[k]),"time_after":float(times[k+1]),"estimated_event_time":float(times[k]+fraction*(times[k+1]-times[k])),"ratio_before":float(before[i,j]),"ratio_after":float(after[i,j]),"added":bool(inside_after),"reciprocal":True})
    return events
