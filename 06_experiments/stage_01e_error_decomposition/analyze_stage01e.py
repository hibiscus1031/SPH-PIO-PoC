"""Read frozen Stage 01D2 evidence and evaluate Stage 01E mechanisms."""

from __future__ import annotations

import csv,hashlib,json,math
from pathlib import Path
import statistics,subprocess,sys
from typing import Any

import numpy as np
from scipy.stats import spearmanr,theilslopes
import yaml

PROJECT_ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(PROJECT_ROOT/"01_solver"))
ROOT=PROJECT_ROOT/"06_experiments"/"stage_01e_error_decomposition"; RESULTS=ROOT/"results"; REPORTS=PROJECT_ROOT/"07_reports"; CONFIG=ROOT/"configs"/"preregistered_stage01e.yml"; D2=PROJECT_ROOT/"06_experiments"/"stage_01d2_v2_requalification"
from benchmark_alignment.support_path_model import bootstrap_two_term  # noqa:E402


def read_csv(path:Path)->list[dict[str,str]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))
def read_json(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))
def write_json(path:Path,value:dict)->None:
    if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
def write_csv(path:Path,rows:list[dict])->None:
    if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
    with path.open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
def markdown(rows:list[dict],columns:list[str])->str:
    lines=["| "+" | ".join(columns)+" |","|"+"|".join("---" for _ in columns)+"|"]
    lines.extend("| "+" | ".join(str(row.get(key,"")) for key in columns)+" |" for row in rows); return "\n".join(lines)
def report(name:str,text:str)->None:
    path=REPORTS/name
    if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(text.rstrip()+"\n",encoding="utf-8")


def verify_manifest(cfg:dict)->bool:
    path=PROJECT_ROOT/cfg["frozen_stage01d2"]["manifest"]
    return all(hashlib.sha256((PROJECT_ROOT/row["path"]).read_bytes()).hexdigest()==row["sha256"] for row in read_csv(path))


def d2_facts()->tuple[list[dict],dict[str,list[dict]]]:
    summaries=[read_json(path) for path in sorted((D2/"run_summaries").glob("*.json"))]
    all_runs=[{"run_id":row["run_id"],"phase":row["phase"],"layout":row["layout"],"seed":row["seed"],"N":row["resolution"],"dx":2/row["resolution"],"H":2/row["resolution"]*row["support_ratio"],"H_over_dx":row["support_ratio"],"mean_edge_count":row["mean_edge_count"],"wall_time_seconds":row["wall_time_seconds"],"status":row["status"]} for row in summaries]
    time=read_csv(D2/"results/time_results.csv"); space=read_csv(D2/"results/space_results.csv"); support=read_csv(D2/"results/support_family_results.csv"); disorder=read_csv(D2/"results/disorder_results.csv"); mach=read_csv(D2/"results/mach_results.csv")
    by_id={row["run_id"]:row for row in summaries}; n48=by_id["stage01d2_s_n48_inc"]
    increasing=[{"run_id":row["run_id"],"N":row["resolution"],"H_over_dx":row["support_ratio"],"velocity_relative_l2":row["final_velocity_relative_l2"],"modal_error":abs(float(row["final_modal_amplitude_error"])),"kinetic_energy_error":row["final_kinetic_energy_error"],"density_fluctuation":row["final_density_fluctuation_relative_rms"]} for row in [by_id[x] for x in ("stage01d2_s_n16_inc","stage01d2_s_n24_inc","stage01d2_t_n32_dt1p25e4","stage01d2_s_n48_inc")]]
    constant=[{"run_id":row["run_id"],"N":row["resolution"],"H_over_dx":4.0,"velocity_relative_l2":row["final_velocity_relative_l2"],"modal_error":abs(float(row["final_modal_amplitude_error"])),"kinetic_energy_error":row["final_kinetic_energy_error"],"density_fluctuation":row["final_density_fluctuation_relative_rms"]} for row in [by_id[x] for x in ("stage01d2_s_n16_inc","stage01d2_sf_n24_const","stage01d2_sf_n32_const")]]
    jitter=[]
    for row in [by_id[x] for x in ("stage01d2_dis_j05_s1","stage01d2_dis_j05_s2","stage01d2_dis_j05_s3","stage01d2_dis_j10_s4","stage01d2_dis_j10_s5","stage01d2_dis_j10_s6")]:
        jitter.append({"run_id":row["run_id"],"layout":row["layout"],"seed":row["seed"],"velocity_relative_l2":row["final_velocity_relative_l2"],"modal_error":abs(float(row["final_modal_amplitude_error"])),"kinetic_energy_error":row["final_kinetic_energy_error"],"density_fluctuation":row["final_density_fluctuation_relative_rms"],"current_rss_bytes":row["current_rss_bytes"],"peak_rss_bytes":row["peak_rss_bytes"],"rss_delta_bytes":row["quartile_rss_increase_bytes"],"rss_relative_increase":row["quartile_rss_relative_increase"],"edge_count":row["mean_edge_count"],"wall_time_seconds":row["wall_time_seconds"],"status":row["status"]})
    mach_full=[{"run_id":row["run_id"],"sound_speed":row["sound_speed"],"nominal_mach":row["nominal_mach"],"velocity_relative_l2":row["final_velocity_relative_l2"],"modal_error":abs(float(row["final_modal_amplitude_error"])),"density_fluctuation":row["final_density_fluctuation_relative_rms"],"maximum_mach":row["maximum_mach"],"peak_rss_bytes":row["peak_rss_bytes"]} for row in [by_id[x] for x in ("stage01d2_mach_cs10","stage01d2_dis_regular","stage01d2_mach_cs40")]]
    return all_runs,{"time":time,"increasing":increasing,"constant":constant,"jitter":jitter,"mach":mach_full,"n48":[n48],"support_raw":support,"space_raw":space,"disorder_raw":disorder,"mach_raw":mach}


