# Findings

- 本仓开始时 main 干净，HEAD 为 `271df91b74a48bafa25a548c9420f9544b43ee32`；origin fetch/push 均为 `qiaoqiao2521/specmesh`。
- 本机默认标准是指向本仓 SPEC.md 的既有软链接；本轮只修改源，不复制、重建链接或重新发行。
- 上游 code-review 描述包含工作中变更，但实际比较 `git diff <fixed-point>...HEAD`，不能覆盖暂存、未暂存或未跟踪材料。本轮明确需求基准、代码基准与交付范围，分别核对这些材料。
- 上游 diagnosing-bugs 不直接调用 tdd，但在存在正确入口时要求先写回归再修复；本轮仅保留症状反馈与必要验证，不采用通用 TDD 门槛和高频循环。
- 上游 codebase-design 强制统一其术语；本仓改为沿用项目术语，区分无价值转发与承担兼容、协议、权限或隔离职责的适配层。
- 上游 to-tickets 自带 tracker、一票一文件及拆分确认；本仓复用现有 plan，明确可验收切片、真实依赖和集成验收点。
- 固定源码、版权与许可见[来源说明](../../docs/ENGINEERING-PRACTICES.md)。上游其他技能仍是参考，不进入本次实现范围。
- 共享知识候选：解释三点 diff 的已提交范围和 dirty 交付边界；根 Codex 决定归入既有主题页还是仅保留项目来源说明。worker 不并发写共享知识。
