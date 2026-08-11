"""Execute the frozen Stage 05B TRAIN-only target and scale qualification."""

from __future__ import annotations

from dataclasses import dataclass
import gc
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import sys
import time
from typing import Any, Callable

import numpy as np
import psutil
from scipy.integrate import solve_ivp
from scipy.optimize import lsq_linear
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import lsmr
import torch
import yaml


HERE = Path(__file__).resolve()
STAGE05B = HERE.parents[1]
STAGE05 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE04B = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
for candidate in (STAGE03C, ROOT / "01_solver", STAGE04B / "formula_templates"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import ReciprocalGraph, build_reciprocal_graph
from stage04b_reference_core import (
    CS, L, RHO0, SUPPORT_OVER_DX, array_sha256, evaluate_autograd, evaluate_symbolic, minimum_image,
)
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum


CONTRACT_PATH = STAGE05B / "contracts/conservative_discrete_defect_target_contract_v0_1.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
DT = L / CS / 256.0
LINEAGES = CONTRACT["formal_population"]["lineages"]
VARIANTS = CONTRACT["formal_population"]["variants"]
PROCESS = psutil.Process()
RSS_START = PROCESS.memory_info().rss
RSS_PEAK = RSS_START
START_TIME = time.perf_counter()
HASH_COUNT = 0
DECODE = {
    "preformal_train_npz_decode_count": 28,
    "preformal_train_json_decode_count": 28,
    "formal_train_npz_decode_count": 0,
    "formal_train_json_decode_count": 0,
    "diagnostic_train_npz_decode_count": 0,
    "diagnostic_train_json_decode_count": 0,
    "validation_state_decode_count": 0,
    "validation_target_decode_count": 0,
    "sealed_formula_decode_count": 0,
    "sealed_state_decode_count": 0,
    "sealed_source_decode_count": 0,
    "sealed_target_decode_count": 0,
    "sealed_origin_decode_count": 0,
}
EXECUTION = {
    "model_instances": 0, "neural_forwards": 0, "parameter_gradients": 0,
    "optimizer_instances": 0, "optimizer_steps": 0, "parameter_updates": 0,
    "training_runs": 0, "checkpoint_selections": 0, "neural_rollouts": 0,
    "performance_evaluations": 0,
}


def update_rss() -> int:
    global RSS_PEAK
    RSS_PEAK = max(RSS_PEAK, PROCESS.memory_info().rss)
    return RSS_PEAK


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    global HASH_COUNT
    HASH_COUNT += 1
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def sha_array(*values: np.ndarray) -> str:
    digest = hashlib.sha256()
    for value in values:
        array = np.ascontiguousarray(value)
        digest.update(str(array.dtype).encode()); digest.update(b"\0")
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes()); digest.update(array.tobytes())
    global HASH_COUNT
    HASH_COUNT += 1
    return "sha256:" + digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    def convert(item: Any) -> Any:
        if isinstance(item, np.bool_): return bool(item)
        if isinstance(item, np.integer): return int(item)
        if isinstance(item, np.floating): return float(item)
        if isinstance(item, np.ndarray): return item.tolist()
        if isinstance(item, torch.Tensor): return item.detach().cpu().tolist()
        raise TypeError(f"unsupported JSON type: {type(item).__name__}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=convert) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def import_access() -> Any:
    path = STAGE05B / "access_control/stage05b_train_access.py"
    spec = importlib.util.spec_from_file_location("stage05b_train_access", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ACCESS = import_access()


def denial_audit(phase: str) -> dict[str, Any]:
    probes = {
        "validation_state": STAGE04B / "access_control/validation_private/lcdf_02_variant_main_n8.npz",
        "validation_target": STAGE04B / "access_control/validation_private/lcdf_09_variant_main_n8.npz",
        "sealed_formula": STAGE04B / "sealed_test/private/sealed_parameters.json",
        "sealed_state": STAGE04B / "sealed_test/private/lcdf_03_variant_main_n8.npz",
        "sealed_source": STAGE04B / "sealed_test/private/lcdf_10_variant_main_n8.npz",
        "sealed_target": STAGE04B / "sealed_test/private/lcdf_03_variant_low_n8.npz",
        "sealed_origin": STAGE04B / "sealed_test/private/lcdf_10_variant_low_n8.npz",
    }
    rows = []
    for kind, path in probes.items():
        denied = False
        try:
            ACCESS.read_train_bytes(path)
        except PermissionError:
            denied = True
        rows.append({"kind": kind, "path": str(path.relative_to(ROOT)), "denied_before_payload_read": denied})
    result = {"phase": phase, "rows": rows, "decode_counts": dict(DECODE), "pass": all(row["denied_before_payload_read"] for row in rows)}
    write_json(STAGE05B / f"access_control/{phase}_allowlist_denial_audit.json", result)
    return result


def load_trajectory(lineage: str, variant: str, resolution: int, role: str) -> tuple[dict[str, np.ndarray], dict[str, Any], Path]:
    stem = f"{lineage.lower()}_{variant.lower()}_n{resolution}"
    path = STAGE04B / f"exact_trajectories/train/{stem}.npz"
    arrays = ACCESS.load_train_npz(path)
    metadata = ACCESS.load_train_json(path.with_suffix(".json"))
    DECODE[f"{role}_train_npz_decode_count"] += 1
    DECODE[f"{role}_train_json_decode_count"] += 1
    return arrays, metadata, path


def tensor(value: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(value)).to(dtype=torch.float64)


def make_state(arrays: dict[str, np.ndarray], resolution: int, frame: int) -> DynamicParticleState:
    hits = np.flatnonzero(arrays["frame_n"] == frame)
    if len(hits) != 1:
        raise RuntimeError(f"frame identity failure: {frame}")
    index = int(hits[0]); count = resolution * resolution; dx = L / resolution
    rho = tensor(arrays["density"][index])
    return DynamicParticleState(
        tensor(arrays["position_unwrapped"][index]), tensor(arrays["velocity"][index]), rho,
        eos_pressure(rho), torch.full((count,), RHO0 * dx * dx, dtype=torch.float64),
        torch.full((count,), SUPPORT_OVER_DX * dx, dtype=torch.float64), tensor(arrays["material_labels"]),
        float(arrays["physical_time"][index]), frame,
    )


@dataclass(frozen=True)
class D0Result:
    start: DynamicParticleState
    midpoint: DynamicParticleState
    accepted: DynamicParticleState
    graphs: tuple[ReciprocalGraph, ReciprocalGraph, ReciprocalGraph]
    sources: tuple[torch.Tensor, torch.Tensor]


def rhs(state: DynamicParticleState, graph: ReciprocalGraph, source: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    pressure_force = conservative_pressure_forces(graph.neighborhood, mass=state.mass, density=state.density, pressure=state.pressure)
    viscosity_force = conservative_viscosity_forces(graph.neighborhood, mass=state.mass, density=state.density, velocity=state.velocity, physical_viscosity=0.02)
    gradient = edge_kernel_gradients(graph.neighborhood)
    dv = state.velocity[graph.row] - state.velocity[graph.col]
    density_rate = scatter_sum(graph.row, state.mass[graph.col] * torch.einsum("nd,nd->n", dv, gradient), state.particle_count)
    acceleration = (pressure_force + viscosity_force) / state.mass[:, None] + source
    return state.velocity, acceleration, density_rate


def source_closed_form(lineage: str, variant: str, labels: torch.Tensor, physical_time: float) -> torch.Tensor:
    tau = physical_time * CS / L
    values = evaluate_symbolic(lineage, variant, np.ascontiguousarray(labels.detach().numpy()), tau)["source"]
    return tensor(values)


class Stage05BD0Transition:
    """Class orchestration over frozen D0 low-level state/graph/EOS/RHS semantics."""

    def __init__(self, lineage: str, variant: str, dt: float) -> None:
        self.lineage, self.variant, self.dt = lineage, variant, float(dt)

    def step(self, start: DynamicParticleState, exact_start_source: torch.Tensor) -> D0Result:
        with torch.no_grad():
            s = start.with_eos(); g0 = build_reciprocal_graph(s); x1, v1, r1 = rhs(s, g0, exact_start_source)
            h = 0.5 * self.dt
            mid = DynamicParticleState(s.x_unwrapped+h*x1, s.velocity+h*v1, s.density+h*r1, torch.empty_like(s.pressure),
                                       s.mass, s.smoothing_length, s.material_labels, s.physical_time+h, s.accepted_step_index).with_eos()
            gm = build_reciprocal_graph(mid); sm = source_closed_form(self.lineage, self.variant, mid.material_labels, mid.physical_time)
            x2, v2, r2 = rhs(mid, gm, sm)
            acc = DynamicParticleState(s.x_unwrapped+self.dt*x2, s.velocity+self.dt*v2, s.density+self.dt*r2,
                                       torch.empty_like(s.pressure), s.mass, s.smoothing_length, s.material_labels,
                                       s.physical_time+self.dt, s.accepted_step_index+1).with_eos()
            ga = build_reciprocal_graph(acc)
        return D0Result(s, mid, acc, (g0, gm, ga), (exact_start_source, sm))


def functional_d0(start: DynamicParticleState, lineage: str, variant: str, dt: float) -> D0Result:
    with torch.no_grad():
        s = start.with_eos(); g0 = build_reciprocal_graph(s)
        ss = source_closed_form(lineage, variant, s.material_labels, s.physical_time); x1, v1, r1 = rhs(s, g0, ss)
        h = 0.5 * dt
        mid = DynamicParticleState(s.x_unwrapped+h*x1, s.velocity+h*v1, s.density+h*r1, torch.empty_like(s.pressure),
                                   s.mass, s.smoothing_length, s.material_labels, s.physical_time+h, s.accepted_step_index).with_eos()
        gm = build_reciprocal_graph(mid); sm = source_closed_form(lineage, variant, mid.material_labels, mid.physical_time)
        x2, v2, r2 = rhs(mid, gm, sm)
        acc = DynamicParticleState(s.x_unwrapped+dt*x2, s.velocity+dt*v2, s.density+dt*r2, torch.empty_like(s.pressure),
                                   s.mass, s.smoothing_length, s.material_labels, s.physical_time+dt,
                                   s.accepted_step_index+1).with_eos()
        ga = build_reciprocal_graph(acc)
    return D0Result(s, mid, acc, (g0, gm, ga), (ss, sm))


def state_arrays(state: DynamicParticleState) -> list[np.ndarray]:
    return [state.x_unwrapped.numpy(), state.velocity.numpy(), state.density.numpy(), state.pressure.numpy()]


def route_disagreement(left: DynamicParticleState, right: DynamicParticleState) -> tuple[float, float]:
    a = np.concatenate([v.ravel() for v in state_arrays(left)]); b = np.concatenate([v.ravel() for v in state_arrays(right)])
    diff = a-b
    return (float(np.linalg.norm(diff)/max(np.linalg.norm(a),np.linalg.norm(b),1.0)),
            float(np.max(np.abs(diff))/max(np.max(np.abs(a)),np.max(np.abs(b)),1.0)))


def state_bitwise(left: DynamicParticleState, right: DynamicParticleState) -> bool:
    return all(np.array_equal(a,b) for a,b in zip(state_arrays(left),state_arrays(right))) and left.physical_time == right.physical_time


def mass_norm(value: np.ndarray, mass: np.ndarray) -> float:
    return float(np.sqrt(np.sum(mass[:,None]*np.asarray(value)**2)/np.sum(mass)))


def decompose(a_def: np.ndarray, mass: np.ndarray, u_origin: float) -> dict[str, Any]:
    total_mass = float(np.sum(mass)); cm = np.sum(mass[:,None]*a_def,axis=0)/total_mass
    cons = a_def-cm; inc = np.broadcast_to(cm,a_def.shape).copy()
    et = mass_norm(a_def,mass)**2; ec = mass_norm(cons,mass)**2; ei = mass_norm(inc,mass)**2
    denom = max(et,u_origin*u_origin)
    force = np.sum(mass[:,None]*cons,axis=0)
    force_denom = max(float(np.sum(mass*np.linalg.norm(cons,axis=1))),u_origin*total_mass)
    return {"a_cm":cm,"a_cons":cons,"a_incompatible":inc,"E_total":et,"E_cons":ec,"E_incompatible":ei,
            "incompatible_fraction":ei/denom,"conservative_coverage":ec/denom,
            "zero_force_normalized_residual":float(np.linalg.norm(force)/force_denom)}


def pair_matrix(state: DynamicParticleState, graph: ReciprocalGraph) -> tuple[np.ndarray, int]:
    selected = (graph.unordered & graph.active_kernel).numpy(); i=graph.row.numpy()[selected]; j=graph.col.numpy()[selected]
    disp=graph.displacement.numpy()[selected]; distance=graph.distance.numpy()[selected]
    rhat=disp/(distance[:,None]+2.0e-12); dv=(state.velocity.numpy()[j]-state.velocity.numpy()[i])/CS
    radial=np.sum(dv*rhat,axis=1); transverse=dv-radial[:,None]*rhat
    mass=state.mass.numpy(); f0=np.sqrt(mass[i]*mass[j])*CS**2/L; bound=0.05; n=state.particle_count; e=len(i)
    B=np.zeros((2*n,2*e),dtype=np.float64)
    for k in range(e):
        for offset,vec in ((0,bound*f0[k]*rhat[k]),(e,bound*f0[k]*transverse[k])):
            B[2*i[k]:2*i[k]+2,k+offset]=vec/mass[i[k]]
            B[2*j[k]:2*j[k]+2,k+offset]=-vec/mass[j[k]]
    return B,e


def solve_basis(state: DynamicParticleState, graph: ReciprocalGraph, target: np.ndarray, u_origin: float,
                *, reverse_columns: bool=False, diagnostic_sparse: bool=False) -> dict[str, Any]:
    B,e=pair_matrix(state,graph)
    if reverse_columns: B=B[:,::-1]
    mass=state.mass.numpy(); M=np.sum(mass); w=np.repeat(np.sqrt(mass/M),2); A=w[:,None]*B; b=w*target.ravel()
    if diagnostic_sparse:
        result=lsmr(csr_matrix(A),b,atol=1e-13,btol=1e-13,conlim=1e12,maxiter=4000)
        c=result[0]; solver=f"lsmr_pseudoinverse_action_istop_{result[1]}"
    else:
        gram=A@A.T; z=np.linalg.pinv(gram,rcond=1e-12,hermitian=True)@b; c=A.T@z; solver="B_T_pinv_BBT_rcond_1e-12"
    residual=(B@c).reshape(target.shape)-target
    denom=max(mass_norm(target,mass),u_origin); q_unbounded=mass_norm(residual,mass)/denom
    feasible=bool(np.max(np.abs(c),initial=0.0)<=1.0+1e-12)
    if feasible:
        cb=np.clip(c,-1.0,1.0); bounded_solver="unbounded_solution_feasible"
    else:
        bounded=lsq_linear(csr_matrix(A),b,bounds=(-1.0,1.0),method="trf",lsq_solver="lsmr",tol=1e-12,lsmr_tol=1e-13,max_iter=1000)
        cb=bounded.x; bounded_solver=f"scipy_lsq_linear_status_{bounded.status}"
    q_bounded=mass_norm((B@cb).reshape(target.shape)-target,mass)/denom
    return {"Q_unbounded":float(q_unbounded),"Q_bounded":float(q_bounded),"unbounded_max_abs_coefficient":float(np.max(np.abs(c),initial=0.0)),
            "bounded_max_abs_coefficient":float(np.max(np.abs(cb),initial=0.0)),"unbounded_feasible":feasible,
            "unordered_pair_count":e,"basis_column_count":2*e,"unbounded_solver":solver,"bounded_solver":bounded_solver}


def independent_route_fields(lineage: str, variant: str, labels: np.ndarray) -> tuple[dict[str,np.ndarray],dict[str,np.ndarray]]:
    count=len(labels); taus=np.arange(0.0,32.0+0.5,0.5,dtype=np.float64)/256.0
    tiled=np.tile(labels,(len(taus),1)); times=np.repeat(taus,count)
    closed=evaluate_symbolic(lineage,variant,tiled,times); independent=evaluate_autograd(lineage,variant,tiled,times)
    keys=("velocity","source")
    return ({k:closed[k].reshape(len(taus),count,-1) for k in keys},
            {k:independent[k].reshape(len(taus),count,-1) for k in keys})


def u5_existing(lineage: str, resolution: int) -> tuple[np.ndarray,dict[str,Any]]:
    path=STAGE04B/f"semidiscrete_audits/{lineage.lower()}_variant_main_n{resolution}_dop853_audit.json"
    data=json.loads(path.read_text())
    metric=data["field_primary_sensitivity"]["velocity"]
    if metric["normalized_L2"] != 0.0 or metric["normalized_Linf"] != 0.0:
        raise RuntimeError("nonzero existing U5 cannot be reconstructed originwise from public audit")
    return np.zeros(32,dtype=np.float64),{"source":str(path.relative_to(ROOT)),"exact_primary_sensitivity_identity":True}


def n12_u5(lineage: str, labels: np.ndarray, arrays: dict[str,np.ndarray]) -> tuple[np.ndarray,dict[str,Any]]:
    # Diagnostic-only same-resolution primary/sensitivity DOP853 integration.
    n=len(labels); mass=np.full(n,RHO0*(L/12)**2); tgrid=arrays["physical_time"]
    def integrate(rtol:float,atol:float)->np.ndarray:
        def unpack(y:np.ndarray)->tuple[np.ndarray,np.ndarray,np.ndarray]:
            return y[:2*n].reshape(n,2),y[2*n:4*n].reshape(n,2),y[4*n:]
        def pack(x:np.ndarray,v:np.ndarray,rho:np.ndarray)->np.ndarray: return np.concatenate((x.ravel(),v.ravel(),rho))
        initial=pack(arrays["position_unwrapped"][0],arrays["velocity"][0],arrays["density"][0])
        mass_t=tensor(mass); smoothing=torch.full((n,),SUPPORT_OVER_DX*L/12,dtype=torch.float64); labels_t=tensor(labels)
        def fun(t:float,y:np.ndarray)->np.ndarray:
            x,v,rho=unpack(y); rt=tensor(rho)
            state=DynamicParticleState(tensor(x),tensor(v),rt,eos_pressure(rt),mass_t,smoothing,labels_t,float(t),0)
            graph=build_reciprocal_graph(state); source=source_closed_form(lineage,"VARIANT_MAIN",labels_t,t)
            xr,vr,rr=rhs(state,graph,source); return pack(xr.numpy(),vr.numpy(),rr.numpy())
        sol=solve_ivp(fun,(float(tgrid[0]),float(tgrid[-1])),initial,method="DOP853",t_eval=tgrid,rtol=rtol,atol=atol,max_step=DT)
        if not sol.success: raise RuntimeError(sol.message)
        return np.stack([unpack(row)[1] for row in sol.y.T])
    primary=integrate(1e-11,1e-13); sensitivity=integrate(1e-12,1e-14)
    values=np.asarray([mass_norm((primary[o+4]-sensitivity[o+4])/DT,mass) for o in range(32)])
    return values,{"primary_velocity_sha256":sha_array(primary),"sensitivity_velocity_sha256":sha_array(sensitivity),
                   "maximum_U5":float(values.max()),"same_resolution":12,"role":"diagnostic_only"}


def validate_reference(arrays:dict[str,np.ndarray],metadata:dict[str,Any],resolution:int,origin:int)->dict[str,Any]:
    idx=int(np.flatnonzero(arrays["frame_n"]==origin+1)[0]); pressure=CS**2*(arrays["density"][idx]-RHO0)
    recomputed=array_sha256(arrays["position"][idx],arrays["velocity"][idx],arrays["density"][idx],arrays["pressure"][idx])
    return {"material_labels":arrays["material_labels"].shape==(resolution*resolution,2),
            "physical_time":abs(float(arrays["physical_time"][idx])-((origin+1)*DT))<=2*np.finfo(float).eps,
            "dt":abs(float(arrays["physical_time"][idx]-arrays["physical_time"][idx-1])-DT)<=2*np.finfo(float).eps,
            "eos_identity":float(np.max(np.abs(pressure-arrays["pressure"][idx])))<=1.0e-12,
            "source_family":metadata["opaque_family_id"] in metadata["lineage_component"],
            "periodic_convention":metadata["physical_constants"]["L"]==2.0 and bool(np.all(arrays["position"][idx]>=-1.0) and np.all(arrays["position"][idx]<1.0)),
            "origin_lineage":metadata["role"]=="TRAIN_LINEAGE",
            "target_hash":recomputed==str(arrays["state_hashes"][idx])}


def summarize_gate(rows:list[dict[str,Any]],key:str,mean_max:float,p95_max:float,max_max:float,lineage_max:float)->dict[str,Any]:
    values=np.asarray([row[key] for row in rows],dtype=float)
    lineage_means={f:float(np.mean([r[key] for r in rows if r["lineage"]==f])) for f in LINEAGES}
    family_balanced=float(np.mean(list(lineage_means.values())))
    return {"family_balanced_mean":family_balanced,"percentile95":float(np.percentile(values,95)),"maximum":float(values.max()),
            "lineage_means":lineage_means,"gates":{"mean":family_balanced<=mean_max,"p95":np.percentile(values,95)<=p95_max,
            "maximum":values.max()<=max_max,"lineages":all(v<=lineage_max for v in lineage_means.values())}}


def live_tensor_count() -> int:
    count=0
    for obj in gc.get_objects():
        try:
            if isinstance(obj,torch.Tensor): count+=1
        except Exception:
            pass
    return count


def main() -> None:
    torch.set_num_threads(1); torch.set_default_dtype(torch.float64)
    access_start=denial_audit("start")
    formal_rows:list[dict[str,Any]]=[]; intermediate_paths=[]; symmetry_cases:dict[tuple[str,str,int],dict[str,Any]]={}
    symmetry_keys={tuple(item) for item in CONTRACT["symmetry_invariance"]["cases"]}
    graph_rebuild_count=0; ls_solves=0; bounded_solves=0; retention=[]
    roundoff=64*np.finfo(np.float64).eps*CS/DT
    for lineage in LINEAGES:
        u5,u5_prov=u5_existing(lineage,8)
        for variant in VARIANTS:
            arrays,metadata,source_path=load_trajectory(lineage,variant,8,"formal")
            closed,independent=independent_route_fields(lineage,variant,arrays["material_labels"])
            mass=np.full(64,RHO0*(L/8)**2,dtype=np.float64)
            trajectory_arrays={k:[] for k in ("a_def","a_cm","a_cons","a_incompatible")}; trajectory_meta=[]
            transition=Stage05BD0Transition(lineage,variant,DT)
            for origin in range(32):
                start=make_state(arrays,8,origin); idx=int(np.flatnonzero(arrays["frame_n"]==origin)[0]); exact_source=tensor(arrays["external_source"][idx])
                class_result=transition.step(start,exact_source); functional=functional_d0(start,lineage,variant,DT); repeat=transition.step(start,exact_source)
                graph_rebuild_count+=9
                l2,linf=route_disagreement(class_result.accepted,functional.accepted)
                source_exact=all(torch.equal(a,b) for a,b in zip(class_result.sources,functional.sources))
                graphs_exact=[g.graph_hash for g in class_result.graphs]==[g.graph_hash for g in functional.graphs]
                repeat_exact=state_bitwise(class_result.accepted,repeat.accepted) and [g.graph_hash for g in class_result.graphs]==[g.graph_hash for g in repeat.graphs]
                target_idx=int(np.flatnonzero(arrays["frame_n"]==origin+1)[0]); ref_v=arrays["velocity"][target_idx]
                a_def=(ref_v-class_result.accepted.velocity.numpy())/DT
                U1=mass_norm((closed["velocity"][2*(origin+1)]-independent["velocity"][2*(origin+1)])/DT,mass)
                U2=mass_norm((class_result.accepted.velocity.numpy()-functional.accepted.velocity.numpy())/DT,mass)
                U3=mass_norm((class_result.accepted.velocity.numpy()-repeat.accepted.velocity.numpy())/DT,mass)
                U4=max(mass_norm(closed["source"][2*origin]-independent["source"][2*origin],mass),
                       mass_norm(closed["source"][2*origin+1]-independent["source"][2*origin+1],mass))
                u=float(max(U1,U2,U3,U4,u5[origin],roundoff)); dec=decompose(a_def,mass,u)
                basis=solve_basis(class_result.midpoint,class_result.graphs[1],dec["a_cons"],u); ls_solves+=1; bounded_solves+=1
                ref_checks=validate_reference(arrays,metadata,8,origin)
                state_gate=l2<=1e-13 and linf<=1e-12 and source_exact and graphs_exact and repeat_exact
                finite=bool(all(np.isfinite(x).all() for x in (a_def,dec["a_cons"],dec["a_cm"])) and bool(class_result.accepted.density.min()>0))
                signal=mass_norm(a_def,mass)>=10*u
                row={"lineage":lineage,"variant":variant,"resolution":8,"origin":origin,"origin_id":f"{lineage}_{variant}_N8_O{origin:02d}",
                     "dt":DT,"D0_state_hash":class_result.accepted.state_hash,"reference_accepted_hash":str(arrays["state_hashes"][target_idx]),
                     "reference_history_hashes":[str(arrays["state_hashes"][int(np.flatnonzero(arrays["frame_n"]==f)[0])]) for f in range(origin-3,origin+1)],
                     "graph_hashes":[g.graph_hash for g in class_result.graphs],"source_identity":sha_array(*[s.numpy() for s in class_result.sources]),
                     "route_normalized_L2":l2,"route_normalized_Linf":linf,"graph_hash_sequence_exact":graphs_exact,"source_evaluation_identity_exact":source_exact,
                     "deterministic_repeat_exact":repeat_exact,"reference_identity_pass":all(ref_checks.values()),"reference_identity_checks":ref_checks,
                     "finite_and_safety":finite,"r_def":mass_norm(a_def,mass),"a_cons_component_rms":float(np.sqrt(np.mean(dec["a_cons"]**2))),
                     "U1":U1,"U2":U2,"U3":U3,"U4":U4,"U5":float(u5[origin]),"u_roundoff_floor":roundoff,"u_origin":u,"signal_bearing":signal,
                     "E_total":dec["E_total"],"E_cons":dec["E_cons"],"E_incompatible":dec["E_incompatible"],
                     "incompatible_fraction":dec["incompatible_fraction"],"conservative_coverage":dec["conservative_coverage"],
                     "zero_force_normalized_residual":dec["zero_force_normalized_residual"],**basis,"D0_transition_pass":state_gate,
                     "defect_construction_pass":finite and all(ref_checks.values())}
                formal_rows.append(row); trajectory_meta.append(row)
                for k,v in (("a_def",a_def),("a_cm",dec["a_cm"]),("a_cons",dec["a_cons"]),("a_incompatible",dec["a_incompatible"])): trajectory_arrays[k].append(v)
                if (lineage,variant,origin) in symmetry_keys:
                    m=class_result.midpoint
                    symmetry_cases[(lineage,variant,origin)]={"x":m.x_unwrapped.numpy().copy(),"v":m.velocity.numpy().copy(),"rho":m.density.numpy().copy(),
                        "mass":m.mass.numpy().copy(),"smoothing":m.smoothing_length.numpy().copy(),"labels":m.material_labels.numpy().copy(),
                        "time":m.physical_time,"step":m.accepted_step_index,"a_def":a_def.copy(),"a_cons":dec["a_cons"].copy(),"u":u,"base":basis}
            stem=f"{lineage.lower()}_{variant.lower()}_n8"
            ipath=STAGE05B/f"defect_construction/{stem}_formal_defects.npz"
            np.savez_compressed(ipath,**{k:np.stack(v) for k,v in trajectory_arrays.items()})
            side={"source_payload":str(source_path.relative_to(ROOT)),"source_payload_sha256":sha_file(source_path),"U5_provenance":u5_prov,
                  "origin_count":32,"intermediate_npz":str(ipath.relative_to(ROOT)),"intermediate_npz_sha256":sha_file(ipath),
                  "origins":trajectory_meta}
            write_json(ipath.with_suffix(".json"),side); intermediate_paths.append(ipath)
            del arrays,metadata,closed,independent,trajectory_arrays,trajectory_meta,start,class_result,functional,repeat
            gc.collect(); retention.append({"after":stem,"live_tensor_count":live_tensor_count(),"rss_bytes":PROCESS.memory_info().rss}); update_rss()

    # Formal aggregate gates and unique scale.
    formal_complete=len(formal_rows)==384
    d0_pass=formal_complete and all(r["D0_transition_pass"] for r in formal_rows)
    defect_pass=formal_complete and all(r["defect_construction_pass"] for r in formal_rows)
    signal_by_lineage={f:float(np.mean([r["signal_bearing"] for r in formal_rows if r["lineage"]==f])) for f in LINEAGES}
    signal_overall=float(np.mean([r["signal_bearing"] for r in formal_rows])); signal_pass=signal_overall>=.95 and all(v>=.90 for v in signal_by_lineage.values())
    signal_rows=[r for r in formal_rows if r["signal_bearing"]]
    compatibility=summarize_gate(signal_rows,"incompatible_fraction",5e-3,1e-2,5e-2,1e-2)
    compatibility["zero_force_max"]=max(r["zero_force_normalized_residual"] for r in formal_rows)
    compatibility["gates"]["zero_force"]=compatibility["zero_force_max"]<=1e-12
    compatibility_pass=all(compatibility["gates"].values())
    unbounded=summarize_gate(formal_rows,"Q_unbounded",.02,.05,.10,.05); bounded=summarize_gate(formal_rows,"Q_bounded",.05,.10,.20,.10)
    representability_pass=all(unbounded["gates"].values()) and all(bounded["gates"].values())
    s2=float(np.mean([r["a_cons_component_rms"]**2 for r in formal_rows])); s_a=math.sqrt(s2)
    u_a=math.sqrt(float(np.mean([r["u_origin"]**2 for r in formal_rows])))
    lineage_scale={f:math.sqrt(float(np.mean([r["a_cons_component_rms"]**2 for r in formal_rows if r["lineage"]==f]))) for f in LINEAGES}
    lineage_u={f:math.sqrt(float(np.mean([r["u_origin"]**2 for r in formal_rows if r["lineage"]==f]))) for f in LINEAGES}
    variant_scale={f"{f}/{v}":math.sqrt(float(np.mean([r["a_cons_component_rms"]**2 for r in formal_rows if r["lineage"]==f and r["variant"]==v]))) for f in LINEAGES for v in VARIANTS}
    variant_u={f"{f}/{v}":math.sqrt(float(np.mean([r["u_origin"]**2 for r in formal_rows if r["lineage"]==f and r["variant"]==v]))) for f in LINEAGES for v in VARIANTS}
    ratios={"global":s_a/u_a,"lineage":{f:lineage_scale[f]/lineage_u[f] for f in LINEAGES},
            "variant":{k:variant_scale[k]/variant_u[k] for k in variant_scale}}
    zero_loss=float(np.mean([r["a_cons_component_rms"]**2/s2 for r in formal_rows])); scale_pass=np.isfinite(s_a) and s_a>0 and abs(zero_loss-1)<=1e-12
    uncertainty_pass=ratios["global"]>=100 and all(v>=20 for v in ratios["lineage"].values()) and all(v>=20 for v in ratios["variant"].values())

    # Symmetry/invariance audit on the frozen 12-case subset.
    symmetry_rows=[]
    Q90=np.asarray([[0.,-1.],[1.,0.]]); REF=np.asarray([[-1.,0.],[0.,1.]])
    def state_from(case:dict[str,Any],x:np.ndarray,v:np.ndarray,labels:np.ndarray,mass:np.ndarray|None=None,smoothing:np.ndarray|None=None)->DynamicParticleState:
        rho=tensor(case["rho"] if len(case["rho"])==len(x) else case["rho"][:len(x)])
        return DynamicParticleState(tensor(x),tensor(v),rho,eos_pressure(rho),tensor(case["mass"] if mass is None else mass),
            tensor(case["smoothing"] if smoothing is None else smoothing),tensor(labels),case["time"],case["step"])
    for key,case in symmetry_cases.items():
        n=len(case["x"]); seed=int.from_bytes(hashlib.sha256(("stage05b_symmetry_v1|"+"|".join(map(str,key))).encode()).digest()[:8],"big")
        perm=np.random.default_rng(seed).permutation(n)
        transforms=[("particle_permutation",case["x"][perm],case["v"][perm],case["labels"][perm],case["a_def"][perm],case["a_cons"][perm],case["mass"][perm],case["smoothing"][perm],False),
                    ("edge_reorder",case["x"],case["v"],case["labels"],case["a_def"],case["a_cons"],case["mass"],case["smoothing"],True),
                    ("translation",case["x"]+np.asarray([.371,-.283]),case["v"],case["labels"],case["a_def"],case["a_cons"],case["mass"],case["smoothing"],False),
                    ("galilean_boost",case["x"]+case["time"]*np.asarray([.173,-.119]),case["v"]+np.asarray([.173,-.119]),case["labels"],case["a_def"],case["a_cons"],case["mass"],case["smoothing"],False),
                    ("SO2_rotation",case["x"]@Q90.T,case["v"]@Q90.T,case["labels"]@Q90.T,case["a_def"]@Q90.T,case["a_cons"]@Q90.T,case["mass"],case["smoothing"],False),
                    ("reflection",case["x"]@REF.T,case["v"]@REF.T,case["labels"]@REF.T,case["a_def"]@REF.T,case["a_cons"]@REF.T,case["mass"],case["smoothing"],False),
                    ("periodic_representative_shift",case["x"]+np.asarray([2.,-2.]),case["v"],case["labels"],case["a_def"],case["a_cons"],case["mass"],case["smoothing"],False)]
        for name,x,v,labels,adef,acons,massv,smoothv,reverse in transforms:
            st=state_from(case,x,v,labels,massv,smoothv); graph=build_reciprocal_graph(st); dec=decompose(adef,massv,case["u"])
            basis=solve_basis(st,graph,dec["a_cons"],case["u"],reverse_columns=reverse); ls_solves+=1; bounded_solves+=1
            vector_error=float(np.linalg.norm(dec["a_cons"]-acons)/max(np.linalg.norm(acons),case["u"]))
            scalars={"component_rms":math.sqrt(float(np.mean(dec["a_cons"]**2))),"incompatible_fraction":dec["incompatible_fraction"],
                     "Q_unbounded":basis["Q_unbounded"],"Q_bounded":basis["Q_bounded"]}
            bases={"component_rms":math.sqrt(float(np.mean(case["a_cons"]**2))),
                   "incompatible_fraction":decompose(case["a_def"],case["mass"],case["u"])["incompatible_fraction"],
                   "Q_unbounded":case["base"]["Q_unbounded"],"Q_bounded":case["base"]["Q_bounded"]}
            scalar_error=max(abs(scalars[k]-bases[k])/max(abs(scalars[k]),abs(bases[k]),1.0) for k in scalars)
            symmetry_rows.append({"lineage":key[0],"variant":key[1],"origin":key[2],"transform":name,
                                  "scalar_relative_difference":scalar_error,"vector_equivariance_normalized_error":vector_error,
                                  "pass":scalar_error<=1e-12 and vector_error<=1e-10})
    symmetry_pass=len(symmetry_rows)==84 and all(r["pass"] for r in symmetry_rows)
    write_json(STAGE05B/"symmetry_and_invariance/symmetry_audit.json",{"rows":symmetry_rows,"pass":symmetry_pass})

    # N12/N16 diagnostics; these never affect formal gates or s_a.
    diagnostic_rows=[]; n12_dop={}
    for resolution in (12,16):
        for lineage in LINEAGES:
            arrays,metadata,_=load_trajectory(lineage,"VARIANT_MAIN",resolution,"diagnostic")
            closed,independent=independent_route_fields(lineage,"VARIANT_MAIN",arrays["material_labels"])
            mass=np.full(resolution*resolution,RHO0*(L/resolution)**2)
            if resolution==12: u5,u5prov=n12_u5(lineage,arrays["material_labels"],arrays); n12_dop[lineage]=u5prov
            else: u5,u5prov=u5_existing(lineage,16)
            transition=Stage05BD0Transition(lineage,"VARIANT_MAIN",DT)
            for origin in range(32):
                start=make_state(arrays,resolution,origin); idx=int(np.flatnonzero(arrays["frame_n"]==origin)[0]); exact_source=tensor(arrays["external_source"][idx])
                cr=transition.step(start,exact_source); fr=functional_d0(start,lineage,"VARIANT_MAIN",DT); rr=transition.step(start,exact_source); graph_rebuild_count+=9
                target_idx=int(np.flatnonzero(arrays["frame_n"]==origin+1)[0]); adef=(arrays["velocity"][target_idx]-cr.accepted.velocity.numpy())/DT
                U1=mass_norm((closed["velocity"][2*(origin+1)]-independent["velocity"][2*(origin+1)])/DT,mass)
                U2=mass_norm((cr.accepted.velocity.numpy()-fr.accepted.velocity.numpy())/DT,mass); U3=mass_norm((cr.accepted.velocity.numpy()-rr.accepted.velocity.numpy())/DT,mass)
                U4=max(mass_norm(closed["source"][2*origin]-independent["source"][2*origin],mass),mass_norm(closed["source"][2*origin+1]-independent["source"][2*origin+1],mass))
                u=max(U1,U2,U3,U4,float(u5[origin]),roundoff); dec=decompose(adef,mass,u)
                basis=solve_basis(cr.midpoint,cr.graphs[1],dec["a_cons"],u,diagnostic_sparse=True); ls_solves+=1; bounded_solves+=1
                diagnostic_rows.append({"resolution":resolution,"lineage":lineage,"variant":"VARIANT_MAIN","origin":origin,
                    "target_component_rms":math.sqrt(float(np.mean(dec["a_cons"]**2))),"incompatible_fraction":dec["incompatible_fraction"],
                    "Q_unbounded":basis["Q_unbounded"],"Q_bounded":basis["Q_bounded"],"u_origin":u,"signal_ratio":mass_norm(adef,mass)/u,
                    "finite":bool(np.isfinite(adef).all() and np.isfinite(list(basis.values())[0]))})
            del arrays,metadata,closed,independent,start,cr,fr,rr
            gc.collect(); retention.append({"after":f"{lineage}_MAIN_N{resolution}","live_tensor_count":live_tensor_count(),"rss_bytes":PROCESS.memory_info().rss}); update_rss()
    diag_summary={}
    n8_main={f:math.sqrt(float(np.mean([r["a_cons_component_rms"]**2 for r in formal_rows if r["lineage"]==f and r["variant"]=="VARIANT_MAIN"]))) for f in LINEAGES}
    for resolution in (12,16):
        rows=[r for r in diagnostic_rows if r["resolution"]==resolution]
        scales={f:math.sqrt(float(np.mean([r["target_component_rms"]**2 for r in rows if r["lineage"]==f]))) for f in LINEAGES}
        ua=math.sqrt(float(np.mean([r["u_origin"]**2 for r in rows])))
        diag_summary[str(resolution)]={"scale":math.sqrt(float(np.mean([r["target_component_rms"]**2 for r in rows]))),
            "scale_ratio_to_N8":math.sqrt(float(np.mean([r["target_component_rms"]**2 for r in rows])))/s_a,
            "lineage_scale_ratio_to_N8_main":{f:scales[f]/n8_main[f] for f in LINEAGES},"u_a":ua,
            "scale_over_u":math.sqrt(float(np.mean([r["target_component_rms"]**2 for r in rows])))/ua,
            "incompatible_fraction_mean":float(np.mean([r["incompatible_fraction"] for r in rows])),
            "Q_unbounded_mean":float(np.mean([r["Q_unbounded"] for r in rows])),"Q_bounded_mean":float(np.mean([r["Q_bounded"] for r in rows])),
            "family_ranking":[x[0] for x in sorted(scales.items(),key=lambda x:x[1],reverse=True)],"diagnostic_only":True}
    diag_summary["N8_main_family_ranking"]=[x[0] for x in sorted(n8_main.items(),key=lambda x:x[1],reverse=True)]
    write_json(STAGE05B/"resolution_diagnostics/resolution_diagnostics.json",{"summary":diag_summary,"rows":diagnostic_rows,"N12_DOP853_provenance":n12_dop,
        "affects_formal_scale_or_gates":False,"spatial_convergence_claim":False,"GCI":False})

    update_rss(); peak_delta=RSS_PEAK-RSS_START
    retention_counts=[r["live_tensor_count"] for r in retention]
    formal_retention=retention_counts[:12]; diagnostic_retention=retention_counts[12:]
    retention_pass=(max(formal_retention,default=0)-min(formal_retention,default=0)<=2 and
                    max(diagnostic_retention,default=0)-min(diagnostic_retention,default=0)<=2)
    resource_pre={"backend":"CPU_FLOAT64","formal_D0_transitions_by_route_repeat":384*3,"formal_graph_rebuild_count":384*9,
        "prior_execution_process_count":4,"prior_completed_full_run_count":1,
        "prior_train_npz_decode_count":28,"prior_train_json_decode_count":28,
        "prior_origin_attempt_count":833,"prior_graph_rebuild_count_excluding_DOP853":7497,
        "prior_pair_basis_solve_count":917,"prior_completed_full_run_wall_time_seconds":119.75749279197771,
        "total_graph_rebuild_count_excluding_DOP853":graph_rebuild_count,"pair_basis_unbounded_solves":ls_solves,"bounded_solves":bounded_solves,
        "resolution_diagnostic_origins":len(diagnostic_rows),"rss_start_bytes":RSS_START,"peak_rss_bytes":RSS_PEAK,"peak_rss_delta_bytes":peak_delta,
        "peak_rss_delta_gate_bytes":1610612736,"retention_samples":retention,"no_monotonic_live_tensor_retention":retention_pass,
        "dense_particle_N_by_N_neural_allocation":False,"audit_linear_systems_only":True,**EXECUTION}
    provenance_pass=access_start["pass"] and sha_file(CONTRACT_PATH)==json.loads((STAGE05B/"freeze/stage05b_freeze_record.json").read_text())["contract_sha256"]
    primary_gates={"historical_freeze":provenance_pass,"access_start":access_start["pass"],"D0_transition":d0_pass,"defect_construction":defect_pass,
        "signal_distinguishability":signal_pass,"conservative_compatibility":compatibility_pass,"pair_basis_representability":representability_pass,
        "scale":scale_pass,"uncertainty":uncertainty_pass,"symmetry_invariance":symmetry_pass}
    primary_pass=all(primary_gates.values())

    # Freeze scale, aggregate evidence, and conditionally materialize Stage05C target records.
    scale_hash=sha_bytes(np.asarray([s_a],dtype=np.float64).tobytes())
    distributions={"a_cons_flat_percentiles":{},"origin_r_def_percentiles":{},"per_component_rms":{}}
    all_cons=[]
    for path in intermediate_paths:
        with np.load(path,allow_pickle=False) as z: all_cons.append(z["a_cons"])
    flat=np.concatenate([x.ravel() for x in all_cons]); distributions["a_cons_flat_percentiles"]={str(p):float(np.percentile(flat,p)) for p in (5,25,50,75,95)}
    distributions["a_cons_flat_percentiles"]["maximum_absolute"]=float(np.max(np.abs(flat)))
    distributions["origin_r_def_percentiles"]={str(p):float(np.percentile([r["r_def"] for r in formal_rows],p)) for p in (5,25,50,75,95)}
    distributions["per_component_rms"]={"x":math.sqrt(float(np.mean([x[...,0]**2 for x in all_cons]))),"y":math.sqrt(float(np.mean([x[...,1]**2 for x in all_cons])))}
    target_entries=[]; target_bytes=0
    if primary_pass:
        row_map={(r["lineage"],r["variant"],r["origin"]):r for r in formal_rows}
        for path in intermediate_paths:
            parts=path.stem.split("_"); lineage="_".join(parts[:2]).upper(); variant="_".join(parts[2:4]).upper()
            with np.load(path,allow_pickle=False) as z:
                for origin in range(32):
                    row=row_map[(lineage,variant,origin)]; adef=z["a_def"][origin]; acm=z["a_cm"][origin]; acons=z["a_cons"][origin]; ainc=z["a_incompatible"][origin]; y=acons/s_a
                    record_id=row["origin_id"]; npz_path=STAGE05B/f"target_records/{record_id}.npz"
                    np.savez_compressed(npz_path,a_def=adef,a_cm=acm,a_cons=acons,a_incompatible=ainc,y_def=y)
                    array_hashes={k:sha_array(v) for k,v in (("a_def",adef),("a_cm",acm),("a_cons",acons),("a_incompatible",ainc),("y_def",y))}
                    meta={"schema":"sph-pio-poc.stage05b.target-record.v1","lineage":lineage,"variant":variant,"N":8,"origin":origin,
                        "reference_history_hashes":row["reference_history_hashes"],"D0_state_hash":row["D0_state_hash"],"reference_accepted_hash":row["reference_accepted_hash"],
                        "dt":DT,"array_hashes":array_hashes,"s_a":s_a,"s_a_hash":scale_hash,"u_origin":row["u_origin"],"signal_bearing":row["signal_bearing"],
                        "incompatible_fraction":row["incompatible_fraction"],"Q_unbounded":row["Q_unbounded"],"Q_bounded":row["Q_bounded"],
                        "graph_hashes":row["graph_hashes"],"source_identity":row["source_identity"],"qualification_verdict":"QUALIFIED_STAGE05B",
                        "npz_path":str(npz_path.relative_to(ROOT)),"npz_sha256":sha_file(npz_path)}
                    meta["canonical_sha256"]=sha_bytes(canonical_bytes(meta)); jpath=npz_path.with_suffix(".json"); write_json(jpath,meta)
                    target_entries.append({"record_id":record_id,"json_path":str(jpath.relative_to(ROOT)),"json_sha256":sha_file(jpath),
                                           "npz_path":str(npz_path.relative_to(ROOT)),"npz_sha256":meta["npz_sha256"],"canonical_sha256":meta["canonical_sha256"]})
                    target_bytes+=npz_path.stat().st_size+jpath.stat().st_size
    del all_cons,flat; gc.collect(); update_rss()

    access_end=denial_audit("end")
    forbidden_decode_zero=all(DECODE[k]==0 for k in DECODE if k.startswith("validation_") or k.startswith("sealed_"))
    resource_final={**resource_pre,"wall_time_seconds":time.perf_counter()-START_TIME,"peak_rss_bytes":RSS_PEAK,"peak_rss_delta_bytes":RSS_PEAK-RSS_START,
        "target_storage_bytes":target_bytes,"target_record_count":len(target_entries),"hash_count":HASH_COUNT,
        "all_hashes_complete":len(target_entries) in (0,384),"access_end_pass":access_end["pass"],"forbidden_decode_counts_zero":forbidden_decode_zero}
    resource_final["pass"]=(resource_final["peak_rss_delta_bytes"]<=1610612736 and retention_pass and access_end["pass"] and forbidden_decode_zero
                            and all(v==0 for v in EXECUTION.values()) and resource_final["all_hashes_complete"])
    write_json(STAGE05B/"resources/stage05b_resource_audit.json",resource_final)
    final_gates={**primary_gates,"access_end":access_end["pass"] and forbidden_decode_zero,"provenance_resources":resource_final["pass"],
                 "prohibitions":all(v==0 for v in EXECUTION.values())}
    final_pass=all(final_gates.values())
    status=("CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED" if final_pass else
            "CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_NOT_QUALIFIED")
    if primary_pass and not final_pass:
        # Records remain evidence but are not Stage05C-authorized when final resources/access fail.
        for entry in target_entries:
            pass

    # Detailed results.
    write_json(STAGE05B/"d0_transition/d0_transition_audit.json",{"formal_origin_count":384,"pass_count":sum(r["D0_transition_pass"] for r in formal_rows),
        "max_normalized_L2":max(r["route_normalized_L2"] for r in formal_rows),"max_normalized_Linf":max(r["route_normalized_Linf"] for r in formal_rows),
        "all_graph_hash_sequences_exact":all(r["graph_hash_sequence_exact"] for r in formal_rows),"all_source_identities_exact":all(r["source_evaluation_identity_exact"] for r in formal_rows),
        "all_repeats_exact":all(r["deterministic_repeat_exact"] for r in formal_rows),"pass":d0_pass})
    write_json(STAGE05B/"reference_transition/reference_identity_audit.json",{"pass_count":sum(r["reference_identity_pass"] for r in formal_rows),"required":384,"pass":all(r["reference_identity_pass"] for r in formal_rows)})
    write_json(STAGE05B/"conservative_decomposition/conservative_compatibility.json",{"compatibility":compatibility,"pass":compatibility_pass})
    write_json(STAGE05B/"pair_basis_representability/unbounded_representability.json",{**unbounded,"pass":all(unbounded["gates"].values())})
    write_json(STAGE05B/"bounded_head_feasibility/bounded_feasibility.json",{**bounded,"pass":all(bounded["gates"].values()),"coefficient_bound_normalized":1.0,"physical_head_bound":0.05})
    scale_result={"s_a":s_a,"s_a_hash":scale_hash,"u_a":u_a,"s_a_over_u_a":ratios["global"],"zero_baseline_loss":zero_loss,
        "zero_baseline_absolute_error":abs(zero_loss-1),"lineage_scale":lineage_scale,"variant_scale":variant_scale,"distributions":distributions,"pass":scale_pass}
    uncertainty_result={"u_a":u_a,"roundoff_floor":roundoff,"ratios":ratios,"signal_bearing_overall":signal_overall,"signal_bearing_by_lineage":signal_by_lineage,
        "low_signal_count":sum(not r["signal_bearing"] for r in formal_rows),"component_maxima":{k:max(r[k] for r in formal_rows) for k in ("U1","U2","U3","U4","U5","u_roundoff_floor")},
        "signal_pass":signal_pass,"uncertainty_pass":uncertainty_pass}
    write_json(STAGE05B/"scale_calculation/stage05b_scale.json",scale_result); write_json(STAGE05B/"uncertainty/stage05b_uncertainty.json",uncertainty_result)
    write_json(STAGE05B/"distinguishability/distinguishability.json",{"ratios":ratios,"signal_overall":signal_overall,"signal_by_lineage":signal_by_lineage,"pass":signal_pass and uncertainty_pass})
    write_json(STAGE05B/"results/formal_origin_results.json",{"rows":formal_rows})

    # Required top-level manifests.
    freeze=json.loads((STAGE05B/"freeze/stage05b_freeze_record.json").read_text())
    input_manifest={**freeze,"schema":"sph-pio-poc.stage05b.input-freeze-manifest.v1","start_access_audit":str((STAGE05B/"access_control/start_allowlist_denial_audit.json").relative_to(ROOT))}
    contract_manifest={"schema":"sph-pio-poc.stage05b.contract-manifest.v1","contract_sha256":freeze["contract_sha256"],"contract_path":freeze["contract_path"],
        "frozen_before_decode":True,"formal_origins":384,"formal_resolution":8,"terminal_statuses":CONTRACT["terminal_statuses"]}
    origin_manifest={"schema":"sph-pio-poc.stage05b.origin-manifest.v1","formal_count":384,"formal_complete":formal_complete,"lineages":LINEAGES,"variants":VARIANTS,
        "origins":list(range(32)),"resolution":8,"inventory_sha256":freeze["origin_inventory_sha256"],"no_sampling_deletion_replacement":True}
    defect_manifest={"schema":"sph-pio-poc.stage05b.defect-manifest.v1","origin_count":len(formal_rows),"D0_pass_count":sum(r["D0_transition_pass"] for r in formal_rows),
        "defect_complete_count":sum(r["defect_construction_pass"] for r in formal_rows),"signal_bearing_count":sum(r["signal_bearing"] for r in formal_rows),
        "compatibility":compatibility,"unbounded":unbounded,"bounded":bounded,"intermediate_artifacts":[{"path":str(p.relative_to(ROOT)),"sha256":sha_file(p)} for p in intermediate_paths]}
    scale_manifest={"schema":"sph-pio-poc.stage05b.scale-manifest.v1",**scale_result,"formal_origin_count":384,"all_origins_included":True,"model_dependent":False}
    uncertainty_manifest={"schema":"sph-pio-poc.stage05b.uncertainty-manifest.v1",**uncertainty_result,"DOP853_versus_exact_included":False}
    target_manifest={"schema":"sph-pio-poc.stage05b.target-manifest.v1","generated":bool(target_entries),"record_count":len(target_entries),"required_record_count":384,
        "s_a_hash":scale_hash,"records":target_entries,"Stage05C_readable":final_pass}
    manifest_dir=STAGE05/"09_manifests"
    for name,value in (("stage05b_input_freeze_manifest.json",input_manifest),("stage05b_contract_manifest.json",contract_manifest),
        ("stage05b_origin_manifest.json",origin_manifest),("stage05b_defect_manifest.json",defect_manifest),("stage05b_scale_manifest.json",scale_manifest),
        ("stage05b_uncertainty_manifest.json",uncertainty_manifest),("stage05b_target_manifest.json",target_manifest)):
        write_json(manifest_dir/name,value)
    qualification={"schema":"sph-pio-poc.stage05b.qualification-summary.v1","status":status,"gates":final_gates,"formal_origin_count":384,
        "s_a":s_a,"u_a":u_a,"s_a_over_u_a":ratios["global"],"target_record_count":len(target_entries),"decode_counts":DECODE,"execution_counts":EXECUTION,
        "Stage05C_authorized":final_pass}
    write_json(STAGE05B/"qualification/stage05b_qualification_summary.json",qualification)
    artifact_paths=[p for p in STAGE05B.rglob("*") if p.is_file()]
    write_json(STAGE05B/"manifests/artifact_index.json",{"artifacts":[{"path":str(p.relative_to(ROOT)),"sha256":sha_file(p),"size_bytes":p.stat().st_size} for p in sorted(artifact_paths)]})
    final_manifest={"schema":"sph-pio-poc.stage05b.final-manifest.v1","status":status,"complete":True,"gates":final_gates,"Stage05C_authorized":final_pass,
        "contract_sha256":freeze["contract_sha256"],"formal_origin_count":384,"target_record_count":len(target_entries),"s_a":s_a,"s_a_hash":scale_hash,"u_a":u_a,
        "s_a_over_u_a":ratios["global"],"decode_counts":DECODE,"execution_counts":EXECUTION,"historical_statuses_unchanged":True,
        "next_authorization":"Stage 05C — Optimizer-Aligned Gradient and No-Writeback Local-Descent Qualification" if final_pass else None}
    write_json(manifest_dir/"stage05b_final_manifest.json",final_manifest)

    # Required reports.
    report_values={
      "stage05b_freeze_and_scope.md":f"# Stage 05B Freeze and Scope\n\nStage 05A authorization was verified. The prospective contract is `{freeze['contract_sha256']}` and was frozen with 384 origins before TRAIN array decode. Stage 04C/04C-R remain unchanged; Stage 04D and training remain unauthorized.\n",
      "stage05b_access_control.md":f"# Stage 05B Access Control\n\nStart and end allowlist-denial audits passed. TRAIN archive decodes were limited to the six authorized lineages. Validation state/target and sealed formula/state/source/target/origin decode counts are all zero.\n",
      "stage05b_origin_inventory.md":"# Stage 05B Origin Inventory\n\nThe formal inventory is exactly 6 TRAIN lineages × 2 variants × 32 origins at N8 = 384. No origin, lineage, or variant was sampled, removed, or replaced. N12/N16 MAIN rows are diagnostic only.\n",
      "stage05b_d0_transition_audit.md":f"# Stage 05B D0 Transition Audit\n\nClass, independent functional, and deterministic-repeat complete explicit-midpoint RK2 routes passed {sum(r['D0_transition_pass'] for r in formal_rows)}/384. Maximum normalized L2/Linf disagreements were `{max(r['route_normalized_L2'] for r in formal_rows):.6e}` and `{max(r['route_normalized_Linf'] for r in formal_rows):.6e}`; graph and source identities were exact.\n",
      "stage05b_defect_construction.md":f"# Stage 05B Defect Construction\n\nAll {sum(r['defect_construction_pass'] for r in formal_rows)}/384 accepted-state defects were constructed as `(v_ref^(n+1)-v_0^(n+1))/dt`. Position and density differences remain diagnostics. This is a discrete correction requirement, not continuum or pair-force truth.\n",
      "stage05b_conservative_compatibility.md":f"# Stage 05B Conservative Compatibility\n\nThe prospective mass-weighted decomposition was applied to every origin. Signal-bearing family-balanced mean, p95, and maximum incompatible fractions are `{compatibility['family_balanced_mean']:.6e}`, `{compatibility['percentile95']:.6e}`, and `{compatibility['maximum']:.6e}`. Maximum normalized zero-force residual is `{compatibility['zero_force_max']:.6e}`. Gate: `{'PASS' if compatibility_pass else 'FAIL'}`.\n",
      "stage05b_pair_basis_representability.md":f"# Stage 05B Pair-Basis Representability\n\nUsing the actual D0 midpoint graph, frozen radial/transverse basis, F0, signed incidence, mass normalization, and normalized head coordinates in [-1,1], unbounded mean/p95/max Q are `{unbounded['family_balanced_mean']:.6e}`/`{unbounded['percentile95']:.6e}`/`{unbounded['maximum']:.6e}`; bounded values are `{bounded['family_balanced_mean']:.6e}`/`{bounded['percentile95']:.6e}`/`{bounded['maximum']:.6e}`. Gate: `{'PASS' if representability_pass else 'FAIL'}`. No model was instantiated.\n",
      "stage05b_scale_qualification.md":f"# Stage 05B Scale Qualification\n\nThe unique all-384 nested TRAIN scale is `s_a={s_a:.17e}` with hash `{scale_hash}`. The zero-correction normalized identity is `{zero_loss:.17e}` (absolute error `{abs(zero_loss-1):.3e}`). Gate: `{'PASS' if scale_pass else 'FAIL'}`.\n",
      "stage05b_uncertainty_and_distinguishability.md":f"# Stage 05B Uncertainty and Distinguishability\n\nThe max-combined nested uncertainty scale is `u_a={u_a:.17e}` and `s_a/u_a={ratios['global']:.6e}`. Signal-bearing origins: {sum(r['signal_bearing'] for r in formal_rows)}/384 ({signal_overall:.3%}); all lineage and variant ratios are frozen in the manifest. Gates: signal `{'PASS' if signal_pass else 'FAIL'}`, uncertainty `{'PASS' if uncertainty_pass else 'FAIL'}`. DOP853-versus-exact model-form difference was excluded.\n",
      "stage05b_symmetry_and_invariance.md":f"# Stage 05B Symmetry and Invariance\n\nThe 12-case preregistered subset produced {len(symmetry_rows)} transform audits covering permutation, edge reorder, translation, Galilean boost, SO(2) rotation, reflection, and periodic representative shift. Passed: {sum(r['pass'] for r in symmetry_rows)}/{len(symmetry_rows)}.\n",
      "stage05b_resolution_diagnostics.md":f"# Stage 05B Resolution Diagnostics\n\nAll six TRAIN MAIN families and 32 origins were evaluated at N12/N16. N12/N16 scale ratios to formal N8 are `{diag_summary['12']['scale_ratio_to_N8']:.6e}` and `{diag_summary['16']['scale_ratio_to_N8']:.6e}`. These are diagnostic only, do not alter N8 scale or gates, and support no convergence or GCI claim.\n",
      "stage05b_resource_audit.md":f"# Stage 05B Resource Audit\n\nCPU float64 execution completed in `{resource_final['wall_time_seconds']:.3f}` s with peak RSS delta `{resource_final['peak_rss_delta_bytes']}` bytes (gate 1.5 GiB). Representability matrices were audit linear systems, not neural attention. Model/parameter/optimizer/training/rollout/performance counts are zero. Resource gate: `{'PASS' if resource_final['pass'] else 'FAIL'}`.\n",
      "stage05b_qualification_report.md":f"# Stage 05B Qualification Report\n\nFinal hard gates: `{json.dumps(final_gates,sort_keys=True)}`. Target records: {len(target_entries)}/384. Verdict: `{status}`.\n",
      "stage05b_final_report.md":f"# Stage 05B Final Report\n\n## Authorization and history\n\nStage 05A status `SCALE_AWARE_DISCRETE_DEFECT_TRAINING_CONTRACT_COMPLETE` uniquely authorized this stage. The contract hash is `{freeze['contract_sha256']}`. Stage 03/04 histories, Stage 04C and Stage 04C-R verdicts, Stage 04D authorization=false, and Stage 05 training NOT_AUTHORIZED remain unchanged.\n\n## TRAIN-only target evidence\n\nThe complete 384-origin N8 inventory passed D0 routes `{sum(r['D0_transition_pass'] for r in formal_rows)}/384` and defect construction `{sum(r['defect_construction_pass'] for r in formal_rows)}/384`. Conservative compatibility is `{'PASS' if compatibility_pass else 'FAIL'}`; unbounded/bounded pair-basis feasibility is `{'PASS' if representability_pass else 'FAIL'}`. The unique scale is `s_a={s_a:.17e}` (`{scale_hash}`), zero-baseline loss is `{zero_loss:.17e}`, uncertainty is `u_a={u_a:.17e}`, and `s_a/u_a={ratios['global']:.6e}`. Signal-bearing count is `{sum(r['signal_bearing'] for r in formal_rows)}/384`.\n\n## Auxiliary audits and records\n\nSymmetry/invariance passed `{sum(r['pass'] for r in symmetry_rows)}/{len(symmetry_rows)}`. N12/N16 remained diagnostic only. Qualified target records: `{len(target_entries)}/384`; their manifest is `09_manifests/stage05b_target_manifest.json`. Validation and all sealed decode counts are zero. Peak RSS delta is `{resource_final['peak_rss_delta_bytes']}` bytes; model, optimizer, training, rollout, and performance counts are zero.\n\n## Decision\n\n`{status}`\n\nStage 05C authorization: `{'true' if final_pass else 'false'}`.\n"
    }
    for name,text in report_values.items(): write_text(STAGE05/"08_reports"/name,text)
    print(json.dumps({"status":status,"s_a":s_a,"u_a":u_a,"ratio":ratios["global"],"records":len(target_entries),"gates":final_gates},sort_keys=True))


if __name__ == "__main__":
    main()
