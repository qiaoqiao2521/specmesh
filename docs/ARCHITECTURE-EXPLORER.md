# Architecture Explorer

Architecture Explorer 是 SpecMesh 面向人的可选入口。打开一张静态页面即可看模块职责、定位源码、检查证据，并判断一处变更可能影响哪些下游模块。它复用 Map v0 的当前文件、`code://` 符号和已有 `area` 门禁，不需要新的索引、图数据库、服务或前端构建工具。

这项工具随源码维护，不在已发布的 v1.3.0 独立运行时 ZIP 中，也不改变 SpecMesh v1.1 规范。

## 打开本仓的页面

在 GitHub 的 **Actions → Architecture Explorer** 中打开一次完成的运行，下载 `architecture-explorer-<commit>` 产物，解压并打开 `index.html`。页面内嵌完整显示数据，可直接离线打开。源码链接需要联网；私有项目仍需要相应仓库权限。

本地从 SpecMesh 源码根目录运行：

```bash
# 只验证模型、路径和已有 area；不执行检查，不生成文件。
python3 -B scripts/build_architecture.py --root . --check

# 构建静态页面；未运行的检查显示“未验证”。
python3 -B scripts/build_architecture.py --root .

# 执行声明中的检查，并显示相对指定修订的真实文件变化。
python3 -B scripts/build_architecture.py \
  --root . --run-checks --base-ref HEAD^
```

默认产物位于 `dist/architecture/`。双击其中的 `index.html` 即可使用。生成目录中的 `architecture.json` 是解析结果，`status.json` 是带来源绑定的检查证据；两者都可以重建，不回写项目声明。

## 三个视图

- **架构总览**：按稳定层级和顺序显示模块，点击模块看职责、源码、上下游和检查记录。
- **模块清单**：按名称、职责或路径搜索，按通过、失败、未验证、过期、来源失效筛选。
- **变更影响**：查看 Git 相对 `--base-ref` 观察到的变化，或输入假设路径查看候选下游。假设与真实变化分别显示，没有比较基线时明确显示不可用。

位置由声明的 `layer` 和 `order` 决定，普通构建不会重新计算力导向布局。视图链接保存选中的模块和页签；影响页的假设路径也可以随链接保留。

## 让另一个仓库使用

在目标仓库维护一份 `architecture/architecture.json`，在该仓库根目录运行已检出的 SpecMesh 构建器：

```bash
python3 ../specmesh/scripts/build_architecture.py --root . --check
python3 ../specmesh/scripts/build_architecture.py --root . --run-checks
```

输入模型的最小结构如下。文件和符号需要替换为目标仓库的真实路径，检查命令必须经过维护者审阅。

```json
{
  "schema": "specmesh-architecture-v1",
  "project": {
    "id": "owner/repository",
    "title": "Project",
    "subtitle": "给维护者的一句话说明",
    "repository_url": "https://github.com/owner/repository"
  },
  "layers": [{"id": "core", "label": "核心能力"}],
  "modules": [{
    "id": "parser",
    "title": "输入解析",
    "summary": "检查输入并生成供后续执行使用的数据。",
    "layer": "core",
    "order": 0,
    "paths": ["src/parser.py"],
    "anchors": ["code://src/parser.py#parse"],
    "checks": ["parser-tests"]
  }],
  "relations": [],
  "checks": [{
    "id": "parser-tests",
    "label": "解析边界单元测试",
    "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
    "timeout_seconds": 60
  }]
}
```

关系声明使用 `from`（上游）、`to`（下游）、`kind`、`label`、`authority: "asserted"` 和 `evidence` 路径数组。影响沿这个方向传播；它表达维护者审阅后的业务关系，扫描器只核对端点和依据是否仍然存在。

已有稳定职责区的项目可以在模块中填写 `area: "area:existing-id"`。构建器复用 `.specmesh/repo-areas.v0.yaml` 与 Map 的 current 门禁；没有已有 area 的项目无需为了页面新增一套职责标识。`mem://`、`spec://` 关系随原 Map 权威和作用域保留在派生数据中，不成为一份新的项目事实。

