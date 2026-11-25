# Decisions

## 2026-11-26 — 按缺口取证，复用计划与历史接口

决定：在 SPEC 渐进索引规则、默认模板及既有检索说明中补充按需上下文恢复。先判定当前动作真正缺什么，当前项目与代码优先，历史查询限定范围并保留原始来源；结果接回现有计划/交接。相同范围与修订的结果复用，失败后明确改变的查询依据或缺少的输入。

依据：用户授权 TraceMesh 新增缺口检测、历史召回与行动压缩，同时同步 SpecMesh。仓库已有 Map、独立 handoff 和 `retrieve_evidence.py`，后者按已审查绑定消费历史材料且只输出定位；直接复用即可保持职责清晰。历史命中、工具退出成功、派生摘要均不代表当前问题已解决或获得执行授权。

不采用：SpecMesh 内新增历史数据库、检索状态机、每轮强制搜索、固定缺口文件、强制跨仓升级或联合发行。规则澄清沿用规范 v1.1.0，不修改已发布 v1.3.0 包或机器接口，也不安装用户本机。更强检索只在真实缺口与重复失败证据表明现有方法不足时重访。

实施与验证见[本轮计划](../plans/context-gap-20261126/task_plan.md)。

## 2026-11-23 — 展示组件直接消费现有图谱

用户进一步明确：SpecMesh 是代码索引、图谱和演化记录的基础；前端组件应基于这些已有结构、可由脚本快速生成。上一版虽然调用了 Map，但主画布仍依赖另一份模块声明，未满足这一要求。

决定：原生 Map 成为默认页面的数据主干，文本与 HTML 共用全局/聚焦选择，保留 code/mem/spec 身份、关系来源和 area 门禁。现有业务 JSON 降为可选补充，不迁移或覆盖项目已经审阅的业务模块。原生图谱与业务关系分别显示其实际依据。

演化先实现本地 Git 基线与当前内容的结构比较，并链接现有项目意图、决定和计划文件的变化。使用同一 Map 引擎读取快照，不执行旧代码、不改当前检出、不自动下载缺失对象、不建历史索引。缺失或稀疏基线显示不可用；同文件哈希变化与逐函数变更区分。

代码与 Blender Harness 同步后直接推 main，页面的实际视觉和使用体验由用户验收。既有静态模板、来源绑定与检查能力继续复用；不扩成后台平台。

## 2026-11-22 — 为人提供可持续维护的架构视图

决定：按用户新授权，在 SpecMesh 源码中实现通用静态 Architecture Explorer，并为 Blender Harness 接入真实模块声明和 CI 构建。它补足人浏览职责、源码、检查证据和变更影响的入口；原来的机器可读 Map 和独立运行时继续保留各自用途。

职责和业务关系由项目 JSON 明确声明，当前代码与符号由已有 Map 派生，HTML 负责展示。复用 `code://`、`mem://`、`spec://` 和 current area 门禁；不建第二份索引，不自动推断业务契约或迁移旧路径。检查结果绑定实际来源；未运行保持 unknown，旧证据保持 stale，结构失败保持 blocked。

采用原生 HTML/SVG 和固定层级顺序；产物内嵌数据，离线可开。提交触发 CI 重建并保存 artifact；私有项目不自动发布公共页面。检查执行只发生在显式 `--run-checks`，影响范围只表示需要复核的下游。当前实现是可选源码工具，不扩大规范、运行时发行或历史任务验收。

使用说明见[架构入口](ARCHITECTURE-EXPLORER.md)，验收见[交付记录](../plans/architecture-explorer/progress.md)。

## 2026-10-19 — 工程方法融入原规范，执行体系保持独立

决定：按用户授权，将 `code-review`、`codebase-design`、`to-tickets`、`diagnosing-bugs` 的可迁移方法写入 SPEC §4/§8 与默认模板。固定来源、许可证及适配差异见[工程方法来源](ENGINEERING-PRACTICES.md)。

原因：行为切片、接口职责、双维审查和症状反馈能补强交接质量；另装一套技能、票据结构或调度链会重复既有能力。需求与规范证据分别判断，交付范围包括工作区时必须核对 dirty 材料，不能只审 `HEAD`。

不采用：强制 TDD、固定 Agent 数量、必建 tracker、统一重命名、自动重构和高频硬件复现。保留已有计划、项目术语、兼容职责与所选执行工具；本轮不改变运行时接口、规范版本号或 v1.3.0 发行包。

重访条件：真实任务暴露方法不足时，修订对应小段及证据边界；不因上游更新自动扩展范围。当前进度见[本轮计划](../plans/mattpocock-methods-20261019/progress.md)。

## 2026-10-12 — 优先复用，自动化按真实收益渐进

用户要求查看已有 Hook，继续借鉴 Google AX 与 OpenAI 的开源协作实现，并将选择原则落入项目准则；明确不必追求完整闭环，以免形式主义消耗注意力。

决定：在 SPEC 工作流与默认 AGENTS 模板补充复用顺序、最小适配、部分自动化和确定性 Hook 的边界。执行实现继续归宿主；工具发现和具体上游比较归能力账本，不将某个框架、插件或本机路径写成便携模板的依赖。没有真实收益时停止扩展，必要验收按当前交付物选择。