def static_summary(rows:list[dict[str,str]])->list[dict]:
    result=[]
    for family in ("constant_neighbor","increasing_neighbor"):
        for layout in ("regular","jitter_05","jitter_10"):
            for n in (16,24,32,48,64):
                selected=[row for row in rows if row["support_family"]==family and row["layout"]==layout and int(row["resolution"])==n]
                item={"support_family":family,"layout":layout,"N":n,"cases":len(selected),"H":float(selected[0]["H"]),"dx":float(selected[0]["dx"]),"dx_over_H":float(selected[0]["dx_over_H"])}
                for key in ("density_rms","EOS_pressure_rms","R_pressure_operator_L2","R_EOS_initialization_L2","R_viscosity_L2","R_total_L2","closure_Linf","mean_edge_count"):
                    values=[float(row[key]) for row in selected]; item[f"{key}_mean"]=statistics.mean(values); item[f"{key}_max"]=max(values)
                result.append(item)
    return result


def trend_table(summary:list[dict])->list[dict]:
    result=[]
    for family in ("constant_neighbor","increasing_neighbor"):
        for layout in ("regular","jitter_05","jitter_10"):
            rows=[row for row in summary if row["support_family"]==family and row["layout"]==layout]
            errors=[row["R_total_L2_mean"] for row in rows]; dx=[row["dx"] for row in rows]; orders=[math.log(errors[i]/errors[i+1])/math.log(dx[i]/dx[i+1]) for i in range(4) if errors[i]>0 and errors[i+1]>0]
            monotone=all(errors[i+1]<errors[i] for i in range(4)); slope=float(np.polyfit(np.log(dx),np.log(errors),1)[0]); asymptotic=monotone and max(orders)-min(orders)<=0.25
            result.append({"support_family":family,"layout":layout,"endpoint_improvement":errors[-1]<errors[0],"global_fitted_positive_slope":slope>0,"global_slope":slope,"pairwise_monotonicity":monotone,"asymptotic_convergence":asymptotic,"N16_error":errors[0],"N64_error":errors[-1]})
    return result


def correlation_row(dataset:str,metric:str,x:list[float],y:list[float],cfg:dict)->dict:
    rho=float(spearmanr(x,y).statistic); slope,intercept,low,high=theilslopes(y,x,0.95); rng=np.random.default_rng(int(cfg["statistics"]["bootstrap_seed"])); boots=[]; n=len(x)
    for _ in range(int(cfg["statistics"]["bootstrap_resamples"])):
        indices=rng.integers(0,n,n); xb=np.asarray(x)[indices]; yb=np.asarray(y)[indices]
        if len(np.unique(xb))>1 and len(np.unique(yb))>1: boots.append(float(spearmanr(xb,yb).statistic))
    lo,hi=np.percentile(boots,[2.5,97.5])
    return {"dataset":dataset,"metric":metric,"n":n,"spearman_rho":rho,"bootstrap_95_low":float(lo),"bootstrap_95_high":float(hi),"theil_sen_slope":float(slope),"theil_sen_intercept":float(intercept),"theil_sen_slope_95_low":float(low),"theil_sen_slope_95_high":float(high),"causality_claimed":False}


