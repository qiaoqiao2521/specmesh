# Project instructions

This repository maintains SpecMesh v1.1. Read PROJECT.md first. Read SPEC.md for normative
rules, docs/ARCHITECTURE.md for implementation boundaries, docs/DECISIONS.md for rationale,
and only the relevant plans/<task>/ files. CLAUDE.md delegates to this entry.

SPEC.md is the versioned standard; templates mirror its minimum structure. Map v0 and Area
Overlay are experiments, not mandatory adoption requirements. Preserve asserted/derived
authority and current-only scoped-memory injection. Generated .specmesh/cache stays untracked.

Maintain task_plan.md, findings.md and progress.md for substantial work. Update project intent,
architecture or decisions only for durable changes. Verify changes with unittest and, when map
inputs change, rebuild/check the map. Publish reviewed source; copy SPEC.md to local user-level
installations only after release verification. Never let generated graphs rewrite reviewed memory.

## 开发知识按需接入

先读本项目上下文。遇到方案取舍、重复问题或跨项目经验时，读取 `KNOWLEDGE_WORKFLOW_CONFIG` 指定的路径说明；未设置时查 `~/.config/knowledge-workflow/paths.md`，再从映射的 Obsidian `Wiki/开发知识入口.md` 选相关页，读写规则见 `Wiki/开发协作接入.md`。配置或来源不可用时跳过，不阻塞开发；不默认扫全库。

选用的经验及来源可以写入现有计划；当前事实、约束与验收仍留在本项目。收尾有可复用认识才由规划或收尾 Agent 修订知识页，普通任务不强制建卡或复测实体环境。适用边界见 [可选外部知识接入](docs/OPTIONAL-KNOWLEDGE.md)；此接入不改变 SPEC、模板或独立运行时，也不恢复 CM 联合发行要求。