取代范围：更新上次任务“不改 SPEC/模板”的范围，不修改已发布运行时、机器合同或历史验收，不要求批量迁移已接入项目。此次是 v1.1 文档原则澄清；源码修订与已发布 v1.3.0 包身份分别判断。本机默认标准已链接 SPEC.md，源修改直接生效。

不采用：新 Hook 平台、默认阻塞 Stop 的完整闭环检查、强制知识写入、全项目调研门禁或为了多 Agent 而拆分任务。只有明确事件或重复痛点证明收益时，才在对应项目验证一个小机制。交付见[本次进度](../plans/reuse-principles-20261012/progress.md)。

## 2026-09-27 — 按需引用外部经验，保持项目事实独立

用户授权将 Obsidian 接入规划与收尾；采用 [可选外部知识接入](OPTIONAL-KNOWLEDGE.md) 的 Agent 文件约定。选用经验可以在现有计划引用，知识库保存可复用解释，当前项目事实仍留在本仓。

此决定补充跨项目学习路径，不改变独立发展方向，不修改 SPEC、默认模板、机器接口或发行包。未配置知识库时项目仍可独立工作；不恢复 CM 联合发行或强制外部检索要求。只有实际重复检索缺口出现时才重访接口方案。

## 2026-09-15 — SpecMesh 独立发展，不再以 CM 接轨为交付目标

决定：用户明确“以后的 specmesh 就单独了，不用和 cm 接轨”。SpecMesh 自主维护项目记忆、任务交接、独立接口与发行；CM lifecycle、CM 等义适配及三仓组合对齐退出本项目必做范围，标记为退出范围而非通过验收。

依据：用户本次指令为权威；[Orca与CM区别](chatgpt-conversation://6aa801c2-a34c-83e9-b4f5-3308147f1afe) 仅提供职责分离的讨论背景，其中集成方案不自动成为实施授权。

保留：既有接口兼容性、历史适配代码和验证证据；独立 S2 验收、S3 全新 Agent 真实交接与 R1 发行要求。没有独立验收结论仍不能标 done。

不采用：以 Orca 替换 CM 成为强制宿主；要求外仓配套升级、联合发布或迁移运行时；因方向变化删除历史记录。完整 provider/device 矩阵为可选后续扩展，不替代当前真实 Agent 验收。

重访条件：用户明确提出具体外部集成需求时另行界定范围；不能从旧计划自动恢复 CM 接轨。本决定覆盖下文旧决定中的 CM 后续必做含义。

## Keep continuity separate from execution and historical recall
SpecMesh stores reviewed intent/status; ControlMesh owns runtime lifecycle; History Viewer owns
historical discovery. Combining these responsibilities would make old transcript claims appear
current and couple the portable standard to an agent product. Revisit only with an evidenced
cross-project contract gap, not because all three tools contain context.

## Keep Map v0 and Area Overlay experimental
The graph improves bounded retrieval while separating derived code facts from asserted memory.
Tests and one repository experiment do not establish a universal required structure. Reject
mandatory graph services and automatic anchor rebinding; revisit after repeated real-task evidence.
Detailed adopt/adapt/reject conclusions remain in README.md and the completed Area plan.

## 2026-09-11 — Integrate against existing repository authority

Reuse the existing storage/parsers and keep SpecMesh independently callable. Do not install a second TaskHub from a proposal or equate historical handoff with live completion. The human overview and headless retrieval have separate entry points. See [scope and remaining limits](CODEKIT-INTEGRATION.md). Status: implemented for v1.2.0; broader roadmap gates remain planned.

## 2026-09-14 — 先独立可用版，按单卡退出

决定：SpecMesh 优先独立状态读取、dirty 基线交接、全新 Agent B 的实际任务验收和独立发行。最小通用流程合同定义意图/计划/交接/验证/收尾的输入、输出、失败与证据责任；CM 的执行权、History 的历史证据边界保留。文件格式与独立使用不得反向依赖宿主。详细出口及旧 ID 映射见 [bounded-delivery](../plans/bounded-delivery/task_plan.md)。

原因：现有独立 CLI 与 POSIX 快照已具窄通过证据，主要缺口是完整状态、可消费 dirty 交接和实际结果被接受。先要求三仓串联会把独立可用性推迟；same-session read/reopen 或 marker recall 又不能证明全新 Agent 完成交付。原生续接可以保留为宿主能力，但不替代本次独立验收。

不采用：先建 CM 插件宿主或第四个总平台；从零重写已验证 port/snapshot；用常驻 Goal/模型轮询追逐所有仓库。每张卡一次实现、一次独立审查、至多两轮修正，验证并更新本仓状态后退出，不自动取下一张。

本次规划不改已发布 SPEC.md 或全局标准链接；新行为通过明确的独立输出合同和有界任务验收后再决定发行。旧 SM-P0/P1 窄通过保留，SM-P2/SM-P3 更广范围、SM-P4 provider/device 与跨仓发行条件不自动关闭。当前四个增量验收单元只在本仓计数，不重复计算父项。

重访条件：独立 S1–S3 与 R1 取得真实验收后，若 CM/History 消费同一合同出现实际兼容缺口，再单列最小适配卡；若确实需要改变规范正文或扩大平台/信任范围，记录新出口和版本影响后另行审查。规划本身不使这些后续动作自动开始。
