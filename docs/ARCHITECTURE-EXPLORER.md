# Architecture Explorer

Architecture Explorer 把 SpecMesh 已有的代码索引、关系图谱和项目演化记录变成面向人的静态页面。默认视图直接读取 Map v0 的节点和关系，按已有 global / focus 排名、预算与 area 门禁选择显示范围。没有手写架构 JSON 的仓库也可生成；已有业务模块与检查声明可以作为补充保留。

它不另建索引、图数据库、后台服务或前端构建工具。代码结构、审阅声明、检查结果分别保留来源，HTML 只负责展示。

这项工具随源码维护，不在已发布的 v1.3.0 独立运行时 ZIP 中，也不改变 SpecMesh v1.1 规范。

## 打开本仓的页面

在 GitHub 的 **Actions → Architecture Explorer** 中打开一次完成的运行，下载 `architecture-explorer-<commit>` 产物，解压并打开 `index.html`。`focus-map/index.html` 是同次构建的聚焦示例。页面内嵌显示数据，可直接离线打开。源码链接需要联网；私有项目仍需要相应仓库权限。

本地从 SpecMesh 源码根目录运行：

```bash
# 验证当前 Map 与可选业务声明；不执行检查，不生成文件。
python3 -B scripts/build_architecture.py --root . --check

# 构建静态页面；未运行的检查显示“未验证”。
python3 -B scripts/build_architecture.py --root .

# 执行已有业务声明中的检查，并比较两个修订的图谱。
python3 -B scripts/build_architecture.py \
  --root . --run-checks --base-ref HEAD^

# 同一来源的检查只运行一次；聚焦页面重用原有证据。
python3 -B scripts/build_architecture.py \
  --root . --focus "map source" --budget 1000 --base-ref HEAD^ \
  --results dist/architecture/status.json --output dist/architecture/focus-map

# 只显示原生 Map，不加载业务模型和其中的检查。
python3 -B scripts/build_architecture.py --root . --no-model --output dist/map-only
```

默认产物位于 `dist/architecture/`。双击其中的 `index.html` 即可使用。生成目录中的 `architecture.json` 是解析结果，`status.json` 是带来源绑定的检查证据；两者都可以重建，不回写项目声明。

## 页面展示什么

- **代码图谱**是默认入口，直接使用原生 `code://`、`mem://`、`spec://` 节点和关系。已有职责区域优先用于分组，其余按目录整理；目录分组只是阅读布局。展开分组、选择节点可查看完整身份、直接关系、权威来源与源码。
- **演化对比**展示明确基线与当前来源之间的节点、关系、区域和文件变化，并链接已有项目意图、决定与计划记录。没有可比较来源时直接解释原因，不显示伪造的“零变化”。
- 有业务模型时，还保留 **业务模块、模块清单与变更影响**，用于说明维护者声明的职责和检查结果。假设路径与实际 Git 变化分别显示。

图谱明确标出选中节点/关系数量、完整可见图数量与预算，并提供“Map 预算选择 / 查看完整关系”切换。Map 的文本预算优先容纳节点，可能未留下关系；此时初始页面明确采用完整 Map 分组图，保留选集提示，也可切回严格预算模式。“查找本页节点”只过滤当前显示范围，不在浏览器另做一套排名。需要另一任务视角时，用 `--focus` 重新构建；需要更宽选集时调整 `--budget`。详情和完整关系列表可查看预算之外的直接关系。分组与布局确定，不使用每次重排的力导向动画。

Map 当前提取文件与公开 Python 符号、可解析的 Python 导入和代码引用。其他文件可以作为文件节点出现；页面并不据此声称掌握完整的 TypeScript 调用、动态执行或业务依赖。

## 让另一个仓库使用

不需要先创建新文件。在目标仓库根目录运行已检出的 SpecMesh 构建器：

```bash
python3 ../specmesh/scripts/build_architecture.py --root . --check
python3 ../specmesh/scripts/build_architecture.py --root .
python3 ../specmesh/scripts/build_architecture.py --root . \
  --focus "task or module name" --base-ref HEAD^ --output dist/focus
```

默认尝试加载 `architecture/architecture.json`；该默认路径不存在时直接构建 Map。显式 `--model` 指定的文件不存在或内容无效时仍报错，避免静默丢掉本应生效的检查。`--no-model` 与 `--model` 互斥。没有模型时从真实 Git origin 推导项目名称与源码链接；没有 origin 则只显示目录名称，不编造地址。

需要补充业务职责或检查时，可以添加以下可选模型。文件和符号应替换为目标仓库真实路径，检查命令必须经过维护者审阅。

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

已有稳定职责区的项目可以在业务模块中填写 `area: "area:existing-id"`。构建器复用 `.specmesh/repo-areas.v0.yaml` 与 Map 的 current 门禁；没有已有 area 的项目无需为了页面新增一套职责标识。`mem://`、`spec://` 关系随原 Map 权威和作用域保留，不成为一份新的项目事实。

## 数据与修订如何对应

| 视图数据 | 现有依据 |
| --- | --- |
| `map.nodes` / `map.edges` | Map 的原生身份、关系、authority / provenance 与 scope；应用原有 area 门禁后保留完整可见图。 |
| `map.selection` | 与 Map 文本 global / focus 共用的选择结果，包括查询、预算、节点 ID 与关系键。 |
| `map.areas` | 原有 area 声明及锚点解析状态，不因目录分组生成新职责事实。 |
| `evolution` | 同一当前 Map 引擎读取基线 Git 对象与当前来源后的比较。 |
| `modules` / `relations` / `checks` | 可选的业务声明及实际检查记录，不替代原生图谱。 |

