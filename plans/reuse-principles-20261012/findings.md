# Findings

- SpecMesh 与 CapMesh 是独立、干净的 main 工作区。Obsidian 外层和自媒体仓库有既有修改，不是本次交付范围；保留各自 Git 边界。
- `~/.agents/standards/specmesh.md` 直接链接本仓 SPEC.md；更新源即可生效，不需要复制或改全局配置。
- Hookify 的部分提示词、文件条件与 Codex 事件字段有静态兼容缺口；配置 enabled 不证明当前运行时触发成功。具体核对及外部来源放 CapMesh `reviews/2026-10-12-agent-reuse.md`。
- CapMesh 自动清单与生成脚本都用 Star 阈值判成熟度，违背已有入口准则。两处一起修正，定向研究独立保存，生成清单只链接人工入口。
- AX、Agents SDK、Symphony 各自解决不同执行与协作问题。借鉴具体机制，不直接决定换掉现有 Mesh 执行工具；文档/源码核对不代表接入已验收。

## 2026-10-13 方法采用

- 复用原规范、模板和本计划，补齐分工的范围/依赖/产物/停止条件、按风险审查、冲突双方意图与真实方案推荐。不固定方案数量或模型/审查轮数。
- 来源为 Hermes 固定修订 eefdfe0692207a7520b3a8c764fe510024f552a1 的 one-three-one-rule、agent-merge-conflict-arbiter、dynamic-workflow、subagent-driven-development、sdlc-review；具体比较由 CapMesh 原研究维护，不复制技能实现。
- Hermes 子 Agent 示例与实际工具、配套参考存在静态契约差异；仅提取方法，宿主权限、等待/恢复与项目准则传递由实际执行工具负责。
- 编辑前规范源和模板的 Git 基线干净；外层 Obsidian 活跃改动保留在其独立 Git 边界，不默认并入本仓。
