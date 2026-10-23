# CLI与真实证据

先加载本技能Enter-Environment.ps1，全部命令用 `$env:SSD_PYTHON`。scripts/ssdflow.py支持：

| 命令 | 作用 |
|---|---|
| prepare --workspace W --case-id ID --title T --source S [--source S2] --output C | 一次冻结原件hash、软件profile及同卷候选；重复prepare拒绝 |
| status --workspace W | 只读接续run、完成与发布状态 |
| package --workspace W --manifest M | source_root相对W，files显式相对source_root白名单；打包并写.ssd/source-package.json |
| clean-data --workspace W --manifest M | M数组每项source相对W、name为CSV文件名；只删明确元数据整列，其他单元格值/顺序校验不变，不改原件或已完成副本 |
| audit --workspace W --evidence E --inputs-only | 审核前机械门禁；不声称独立通过 |
| admit-review --workspace W --evidence E | 机械通过后冻结唯一token/run/scope/snapshot，返回admission的path/sha256 |
| review-binding --workspace W --session-log P --call-id C | 只读计算实际独立派发绑定，不签pass |
| role-receipt --workspace W --role build/repair --session-log CHILD --outputs LIST --receipt evidence/唯一.json [--bootstrap] [--source-trace evidence/source-trace.json] | 子任务完成当前产物时创建不可变完成范围；由该子任务最新final真实签署 |
| audit --workspace W --evidence E | 验全部门禁及真实独立子会话final |
| finalize --workspace W --evidence E | 审核通过后冻结精确成品hash；不覆盖不同完成事实 |
| publish --workspace W --name 本案独立目录名 | 同卷原子发布，无历史覆盖，留真实收据 |

package的M为内部JSON：`{"source_root":"source","files":["backend/app.py","frontend/package.json","start.ps1","stop.ps1"]}`，按实际所有必要代码填写，列表不是固定模板。启动入口不能暗依赖旧工作区或被排除原材料。

统一E为内部JSON对象。每项引用格式为`{"path":"evidence/具体文件.json","sha256":"该文件实际SHA256"}`，全部路径相对W且在W内。必需键如下；脚本不编写业务结论：

