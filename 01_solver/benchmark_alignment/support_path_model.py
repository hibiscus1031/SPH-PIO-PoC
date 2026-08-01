"""Descriptive, guarded two-term support-path fit for Stage 01E."""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares


def fit_two_term(H: np.ndarray, dx_over_H: np.ndarray, error: np.ndarray) -> dict[str, object]:
    H=np.asarray(H,float); qx=np.asarray(dx_over_H,float); error=np.asarray(error,float)
    if len(error)<6 or np.any(error<=0) or not np.all(np.isfinite(error)):
        return {"status":"two-term asymptotic fit not identifiable", "reason":"insufficient positive finite observations"}
    def residual(theta: np.ndarray) -> np.ndarray:
        ch,cq,p,q=theta
        return (np.exp(ch)*H**p + np.exp(cq)*qx**q-error)/error
    fit=least_squares(residual, np.array([np.log(np.median(error)/2),np.log(np.median(error)/2),1.0,1.0]), bounds=([-30,-30,0,0],[30,30,8,8]))
    rank=int(np.linalg.matrix_rank(fit.jac))
    status="IDENTIFIABLE_DESCRIPTIVE_ONLY" if fit.success and rank==4 and fit.x[2]>0 and fit.x[3]>0 else "two-term asymptotic fit not identifiable"
    return {"status":status,"C_H":float(np.exp(fit.x[0])),"C_Q":float(np.exp(fit.x[1])),"p":float(fit.x[2]),"q":float(fit.x[3]),"jacobian_rank":rank,"relative_residual_rms":float(np.sqrt(np.mean(fit.fun**2)))}


def bootstrap_two_term(H: np.ndarray, dx_over_H: np.ndarray, error: np.ndarray, *, resamples: int, seed: int, stable_relative_ci_width_maximum: float) -> dict[str, object]:
    base=fit_two_term(H,dx_over_H,error)
    if base["status"]!="IDENTIFIABLE_DESCRIPTIVE_ONLY": return base
    rng=np.random.default_rng(seed); values=[]; count=len(error)
    for _ in range(resamples):
        selected=rng.integers(0,count,count); fitted=fit_two_term(H[selected],dx_over_H[selected],error[selected])
        if fitted["status"]=="IDENTIFIABLE_DESCRIPTIVE_ONLY": values.append([fitted[k] for k in ("C_H","C_Q","p","q")])
    if len(values)<0.9*resamples:
        return {**base,"status":"two-term asymptotic fit not identifiable","bootstrap_success_fraction":len(values)/resamples,"reason":"bootstrap rank or positivity instability"}
    array=np.asarray(values); intervals={}
    stable=True
    for i,key in enumerate(("C_H","C_Q","p","q")):
        low,high=np.percentile(array[:,i],[2.5,97.5]); intervals[f"{key}_bootstrap_95_low"]=float(low); intervals[f"{key}_bootstrap_95_high"]=float(high)
        stable=stable and (high-low)/max(abs(float(base[key])),1e-12)<=stable_relative_ci_width_maximum
    return {**base,**intervals,"bootstrap_success_fraction":len(values)/resamples,"status":base["status"] if stable else "two-term asymptotic fit not identifiable","reason":"stable bootstrap" if stable else "bootstrap interval too wide"}