def main()->int:
    cfg=yaml.safe_load(CONFIG.read_text()); RESULTS.mkdir(parents=True,exist_ok=True)
    manifest_ok=verify_manifest(cfg); tag_ok=subprocess.check_output(("git","rev-list","-n","1",cfg["frozen_stage01d2"]["tag"]),cwd=PROJECT_ROOT,text=True).strip()==cfg["frozen_stage01d2"]["evidence_head"]
    all_runs,facts=d2_facts(); write_csv(RESULTS/"stage01d2_all_run_geometry.csv",all_runs)
    static=read_csv(RESULTS/"initial_residual_matrix.csv"); summaries=static_summary(static); write_csv(RESULTS/"initial_residual_summary.csv",summaries); trends=trend_table(summaries); write_csv(RESULTS/"support_path_trends.csv",trends)
    short_summaries=[read_json(path) for path in sorted((RESULTS/"short_summaries").glob("*.json"))]; short_by={(row["layout"],int(row["seed"])):row for row in short_summaries}; static_n32={(row["layout"],int(row["seed"])):row for row in static if row["support_family"]=="increasing_neighbor" and int(row["resolution"])==32}
    metrics=("density_rms","EOS_pressure_rms","R_pressure_operator_L2","R_EOS_initialization_L2","R_viscosity_L2","R_total_L2")
    short_keys=[key for key in short_by if key[0]!="regular"]; correlations=[]
    for metric in metrics: correlations.append(correlation_row("short_20_frozen_jitter_seeds",metric,[float(static_n32[key][metric]) for key in short_keys],[float(short_by[key]["final_velocity_relative_l2"]) for key in short_keys],cfg))
    d2_velocity={(row["layout"],int(row["seed"])):float(row["velocity_relative_l2"]) for row in facts["jitter"]}; matched=list(d2_velocity)
    for metric in metrics: correlations.append(correlation_row("stage01d2_six_matched_jitter_runs",metric,[float(static_n32[key][metric]) for key in matched],[d2_velocity[key] for key in matched],cfg))
    write_csv(RESULTS/"disorder_correlations.csv",correlations)
    short_resource=[{"run_id":row["run_id"],"layout":row["layout"],"seed":row["seed"],"first_quartile_rss_median_bytes":row["first_quartile_rss_median_bytes"],"absolute_rss_increase_bytes":row["absolute_rss_increase_bytes"],"relative_rss_increase":row["relative_rss_increase"],"allocator_warmup_bytes":row["allocator_warmup_bytes"],"edge_count_change":row["edge_count_change"],"peak_rss_bytes":row["peak_rss_bytes"],"wall_time_seconds":row["wall_time_seconds"]} for row in short_summaries]; write_csv(RESULTS/"short_resource_auxiliary.csv",short_resource)
    growth=[]
    for layout in ("regular","jitter_05","jitter_10"):
        sample_files=[path for path in (RESULTS/"short_samples").glob("*.csv") if read_csv(path)[0]["layout"]==layout]
        samples=[read_csv(path) for path in sample_files]
        for step in range(41):
            selected=[row[step] for row in samples]
            growth.append({"layout":layout,"step":step,"time":float(selected[0]["time"]),"cases":len(selected),"velocity_relative_l2_mean":statistics.mean(float(x["velocity_relative_l2"]) for x in selected),"modal_error_mean":statistics.mean(float(x["modal_error"]) for x in selected),"density_fluctuation_mean":statistics.mean(float(x["density_fluctuation_relative_rms"]) for x in selected),"EOS_pressure_rms_mean":statistics.mean(float(x["EOS_pressure_rms"]) for x in selected),"pressure_operator_residual_l2_mean":statistics.mean(float(x["pressure_operator_residual_l2"]) for x in selected),"EOS_initialization_residual_l2_mean":statistics.mean(float(x["EOS_initialization_residual_l2"]) for x in selected),"viscosity_residual_l2_mean":statistics.mean(float(x["viscosity_residual_l2"]) for x in selected),"total_material_residual_l2_mean":statistics.mean(float(x["total_material_residual_l2"]) for x in selected),"minimum_separation_mean":statistics.mean(float(x["minimum_separation"]) for x in selected),"edge_count_mean":statistics.mean(float(x["edge_count"]) for x in selected)})
    write_csv(RESULTS/"short_growth_summary.csv",growth)
    increasing=[row for row in static if row["support_family"]=="increasing_neighbor"]
    model=bootstrap_two_term(np.array([float(x["H"]) for x in increasing]),np.array([float(x["dx_over_H"]) for x in increasing]),np.array([float(x["R_total_L2"]) for x in increasing]),resamples=int(cfg["support_model"]["bootstrap_resamples"]),seed=int(cfg["support_model"]["bootstrap_seed"]),stable_relative_ci_width_maximum=float(cfg["support_model"]["stable_relative_ci_width_maximum"])); write_json(RESULTS/"support_two_term_fit.json",model)
    focus=[row for row in static if row["support_family"]=="increasing_neighbor" and int(row["resolution"])==32 and row["layout"]!="regular"]
    med={key:statistics.median(float(row[key]) for row in focus) for key in ("R_pressure_operator_L2","R_EOS_initialization_L2","R_viscosity_L2","R_total_L2")}; ratio_threshold=float(cfg["classification"]["model_form_dominant_ratio"])
    closure=max(float(row["closure_Linf"]) for row in static); complete=len(static)==210 and len(short_summaries)==21 and all(row["status"]=="PASS" for row in short_summaries) and manifest_ok and tag_ok
    if not complete or closure>float(cfg["static_matrix"]["closure_absolute_tolerance"]): classification="E_EVIDENCE_INCOMPLETE"
    elif med["R_EOS_initialization_L2"]>=ratio_threshold*max(med["R_pressure_operator_L2"],med["R_viscosity_L2"]): classification="E_MODEL_FORM_ALIGNMENT_DOMINANT"
    elif max(med["R_pressure_operator_L2"],med["R_viscosity_L2"])>=ratio_threshold*med["R_EOS_initialization_L2"]: classification="E_DISORDER_PAIR_OPERATOR_DOMINANT"
    elif model["status"]=="two-term asymptotic fit not identifiable" and any(not x["pairwise_monotonicity"] for x in trends): classification="E_SUPPORT_PATH_NONASYMPTOTIC"
    else: classification="E_MIXED_ERROR_MECHANISMS"
    base_growth={layout:{row["step"]:row for row in growth if row["layout"]==layout} for layout in ("regular","jitter_05","jitter_10")}
    growth_class={}
    for layout,rows in base_growth.items():
        initial=rows[0]["velocity_relative_l2_mean"]; fifth=rows[5]["velocity_relative_l2_mean"]; final=rows[40]["velocity_relative_l2_mean"]
        growth_class[layout]="step_0_present" if initial>=0.5*final else ("first_acoustic_steps" if fifth>=0.5*final else "gradual_accumulation")
    baseline=np.array([float(x["first_quartile_rss_median_bytes"]) for x in short_resource]); absolute=np.array([float(x["absolute_rss_increase_bytes"]) for x in short_resource]); relative=np.array([float(x["relative_rss_increase"]) for x in short_resource]); edges=np.array([float(x["edge_count_change"]) for x in short_resource])
    resource_explanation={"spearman_relative_vs_baseline":float(spearmanr(relative,baseline).statistic),"spearman_absolute_vs_edge_change":float(spearmanr(absolute,edges).statistic) if len(np.unique(edges))>1 else None,"median_absolute_rss_increase_bytes":float(np.median(absolute)),"median_relative_rss_increase":float(np.median(relative)),"interpretation":"short-run auxiliary evidence only; no Stage 01D2 resource reclassification"}
    evaluation={"schema_version":"sph-pio-poc.stage01e.evaluation.v1","stage01d2_manifest_identity":manifest_ok,"stage01d2_tag_identity":tag_ok,"stage01d2_status":"STAGE01D2_V2_REQUALIFICATION_FAIL","static_cases":len(static),"short_trajectories":len(short_summaries),"short_children_all_pass":all(row["status"]=="PASS" for row in short_summaries),"maximum_closure_linf":closure,"focus_n32_increasing_jitter_median_components":med,"EOS_to_pressure_operator_ratio":med["R_EOS_initialization_L2"]/med["R_pressure_operator_L2"],"EOS_to_viscosity_ratio":med["R_EOS_initialization_L2"]/med["R_viscosity_L2"],"support_two_term_fit_status":model["status"],"short_growth_classification":growth_class,"resource_auxiliary":resource_explanation,"gci_statement":"GCI not justified","gci_recomputed":False,"unique_classification":classification,"v3_started":False,"stage02_started":False,"training_started":False,"formal_v2_rerun":False}
    write_json(RESULTS/"stage01e_evaluation.json",evaluation)
    generate_reports(cfg,evaluation,all_runs,facts,summaries,trends,correlations,growth,short_resource,model)
    print(classification); return 0


