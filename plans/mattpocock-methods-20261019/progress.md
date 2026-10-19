# Progress

## Current

2026-10-19 四项方法已写入规范、模板与来源说明，本仓验证完成，待根 Codex 最终审阅和远端交付。规范版本仍为 v1.1.0，v1.3.0 包未变。

## Done

- 核对干净基线、仓库身份、既有标准软链接和相关旧计划。
- 更新 SPEC §4/§8、AGENTS/task_plan 模板、PROJECT、DECISIONS 与计划索引。
- 来源说明绑定上游提交及 MIT 许可，明确 dirty 审查命令的覆盖范围。
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`：112 项通过，11.209s。未增加镜像文档的测试。
- 10 个变动 Markdown 文件共 48 个本地链接及锚点通过；`git diff --check` 通过。
- `python3 scripts/map_v0.py build` 与 `check` 通过，缓存为 fresh；缓存保持未跟踪的派生数据。
- 既有标准软链接仍指向本仓 SPEC.md，源 SHA-256 为 `86f3ff4a227bbc6615c5f1566243dd42fdcf084ff270c033df40f77d81704fa5`。源码已更新不代表旧发行包或全部下游仓库已更新。

- 根已独立审阅，未发现实质问题；远端两笔账号/CI维护更新与本轮文件无重叠，已快进到0d3c2af后保留全部本轮修改。

## Remaining

- 根 Codex 审阅本仓变更，串行提交推送并读回远端。

## Issues

知识回写 `updated`：根已在CapMesh原docs/SKILL_SCOPE_20261001.md补充项目接入范围，同步DECISIONS D023及能力索引并读回。四项方法与dirty范围留在本仓SPEC及来源说明，不向其他知识库复制第二套规范。

`already_covered`：既有知识原页已覆盖按任务选择验收与真实调用路径。本轮不修改运行时或旧发行包。

## Next

根 Codex 接续审阅与整合；worker 已完成本仓检查，未提交推送。此计划不授权安装上游技能、修改发行包或自动同步全部下游仓库。