- source_trace：`sources`包含所有原件path/sha256；`mappings`每项有source_location、definition、function、api、persistence、page、export、validation。可用字符串或具体路径数组；不适用须解释，不写空白。`conflicts`每项保source_locations/discrepancy/implementation_basis/limitation。源图片和公式也在同一映射中，不能只映射段落。
- data_plan：沿复制data_preflight约定的export_schema/known_names/allowed_terms/name_review/baseline_metrics/expansion_plan。逐列kind（id/number/timestamp/enum/text）、meaning，数字列unit（无量纲用1），ID正则、enum允许值、nullable及PK/effective_key/FK。主明细有效键含真实业务内容，不能只有行ID；维表声明table_role=dimension。自然主键显式primary_key_kind=natural。每CSV实际hash审阅，不能填模板hash。expansion_plan有generation_method和main_tables中target_effective_rows/required_events/适用adjustment_reason。
- provenance：nature准确性质，sources数组每项url/license/accessed_at/obtained。实际取得者附raw_file内证引用，未取得者restriction具体限制；validation保存范围/分布/缺失/时序/约束/派生完整复算证据，不能用泛泛true代替。
- execution：run_id与checks数组；algorithm/api/persistence/browser/export/lifecycle六类，每项kind/真实command/exit_code=0/具体summary/log引用。领域检查的真实输入和实现hash与日志同时保留。lifecycle包含启动→停止→端口释放及备份恢复的真实结果。
- cleanup：本技能process_guard.py实际生成.ssd/cleanup.json的引用，status=stopped，真实workspace且无remaining/ports_still_listening；不是父手写布尔声明。
- package_probe：本技能package_probe.py真实输出收据。命令 `scripts/package_probe.py run --workspace W --probe W\evidence\package_probe_case.py --receipt W\evidence\package-probe-唯一.json --timeout 180`。案件探针从环境SSD_PACKAGE_ROOT访问**实际解包目录**，SSD_PACKAGE_RESULT写真实结果；SSD_PACKAGE_RUN_ID绑定案。结果至少`{"core_flow":"实际核心业务链", "checks":[{"kind":"startup","name":"实际断言","passed":true},{"kind":"core_flow","name":"实际断言","passed":true}]}`。实际启动服务、算法、落库查询、导出与停止不得借旧服务。工具在执行任何案件指令前分配独立Windows Job、超时及退出精确清退。receipt/log/checker/probe/sourceZIP哈希内部保存。它不是OS安全沙箱，独立审核检查探针是否真实。
- recording：video_sha256、duration、continuous_capture=true、real_browser=true、edited=false、events。事件至少6步且至少3类action；每项action/started/completed/真实assertion、可选selector与业务对象。连续时轴自然阅读与输入，禁止静止补时；保实际录制输入、rAF/错误/下载日志和首末真实浏览器断言。
- timeline：复制_video_evidence_core.generate(video, internal_new_dir, sample_fps=5,min_seconds=60,max_seconds=None,tool_paths={ffmpeg,ffprobe},interaction_events=recording.events)实际生成timeline.json。它只出技术证据，不授视觉通过；自动black/freeze信号交ultra按业务判断。
- model_dispatch：build数组（一个或多个实际high建设子任务）、repair数组（实际发生才填）、review对象。每项parent_log/真实call_id/agent_id/child_log；build/repair还须completion:{path,sha256}，是当前run的真实角色完成收据。review另附admission:{path,sha256}。可用.ssd/model-dispatch.json路径方便review-binding读取。真实Codex sessions目录JSONL必须保留，不可抄到W假装真实日志；不改会话文件。
- review：另一ultra独立完成后写的JSON，格式见下。首次审阅需全视觉；后续未变且真实已阅证据可以继承明确旧proof及其真实final，工具仍核当前hash。不要伪造已阅声明。

首次录制期间每案独立Chromium/context/storage/download目录，不共享可写DB；原片编码H264 CRF20、输出1920×1080。录制/在线验证后精确关闭本案后台再清洗/打包。浏览器finally关闭，package_probe独立Job留真实退出事实。可复用业务录制器，但不得复用旧caseflow/批次状态，不为新技能回写旧工作区。

## 建设与返修实际完成绑定

完成角色在自己的真实child会话运行role-receipt。LIST是W内内部JSON数组，逐项填实际完成的当前文件相对路径；收据outputs记录每文件实际SHA256。收据contract=ssd-role-completion-v1，绑定run_id/workspace/sources/role/agent_id/child_session_id/parent_session_id/prepared_ns/completed_ns、输出范围，以及真实child在prepare之后操作本案的工具事件hash/时间。命令不证明领域验收，独立审核仍须读取实际代码、执行与输出。

命令stdout直接返回最终要签署的单JSON；child核实际范围后将该JSON作为自己的最新完整final，不能只在聊天里写“已完成”。例如：

```powershell
& $env:SSD_PYTHON 'E:\研发自动化\skills\software-system-delivery\scripts\ssdflow.py' role-receipt --workspace '当前W' --role build --session-log '自己的真实child.jsonl' --outputs 'W内输出清单JSON绝对路径' --receipt 'evidence/build-唯一-completion.json' --source-trace 'evidence/source-trace.json' --bootstrap
```

--bootstrap仅在真实先spawn后prepare时显式使用；没有历史前置admission可补，也无需捏造。审核派发不接受此例外。

child必须实际读取原件路径/hash；若按共享抽取结果建设，先用自己的工具读取绑定run.sources的source-trace.json，命令带--source-trace。收据保存当时trace不可变副本与原实际读取路径，后续映射修正不会改写旧事实。每个收据独占新路径；完成范围有变化时生成新收据，不能改旧完成记录。相同文件由后续真实返修覆盖时，最终门禁按完成时序核最新角色所签当前hash。

该child最新完整final须为单JSON（允许标准尾部memory citation），父不能代写：