def generate_reports(cfg:dict,e:dict,all_runs:list[dict],facts:dict[str,list[dict]],summaries:list[dict],trends:list[dict],correlations:list[dict],growth:list[dict],resource_rows:list[dict],model:dict)->None:
    frozen=f"Stage 01D2 tag `{cfg['frozen_stage01d2']['tag']}` -> `{cfg['frozen_stage01d2']['evidence_head']}`；唯一历史状态保持 `{cfg['frozen_stage01d2']['status']}`。"
    report("stage_01e_stage01d2_result_audit.md",f"# Stage 01E — Stage 01D2 result audit\n\n{frozen}\n\n## 时间四轨迹\n\n{markdown(facts['time'],list(facts['time'][0]))}\n\n## Increasing family（含条件 N48）\n\n{markdown(facts['increasing'],list(facts['increasing'][0]))}\n\n## Constant family\n\n{markdown(facts['constant'],list(facts['constant'][0]))}\n\n## 六条 jitter\n\n{markdown(facts['jitter'],list(facts['jitter'][0]))}\n\n## 三条 Mach\n\n{markdown(facts['mach'],list(facts['mach'][0]))}\n\n## 全部 Stage 01D2 run 几何与成本\n\n{markdown(all_runs,list(all_runs[0]))}\n\nEndpoint improvement、global fitted positive slope、pairwise monotonicity 与 asymptotic convergence 是四个不同命题。Stage 01D2 可同时满足 endpoint 和全局正斜率而不满足 pairwise monotonicity；没有渐近区证据。**GCI not justified**，本阶段未重算 GCI。\n")
    report("stage_01e_tgv_benchmark_alignment.md",f"# Stage 01E — TGV benchmark alignment\n\n令 `k=pi`、`A=exp(-2 nu k^2 t)`。速度与解析压力按预登记式实现。显式结果为：`partial_t u=-2 nu k^2 u`；`(u·grad)u=(U0^2 A^2 k/2)[sin(2kx),sin(2ky)]`；`-grad(p)/rho0` 等于同一对流项；`nu laplacian(u)=-2 nu k^2 u`。因此 `D u/Dt=-grad(p)/rho0+nu laplacian(u)`。随机坐标 float64 测试见 `test_stage01e_exact_tgv_pressure.py` 与 `test_stage01e_material_acceleration.py`，完整 pytest 为证。\n\n这揭示 benchmark alignment：不可压 TGV 在 t=0 需要非零空间压力场，而冻结 WCSPH 初始化压力来自 `c_s^2(rho_h-rho0)`；两者并不自动相容。\n")
    noise_cols=["support_family","layout","N","cases","density_rms_mean","EOS_pressure_rms_mean","analytic_pressure_rms_mean"] if "analytic_pressure_rms_mean" in summaries[0] else ["support_family","layout","N","cases","density_rms_mean","EOS_pressure_rms_mean"]
    report("stage_01e_initial_density_pressure_noise.md",f"# Stage 01E — Initial density and pressure noise\n\n{markdown(summaries,noise_cols)}\n\n完整 210-case 逐种子值位于 `results/initial_residual_matrix.csv`。EOS pressure noise 是 kernel-sum density 偏差经 `c_s^2` 放大的结果；其与解析 TGV pressure 的差异是初始化/模型形式项，不等同于 pair operator residual。\n")
    residual_cols=["support_family","layout","N","cases","R_pressure_operator_L2_mean","R_EOS_initialization_L2_mean","R_viscosity_L2_mean","R_total_L2_mean","closure_Linf_max"]
    report("stage_01e_pair_operator_residuals.md",f"# Stage 01E — Pair-operator residuals\n\n{markdown(summaries,residual_cols)}\n\n残差逐点满足 `R_total = R_pressure_operator + R_EOS_initialization + R_viscosity`；最大闭合 Linf=`{e['maximum_closure_linf']:.6g}`。N32 increasing jitter 中位分量：`{e['focus_n32_increasing_jitter_median_components']}`。EOS/operator 比=`{e['EOS_to_pressure_operator_ratio']:.6g}`，EOS/viscosity 比=`{e['EOS_to_viscosity_ratio']:.6g}`。\n")
    report("stage_01e_support_path_analysis.md",f"# Stage 01E — Support-path analysis\n\n{markdown(trends,list(trends[0]))}\n\nFixed H/dx family 可用 dx 作单一描述参数；increasing family 同时改变 H 与 dx/H，global slope 不称为标准空间阶。两项描述拟合结果：`{model}`。最终表述：**{model['status']}**。Stage 01D2 的非单调性与 truncation–quadrature competition 是否一致，只作为机制相容性判断，不作为已证明的渐近阶。\n")
    report("stage_01e_disorder_error_correlation.md",f"# Stage 01E — Disorder/error correlation\n\n{markdown(correlations,list(correlations[0]))}\n\n短程 20 个冻结 jitter seed 与 Stage 01D2 可明确匹配的 6 条轨迹分别分析。Spearman、Theil–Sen robust slope 与 bootstrap 95% 区间均已报告。10% 的 9.338 放大需与各残差相关强弱联合解读；相关性不解释为因果，三个/六个 Stage 01D2 种子也不冒充完整随机不确定性。\n")
    endpoints=[row for row in growth if row["step"] in (0,1,5,40)]
    final_sections=[
        ("1. Stage 01D2 冻结",frozen),("2. 形式失败与科学失败", "Stage 01D2 的正式失败由冻结的 50% RSS/无序门触发；Stage 01E 只解释科学机制，不撤销或放宽该形式判定。"),("3. 完整时间、空间、jitter、Mach 数值", "完整数值位于 `stage_01e_stage01d2_result_audit.md`，包含所有 endpoint、H、dx、H/dx、edge count 与 wall time。"),("4. TGV 解析压力与材料加速度", "解析压力提供对流平衡，材料加速度恒等式已在随机 float64 坐标测试。"),("5. t=0 残差分解",f"210/210 cases，最大闭合 Linf `{e['maximum_closure_linf']:.6g}`。"),("6. EOS 初始压力不相容",f"N32 increasing jitter 的 EOS/operator 中位 L2 比为 `{e['EOS_to_pressure_operator_ratio']:.6g}`。"),("7. 压力与黏性保守算子残差",f"中位分量 `{e['focus_n32_increasing_jitter_median_components']}`。"),("8. 短程误差增长",f"{markdown(endpoints,['layout','step','time','velocity_relative_l2_mean','density_fluctuation_mean','EOS_pressure_rms_mean','total_material_residual_l2_mean'])}\n\n分类：`{e['short_growth_classification']}`。这些 40-step 轨迹不是新 V2 证据。"),("9. 支撑路径分析",f"{model['status']}；increasing path 不报告标准空间阶。"),("10. 无序相关性","Spearman、robust regression 和 bootstrap 区间见相关性报告；无因果声明。"),("11. 资源增量辅助解释",f"{markdown(resource_rows,list(resource_rows[0]))}\n\n`{e['resource_auxiliary']}`。不产生新的资源 PASS。"),("12. 唯一机制分类",f"**{e['unique_classification']}**"),("13. 下一阶段允许路线", "若为 model-form dominant：仅允许设计 WCSPH-compatible MMS；若 pair operator dominant：返回 V1 并重过 C1–C4；若 support nonasymptotic：拆分 fixed-ratio/consistency paths；若 mixed：先 MMS 再算子修复。当前只给出路线，不启动。"),("14. V3 与 Stage 02 边界","V3 与 Stage 02 均未开始；未训练网络、未生成标签、未重跑正式 V2。")]
    report("stage_01e_final_report.md","# Stage 01E final report\n\n"+"\n\n".join(f"## {title}\n\n{text}" for title,text in final_sections))


if __name__=="__main__": raise SystemExit(main())
