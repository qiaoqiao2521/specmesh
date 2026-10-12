# SpecMesh project context

## Why
帮助人和 Agent 从少量渐进链接的项目文件恢复意图、约束与当前工作，并完成可验证的独立交接。

## User Intent
优先交付独立 SpecMesh：无需 ControlMesh 或 History，也能读取当前状态、交接包含 dirty 基线的未完成任务，让全新 Agent B 产出被独立验收接受的实际结果，并独立发行。

2026-09-15 用户确认：SpecMesh 今后独立发展，不再要求与 CM 接轨。项目意图、计划、交接、验证与收尾由本仓独立定义和发行；外部工具可以消费 Markdown 或独立接口，但不形成绑定、配套升级或联合发行义务。Orca 也不是新的必需宿主。原生同会话 resume/marker recall 不等于全新 Agent 交付。

2026-10-12 用户要求把优先复用现有和外部实现、按需使用 Hook、允许有价值的部分自动化落实到项目准则。完整闭环和组件接齐不作为完成标准；继续扩展以真实任务收益为依据。

## Non-goals
不自建 Agent runtime、调度器、provider 管理、历史数据库或第四个总平台；不强制图基础设施，不自动把会话声明晋升为项目事实。本轮不做 Ops、多设备协作或跨仓生产切换。

## Success
全新 Agent 从入口和明确交接材料即可找到意图、架构、决定与唯一下一步；保留既有未提交修改，拒绝过期/取消任务，以实际 diff、固定验证和 owner 接受证明交付。状态读取、dirty 交接、新 Agent 实际交付、独立发行分别验收；实验性检索仍需重复真实任务证据。

## Constraints
当前规范源沿用 v1.1.0，2026-10-12 的复用与流程成本澄清已写入源码。已发布 v1.3.0 包保持原内容与身份，未重新发行；不能将当前源码与旧发行包视为相同文件集。模板只是脚手架，Map 为 derived，已审查 Markdown 为 asserted；只有 current area 注入 scoped memory，缓存可丢弃。未知、旧 done 和结构检查 pass 不得成为外部任务验收。

上次独立运行时交付中的“不改 SPEC.md/全局标准链接”是当次范围。2026-10-12 按新指令补充规范源与默认模板的复用、流程成本准则；本机已有标准软链接随源文件更新，不重建链接。已发布 v1.3.0 包、机器接口与历史验收保持原身份。独立版 S1/S2/S3/R1 已接受；当时的授权、串行验收顺序、尝试上限与追加授权保留在[交付记录](plans/bounded-delivery/progress.md)，不构成新的待执行队列。

默认在主工作区推进，确需并行或测试隔离才使用独立目录/worktree；保留已授权任务的直接 push 路径，不一律要求 PR。已配置授权的 CBC/AGY 等可按任务承担实现/审查。S3 已完成单次模型调用并获独立接受，次数与失败历史见交付记录；后续模型调用、发布和安装按新任务授权处理。产品验收是否需真实 provider 与开发执行者身份分开判断。

## Current State

2026-09-15 独立可用版S1/S2/S3/R1全部独立接受，4/4；不是全平台或旧CM集成完成。

v1.3.0已正式发行，源码/tag为0bfdfd1d4c79bdefc5926b87877253e69a6f93a7；CI34896336208的Python3.11/3.12各112项通过。远端下载包29/29文件匹配且与tag源码逐文件一致；本机specmesh --version=1.3.0，隔离运行及版本切换/回退验收通过。规范仍v1.1.0、全局标准链接未改。

S1累计尝试3；S2累计实现尝试5；S3全新AGY B调用1、修正0，真实产物和dirty保留获独立接受；R1修正1。费用unknown，已知S3 token字段及全部失败记录保留在[活动交付记录](plans/bounded-delivery/progress.md)。

[Release](https://github.com/muqiao215/specmesh/releases/tag/v1.3.0) · [最终验收](plans/bounded-delivery/evidence/SM-P0.R1/acceptance.md)。后续文档收口提交不改变已发布源码/tag身份。

## Current Priority

当前维护是[复用与流程成本准则](plans/reuse-principles-20261012/task_plan.md)，交付状态见[进度](plans/reuse-principles-20261012/progress.md)。此前独立交付已完成；本次不自动恢复 CM 接轨、Map v1 或 provider/device 扩展。

## Knowledge Map
- Optional external experience in planning/closeout → [OPTIONAL-KNOWLEDGE](docs/OPTIONAL-KNOWLEDGE.md); project facts and independent runtime remain local to this repository.
- Normative rules → [SPEC.md](SPEC.md)
- Architecture → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Decisions → [docs/DECISIONS.md](docs/DECISIONS.md)
- Reuse and process-cost clarification → [SPEC section](SPEC.md#复用与流程成本), [task](plans/reuse-principles-20261012/task_plan.md)
- Completed bounded delivery → [plan](plans/bounded-delivery/task_plan.md), [findings](plans/bounded-delivery/findings.md), [progress](plans/bounded-delivery/progress.md)
- Prior machine-port phases and evidence → [independent-plugin-port](plans/independent-plugin-port/task_plan.md)
- Release alignment → [plans/release-alignment/](plans/release-alignment/)
- Completed Map experiment → [plans/map-v0-spike/](plans/map-v0-spike/)
- Completed Area experiment → [plans/area-overlay-v0/](plans/area-overlay-v0/)
- Experimental configuration → [.specmesh/context.md](.specmesh/context.md)

- Plan status index → [plans/README.md](plans/README.md)

## Established direction

2026-09-14 开始的 [bounded-delivery](plans/bounded-delivery/task_plan.md) 已完成，是交付追溯入口。2026-09-15 确认长期独立方向：旧 SM/X IDs 仅用于追溯，CM 接轨不再是后续必做项。四个独立验收单元分母不变；旧 SM-P0/P1 的历史窄通过另列，不重复计数，不另建跨仓权威进度库。
