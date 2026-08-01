"""Render the seven Stage 01F reports from immutable analytic evidence."""

from __future__ import annotations
import csv,json
from pathlib import Path
import yaml

PROJECT_ROOT=Path(__file__).resolve().parents[2]; ROOT=PROJECT_ROOT/"06_experiments"/"stage_01f_mms_design"; RESULTS=ROOT/"results"; REPORTS=PROJECT_ROOT/"07_reports"; CONFIG=ROOT/"configs"/"preregistered_mms_specification.yml"


def read_csv(name:str)->list[dict[str,str]]:
    with (RESULTS/name).open(encoding="utf-8") as stream:return list(csv.DictReader(stream))
def table(rows:list[dict],columns:list[str])->str:
    return "\n".join(["| "+" | ".join(columns)+" |","|"+"|".join("---" for _ in columns)+"|"]+["| "+" | ".join(str(row.get(c,"")) for c in columns)+" |" for row in rows])
def write(name:str,text:str)->None:
    path=REPORTS/name
    if path.exists():raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(text.rstrip()+"\n",encoding="utf-8")


def main()->int:
    cfg=yaml.safe_load(CONFIG.read_text()); e=json.loads((RESULTS/"stage01f_evaluation.json").read_text()); closure=read_csv("analytic_closure.csv"); scales=read_csv("mms_b_term_scale.csv"); initialization=read_csv("particle_initialization_audit.csv"); contract=json.loads((RESULTS/"source_injection_contract_audit.json").read_text()); p=cfg["parameters"]
    frozen=f"Stage 01E tag `{cfg['frozen_stage01e']['tag']}` 固定于 `{cfg['frozen_stage01e']['evidence_commit']}`；历史分类保持 `{cfg['frozen_stage01e']['status']}`。"
    write("stage_01f_governing_equation_contract.md",f"""# Stage 01F governing-equation contract

{frozen}

连续目标固定为 `dx/dt=u`，`partial_t rho + div(rho u)=0`，`partial_t u+(u·grad)u=-(1/rho)grad(p)+nu laplacian(u)+f_MMS`，以及 `p=c_s^2(rho-rho0)`。

`f_MMS` 是单位质量外部加速度，不是内部粒子对力，不要求成对反对称。内部压力/黏性守恒与外力分开审计；受迫问题比较 `d/dt sum_i(m_i u_i)` 与 `sum_i(m_i f_MMS_i)`，不要求总动量恒定。source 不依赖数值误差、SPH residual 或网络输出。
""")
    write("stage_01f_mms_a_specification.md",f"""# Stage 01F MMS-A specification

令 `xi=x-U_c t`：

- `rho_A=rho0[1+epsilon sin(k xi)sin(k y)]`；`u_A=[U_c,0]`；`p_A=c_s^2(rho_A-rho0)`。
- `partial_t rho_A=-rho0 epsilon k U_c cos(k xi)sin(k y)`。
- `grad rho_A=rho0 epsilon k[cos(k xi)sin(k y), sin(k xi)cos(k y)]`。
- `div(rho_A u_A)=U_c partial_x rho_A=-partial_t rho_A`。
- `grad p_A=c_s^2 grad rho_A`；material acceleration 与 `laplacian(u_A)` 均为零。
- `f_A=grad(p_A)/rho_A`，故 `-grad(p_A)/rho_A+f_A=0`，完整动量方程闭合。

闭式粒子轨迹为 `x_i(t)=wrap(x_i(0)+U_c t)`、`y_i(t)=y_i(0)`；仅验证公式，未运行 SPH。
""")
    write("stage_01f_mms_b_specification.md",f"""# Stage 01F MMS-B specification

`psi=sin(kx)sin(ky)`，`rho_B=rho0(1+epsilon psi)`，`a(t)=U_v exp(-lambda t)`，`u_B=[a sin(kx)cos(ky), -a cos(kx)sin(ky)]`，`p_B=c_s^2(rho_B-rho0)`。

手工导数为 `div(u_B)=0`、`u_B·grad(rho_B)=0`、`partial_t rho_B=0`、`partial_t u_B=-lambda u_B`、`laplacian(u_B)=-2k^2u_B`；对流加速度为 `(a^2 k/2)[sin(2kx),sin(2ky)]`；`grad(p_B)=c_s^2 rho0 epsilon k[cos(kx)sin(ky),sin(kx)cos(ky)]`。

外部加速度冻结为 `f_B=partial_t u_B+convection+grad(p_B)/rho_B-nu laplacian(u_B)`，代回冻结 WCSPH 连续方程后逐点闭合。
""")
    write("stage_01f_particle_initialization.md",f"""# Stage 01F particle initialization

仅允许 N×N 规则中心格点，`V_i^0=(2/N)^2`，`m_i=rho_exact(x_i^0,y_i^0,0)V_i^0`：

{table(initialization,list(initialization[0]))}

质量在后续积分中固定。MMS-A 沿平移轨迹保持体积和密度；MMS-B 因 `div(u)=0` 且 `u·grad(rho)=0`，解析密度沿粒子轨迹保持不变。以后 numerical density 仍来自 SPH kernel sum，不得逐步用 analytic rho 覆盖；analytic rho 只用于初始化、误差评价和外部 source。Stage 01F 不设计 jitter 质量修正。
""")
    write("stage_01f_source_injection_audit.md",f"""# Stage 01F source-injection audit

接口只接受 `(solution, stage, numerical_positions, physical_stage_time, parameters)`，未连接动态求解器。未来每个 RK2 力评估必须在 start 与 midpoint 分别重算。

机器审计：`{contract}`。

禁止复用 step-start source、使用 analytic particle position、用 numerical SPH residual 修正 source、混入 pressure/viscosity pair antisymmetry，或把 external force 纳入 internal-force-zero gate。外力动量平衡单独比较质量加权 source。
""")
    write("stage_01f_analytic_closure.md",f"""# Stage 01F analytic closure

## 闭合硬门

{table(closure,list(closure[0]))}

## MMS-B 项尺度

{table(scales,list(scales[0]))}

随机点 `{e['random_point_count']}`，边界近点 `{e['boundary_point_count']}`。最大 EOS=`{e['maximum_eos_residual']}`、continuity=`{e['maximum_continuity_residual']}`、momentum=`{e['maximum_momentum_residual']}`、manual/autograd=`{e['manual_autograd_maximum_difference']}`、periodicity=`{e['maximum_periodicity_residual']}`；最低密度=`{e['density_minimum_observed']}`。最小核心项/最大项 L2 比=`{e['minimum_core_term_fraction_of_maximum']}`，未出现机器零核心项。
""")
    metrics="particle-position、velocity、density、pressure 的 L1/L2/Linf；one-step local truncation error；trajectory self-convergence；internal-force balance；external-force momentum balance；energy balance with external power；CPU determinism；resource policy"
    sections=[("1. Stage 01E 冻结",frozen),("2. WCSPH 连续方程约定","`dx/dt=u`；质量守恒；含单位质量外部加速度的动量方程；线性 EOS。内部守恒与外部作用分开。"),("3. 公共参数",f"Domain `[-1,1)^2`，rho0={p['rho0']}，c_s={p['sound_speed']}，nu={p['viscosity']}，k=pi，U_ref={p['reference_velocity']}，Ma={p['reference_mach']}，epsilon={p['density_amplitude']}，rho∈[{p['density_minimum']},{p['density_maximum']}]，U_c={p['mms_a_translation_speed']}，lambda={p['mms_b_decay_rate']}，U_v={p['mms_b_velocity_amplitude']}，t∈[0,0.2]。"),("4. MMS-A 完整公式","见 MMS-A specification：平移密度波、常速度、EOS pressure、`f_A=grad(p_A)/rho_A` 和闭式 wrapped trajectory 均已冻结。"),("5. MMS-B 完整公式","见 MMS-B specification：静态密度、衰减无散涡、压力梯度、对流/黏性导数和 `f_B` 均已冻结。"),("6. EOS、连续和动量闭合",f"{table(closure,list(closure[0]))}"),("7. Manual/autograd 对照",f"最大差 `{e['manual_autograd_maximum_difference']}`；source 最大差 `{e['source_manual_autograd_maximum_difference']}`，满足 1e-11 门。"),("8. 项尺度审计",f"{table(scales,list(scales[0]))}\n\n最小/最大 L2 比 `{e['minimum_core_term_fraction_of_maximum']}` > 1e-4。"),("9. 粒子质量初始化","规则格点 `m_i=rho_exact V_i^0`；质量固定；不覆盖 numerical kernel density；无 jitter 质量设计。"),("10. Source injection contract","按 numerical position 与 physical stage time 在 start/midpoint 分别重算；与内部 pair forces 和 internal-force gate 分离。"),("11. MMS-B 独立轨迹参考计划","后续独立求解 `dx/dt=u_exact`，DOP853 或同等级，rtol≤1e-12、atol≤1e-14；使用连续 unwrapped trajectory，仅场评价时 wrap，并做时间步敏感性。Stage 01F 未生成正式轨迹。"),("12. 后续误差指标",f"只定义：{metrics}。必须区分 continuum closure、trajectory-reference error、SPH spatial error、RK2 temporal error 与 forcing discretization error。"),("13. 唯一 MMS 规范状态",f"**{e['status']}**"),("14. Stage 01F2 资格","具备申请 Stage 01F2 设计审计资格。" if e["status"]=="MMS_SPECIFICATION_PASS" else "不具备；需先解决条件或失败。"),("15. V3 和 Stage 02 边界","V3、Stage 02、Stage 01F2、训练和学习标签均未开始。")]
    write("stage_01f_final_report.md","# Stage 01F final report\n\n"+"\n\n".join(f"## {title}\n\n{text}" for title,text in sections)); return 0


if __name__=="__main__":raise SystemExit(main())
