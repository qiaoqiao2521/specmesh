# 工程方法来源与适配

本页记录来源、适配边界与审查命令示例。现行规则以 [SPEC §4](../SPEC.md#4-文件职责) 和 [SPEC §8](../SPEC.md#8-工作流) 为准；本页不建立第二套流程。

## 固定来源

方法参考 [mattpocock/skills](https://github.com/mattpocock/skills/tree/49dd158d1076134a641b33efb035946536778336)，固定提交为 `49dd158d1076134a641b33efb035946536778336`。上游版权为 Copyright (c) 2026 Matt Pocock，采用 [MIT License](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/LICENSE)。本次用项目语言改写方法，未复制技能实现、脚本或完整正文。

| 来源 | 本仓采用与适配 |
| --- | --- |
| [to-tickets](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/to-tickets/SKILL.md) | 将可独立验收的切片与真正依赖写入现有计划。跨层迁移注明兼容过渡与最终验收点；不要求新票据文件、tracker 或逐票审批。 |
| [codebase-design](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/codebase-design/SKILL.md) | 检查接口是否减少调用方复杂度及封装是否承担实际职责。保留项目术语和有用适配层；不按接口数量裁定质量，不强制多方案子 Agent。 |
| [code-review](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/code-review/SKILL.md) | 保留规范与需求两维证据，按风险选择审查方式。修正只看三点 diff 到 HEAD 的范围限制；不强制两个 Agent 或 tracker。 |
| [diagnosing-bugs](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/diagnosing-bugs/SKILL.md) | 用原始症状、最小复现、可证伪假设与原场景复核约束修复。回归验证按风险选择；不强制 TDD、固定假设数、秒级循环或危险重放。 |

## 工作区审查的范围示例

先确定当前需求来源，可以是用户已确认的约束、项目目标、计划或指定 issue。记录适用规则及验收条件，避免用提交描述自行替代需求。

对包含工作区的交付，先记录当前 `HEAD`、被采用的基准提交和文件状态，再分别读取相关差异。以下是读取入口，`<base>` 必须替换成已核实的基准；不要求每次执行全部命令。

```bash
git rev-parse HEAD
git rev-parse <base>
git merge-base <base> HEAD
git status --short
git diff <base>...HEAD
git diff --cached
git diff
git ls-files --others --exclude-standard
```

三点 diff 只展示共同祖先到 `HEAD` 的已提交差异。`--cached` 展示索引相对 `HEAD`，无参数 diff 展示工作区相对索引；二者不能代替最终文件读回。未跟踪列表只提供路径，需逐项判断归属并读取属于交付的安全文本或检查对应产物。不得批量读取或提交凭据、会话状态和运行时日志。

若同一文件同时有暂存和未暂存修改，结合最终文件核对实际行为。忽略文件不在上述未跟踪列表内；只有明确属于本次交付的产物才按项目入口验证。记录未覆盖范围与原因，不把整个目录或未读材料声称为已审查。并行工作改变相关内容时，重查受影响的差异和验证结果；不要为冻结范围丢弃其他人的工作。

## 证据与版本边界

本轮只完成规范、模板和来源说明的同步。规范仍为 v1.1.0，已发布 v1.3.0 包不变。文档检查与既有 unittest 证明当前改动的相应范围，不证明上游技能已安装、所有下游仓库已同步，或这些方法在未来任务中已产生效果。验收与知识归属见[本轮进度](../plans/mattpocock-methods-20261019/progress.md)。