```json
{"agent_id":"/root/实际建设者","role_completion":{"path":"evidence/唯一-completion.json","sha256":"实际收据hash"}}
```

技能首次引导建设可以早于prepare启动。此时显式--bootstrap允许沿真实原spawn接续，不伪造提前admission：收据必须绑定后来真实prepare的当前run/原件/工作区、prepare后仍持续的工具操作、实际当前输出和完成时间，最新final须在prepare后签署。独立审核核这些真实日志与业务范围。与本案无关的旧技能建设final、旧已完成案、在prepare前已结束的任务均不满足；公共技能建设者不能冒充本案业务建设者。既有合法run无需重prepare或修改冻结合同，只增加这些实际新完成证据。普通建设spawn可在prepare后，仍必须实际完成绑定。

批release另外要求真实spawn在原acquire之后、父等于原group，且一个parent/call只可消费一次。bootstrap不能补造历史queue准入；未登记批的真实建设可按本案完成证据验收。review始终须先admit-review再实际spawn，不能走bootstrap。

首次完整CSV质量/扩量/清洗通过会创建.ssd/data-completion.json及不可变原计划/出处/清洗事实副本。后续门禁只核同成员和字节hash、原pass事实与副本完整性，不重新逐行扫描，也不拿新算法计划改写旧数据完成事实。成品CSV字节或成员变化会阻挡并保留原事实；明确数据错误需显式建立修订及定向复验，不能删除原pass收据暗中全重做。

发布先写.ssd/publish-intent.json，固定run/候选/目标/成品hash/finalizehash。rename后收据中断时，同原publish命令核目标与原意图逐字节一致后补写publish.json；同一目标重复接续幂等，不覆盖不同内容或改名换目标。此恢复只补已核验过的原发布事实，不重新签领域或独立pass。

## 另一ultra如何签署

先inputs-only，再admit-review。父实际spawn另一名gpt-6.1-sol/ultra、fork_turns=none；明文派发要写返回token、run_id和W。桌面gAAAA信封不可读时，只接受真实调用/返回hash、先于派发的admission、同时间窗创建且真实父子绑定的child及其签署；工具不宣称解密或验证信封MAC。

派发后填model_dispatch.review并运行review-binding，独立审核者读取实际绑定。proof至少：run_id、reviewer_agent_id、decision（pass/revise）、精确candidate snapshot（相对文件→SHA256）、review_dispatch_binding、reviews数组。reviews包含source_fidelity/algorithm/api/persistence/browser/export/data/source_package/video/lifecycle，每项kind/decision/evidence（实际发现及证据）。video_visual含decision及viewed数组，数组精确包含全部contact_sheets、全部interaction_frames、first/last的file/sha256；审核者用图片查看工具真实看完，必要查看全尺寸5fps帧。无损主体的小瑕疵只建议，不强制返修。

审核者最新完整final必须是单个JSON（可带尾部标准memory citation）：

```json
{"reviewer_agent_id":"真实/root/独立审核者", "review_evidence_sha256":"该review JSON实际hash", "review_dispatch_binding":{"contract":"ssd-independent-ultra-v1","token":"...","run_id":"...","workspace":"...","parent_session_id":"...","call_id":"...","dispatch_message_sha256":"...","dispatch_event_sha256":"..."}}
```

父记录引用后audit/finalize/publish。父总结、手写runtime/model声明、其他child的final、旧review、被改proof、缺少首次视觉和降级模型都不能通过。若判revise，另派ultra修复后只复验未通过/未读/受影响项，保留未变CSV与视频及首次实际已阅事实；新admission绑定当前差异，不改旧票据和通过记录。

已合格视频不重阅时，video_visual可用`{"decision":"pass","inherited_review":{"proof":{"path":"旧proof相对路径","sha256":"旧proof实际hash"},"dispatch":旧model_dispatch.review完整对象}}`。门禁沿真实旧ultra派发及其实际final核旧proof签署、同视频hash及首次全视觉覆盖，拒绝循环与自造继承，不把旧审核证明新算法。首次未审视频不能走继承。