`--base-ref` 必须能在本地解析为提交。构建器通过只读 Git 对象读取，在临时目录恢复基线的参与文件，并用当前引擎解析；不切换工作区、不运行旧版本代码、不拉取缺失对象。当前来源可含明确标注的未提交变化。缺少历史对象或可比较的完整检出时，演化显示不可用；原生当前图仍可浏览。子模块内部文件不属于本仓 Map 的跟踪文件范围。

文件移动保留旧身份的删除和新身份的增加，旧链接固定基线提交，新链接固定当前提交。相同节点身份所在文件的内容变化标为 `source_sha256` 变化；对符号而言这只证明所属文件改变，不证明每个函数体都改了。节点与关系的演化比较针对完整可见图，调整 focus 或预算不会改变实际差异。

已有 `PROJECT.md`、`docs/DECISIONS.md` 与 `plans/` 等记录的变化会单列链接，供人核对意图和实现。它们是原记录的导航，不是从 Git diff 自动推导的动机解释，也不自动生成新决定。

## 什么可以变绿

| 页面状态 | 依据与处理 |
| --- | --- |
| 检查通过 `pass` | 当前绑定上，模块声明的所有检查均已执行并成功。只覆盖每条检查标明的范围。 |
| 检查失败 `fail` | 当前检查非零退出或超时；详情包含命令、时间和输出摘录。 |
| 未验证 `unknown` | 没有声明检查、没有运行、命令不可用或结果元数据不足。文件存在本身不会变绿。 |
| 证据过期 `stale` | 旧证据与当前修订、内容或构建定义不同，或者执行检查期间来源变化；需要重跑。 |
| 来源待确认 `blocked` | 路径或符号不存在、area 未 current 或关系依据失效；先审阅声明。 |

结果绑定实际读取的 Git HEAD、dirty 状态、Map 源文件内容指纹、可选架构模型、构建器、Map 实现和页面模板。未提交内容有独立指纹，页面明确标注工作区有变更；源码链接固定到 HEAD 基线，尚未进入该提交的新文件不生成虚假链接。没有 Git 的目录使用内容指纹，不编造修订。原生图谱节点本身没有“检查通过”状态。

旧路径不会凭文件名相似自动迁移。即使 Map 找到唯一的重定位候选，`candidate_rebind` 仍阻断该 area，须由维护者更新锚点后重新构建。失效关系不会参与下游影响传播。

Map 实际读取的配置、记忆和区域声明也必须位于目标仓库内，并参加同一来源指纹。构建器拒绝越界、绝对路径、符号链接逃逸、被忽略或位于生成目录中的这类输入，避免视图使用了未绑定的外部记忆。

可显式重用之前生成的证据：

```bash
python3 -B scripts/build_architecture.py \
  --root . --results dist/architecture/status.json
```

该命令不运行检查，重新核对来源绑定；不匹配时显示过期。`--focus`、`--budget` 和 `--base-ref` 只改变展示/比较，不改变检查范围或来源绑定，因此可以复用同源证据。结果文件是本地或受控 CI 的执行记录，不是签名证明，不应信任未知来源提供的成功 JSON。

默认构建允许未知状态，并以结构有效返回 0。`--run-checks` 或 `--results` 下，只要声明检查存在非 pass 状态就返回 1，仍生成页面用于定位问题。结构阻断返回 1；输入或构建错误返回 2。`--check` 与执行、结果回放互斥。

## 自动更新与权限

本仓工作流在 main 提交、PR 和手动触发时构建默认页面，执行一次声明检查，再用同源结果生成聚焦页面，并保存 Actions artifact。检查失败也尽量上传页面，同时保持工作流失败状态。页面是该次运行的快照；查看者应核对页头修订与构建时间。

接入仓库的工作流应固定 SpecMesh 的完整提交 SHA，与项目分开 checkout；需要演化对比时提供完整的目标仓库历史。只需要 Python 3.11+、Git 和可选模型中检查所需的现有工具；不用安装 Node 或下载前端包。检查是仓库代码执行，只在显式 `--run-checks` 下按 argv 调用，默认不执行。PR 工作流使用只读权限，不使用 `pull_request_target`。

公共仓库可以按自己的发布要求把同一静态目录交给 Pages 或现有站点。当前工作流只生成 artifact；私有仓库不自动公开架构、源码路径或检查日志。

## 维护边界

模块职责与业务关系需要人审阅；扫描文件不能证明全部架构关系。代码、实际检查和审阅声明分别保留来源，不把“历史上说过”“路径存在”或“纯参数测试通过”升级为当前生产验收。

变更影响是根据显式关系得到的复核候选范围，不证明下游一定出错，也不保证未列出的模块不受影响。未映射文件单独显示。外部渲染、真实服务和用户体验只有对应本次执行证据时才能通过。

生成物只能写到仓库的 `dist/`、`.specmesh/cache/` 子目录或新的外部目录；已有非空目录必须带本生成器标记。构建器拒绝覆盖源码、仓库根目录或符号链接输出。模型和已审阅的记忆不由生成器修改。