## 什么可以变绿

| 页面状态 | 依据与处理 |
| --- | --- |
| 检查通过 `pass` | 当前绑定上，模块声明的所有检查均已执行并成功。只覆盖每条检查标明的范围。 |
| 检查失败 `fail` | 当前检查非零退出或超时；详情包含命令、时间和输出摘录。 |
| 未验证 `unknown` | 没有声明检查、没有运行、命令不可用或结果元数据不足。文件存在本身不会变绿。 |
| 证据过期 `stale` | 旧证据与当前修订、内容或构建定义不同，或者执行检查期间来源变化；需要重跑。 |
| 来源待确认 `blocked` | 路径或符号不存在、area 未 current 或关系依据失效；先审阅声明。 |

结果绑定实际读取的 Git HEAD、dirty 状态、Map 源文件内容指纹、架构模型、构建器、Map 实现和页面模板。未提交内容有独立指纹，页面明确标注工作区有变更；源码链接固定到 HEAD 基线，尚未进入该提交的新文件不生成虚假链接。没有 Git 的目录使用内容指纹，不编造修订。

旧路径不会凭文件名相似自动迁移。即使 Map 找到唯一的重定位候选，`candidate_rebind` 仍阻断该 area，须由维护者更新锚点后重新构建。失效关系不会参与下游影响传播。

Map 实际读取的配置、记忆和区域声明也必须位于目标仓库内，并参加同一来源指纹。构建器拒绝越界、绝对路径、符号链接逃逸、被忽略或位于生成目录中的这类输入，避免视图使用了未绑定的外部记忆。

可显式重用之前生成的证据：

```bash
python3 -B scripts/build_architecture.py \
  --root . --results dist/architecture/status.json
```

该命令不运行检查，重新核对来源绑定；不匹配时显示过期。结果文件是本地或受控 CI 的执行记录，不是签名证明，不应信任未知来源提供的成功 JSON。

默认构建允许未知状态，并以结构有效返回 0。`--run-checks` 或 `--results` 下，只要声明检查存在非 pass 状态就返回 1，仍生成页面用于定位问题。结构阻断返回 1；输入或构建错误返回 2。`--check` 与执行、结果回放互斥。

## 自动更新与权限

本仓工作流在 main 提交、PR 和手动触发时构建页面，并保存 Actions artifact。检查失败也尽量上传页面，同时保持工作流失败状态。页面是该次运行的快照；查看者应核对页头修订与构建时间。

接入仓库的工作流应固定 SpecMesh 的完整提交 SHA，与项目分开 checkout。只需要 Python 3.11+、Git 和模型中检查所需的现有工具；不用安装 Node 或下载前端包。检查是仓库代码执行，只在显式 `--run-checks` 下按 argv 调用，默认不执行。PR 工作流使用只读权限，不使用 `pull_request_target`。

公共仓库可以按自己的发布要求把同一静态目录交给 Pages 或现有站点。当前工作流只生成 artifact；私有仓库不自动公开架构、源码路径或检查日志。

## 维护边界

模块职责与业务关系需要人审阅；扫描文件不能证明全部架构关系。代码、实际检查和审阅声明分别保留来源，不把“历史上说过”“路径存在”或“纯参数测试通过”升级为当前生产验收。

变更影响是根据显式关系得到的复核候选范围，不证明下游一定出错，也不保证未列出的模块不受影响。未映射文件单独显示。外部渲染、真实服务和用户体验只有对应本次执行证据时才能通过。

生成物只能写到仓库的 `dist/`、`.specmesh/cache/` 子目录或新的外部目录；已有非空目录必须带本生成器标记。构建器拒绝覆盖源码、仓库根目录或符号链接输出。模型和已审阅的记忆不由生成器修改。
