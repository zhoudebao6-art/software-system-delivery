# 批调度与安全收尾

新的所有批共用 `E:\研发自动化\work\.ssd-control`，绝不使用原cases/.batches或原batch_control。scripts/batch_control.py只维护独立授权清单与ready/active/blocked/delivered事实，不派模型、不签验收。register的清单为数组，每案含case_id/workspace/source（原件绝对路径），授权引用作为字符串保留；源hash内容去重，重复不再次制作。已有批status接续；单案blocked记录具体原因及解除条件，不阻塞其他ready；已published按真实收据标delivered，不能将候选算完成。

长期父按真实运行时声明和全局理论池最多12准入；目前平台4总槽含父，实际最多3子任务。不能因登记新批或改容量获得多余真实模型槽。build/repair/review三路按最近成功准入轮转、同路FIFO与300秒公平老化；不固定组/阶段配额、不抢停active，失去owner的active需核身份恢复，不能因父退出就当子孙已停。所有当前批同root，禁止绕root扩容。真实spawn成功后记录agent/call；等待模型/媒体不占建设位，正常运行不催办、不忙轮询。

独立media槽最多4、evidence单槽。capture开始前按可用physical/commit较小余量至少首路4096MB、额外每路2048MB，每路4逻辑CPU且保留2、实际CPU≤85%检查；不够等待，不停别项目。每案独立应用/DB/监听端口/浏览器/context/storage/downloads，capture与evidence互斥，queued evidence优先排空但不撤销active capture。每个捕获/编码进程由本次唯一Windows Job或等效持有句柄的监督器管理，在执行前Assign；记录器finally精确关闭拥有的浏览器，父退出不能凭空释放媒体槽。批控制器的lease只证明准入，不证明Job隔离；media_job.Job/launch_suspended供实际监督器使用。没有真正Job和运行归属时保持cleanup_pending，不能只填receipt称安全。

实际启动使用 `job_runner.py --workspace W --batch-id ID --token 已active媒体token --owner-pid 原长期父PID --receipt evidence/media-唯一.json --timeout 合理独立超时 -- 真正解释器 真正录制器及参数`。工具先创建suspended进程、Assign独占Job、绑定真实PID/Job后才resume，结束/超时/中断关闭本Job，确认无成员后释放原媒体token。超时只是保护，不是成片固定时长上限；失败收据和原片保留。不得只手写runtime绑定或忽略Job失败。单案如未登记批，可由本案专属受控录制器持同等Job和finally归属证据；批中媒体必须走原票监督器。

批命令顺序为register（--cases授权清单JSON、--authorization真实请求引用、--parent-log真实父JSONL、--pid长期父PID）→queue --case-id CID --stage build/repair/review/capture/evidence→acquire --token返回token。未取得时看selected推进真正owner的ready案，不代领。模型release的--value为实际{parent_log,call_id,agent_id,child_log}完成记录；建设/返修另含completion:{path,sha256}，审核另含admission:{path,sha256}。工具核当前run/角色完成、真实子会话最新final、派发在原acquire后及同parent/call一次性消费；媒体由job_runner真退出释放。block的--value须reason/resume_when，resume只恢复明确blocked案。complete从当前真实publish收据核成品hash。recover-owner只允许原owner确已退出、真实新父日志及reason；active归属未知保留，不偷票不靠失联自动释放。普通/加急按[加急](expedited.md)保scope与路由，失败调用、票据及收据保留。

服务实际启动前保Popen/PID、创建时间、绝对entry/工作区命令行和监听端口，脚本路径从当前部署目录解析，不含旧工作区硬编码。Windows Start-Process必须隐藏；CIM/JSON子进程输出明确UTF-8，Python strict解码并核returncode。`scripts/process_guard.py register --workspace W --pid P`登记真实调用本案绝对脚本入口的专属服务；仅argv含工作区、-c/-e/读文件/搜索命令拒绝。登记捕获真实父链子孙，清退时保有精确根与子孙句柄、先停父再收尽晚生子孙；无法证明或受保护的成员保留cleanup_pending。未知入口须先使用独立Job监督器，不以路径字符串猜归属；录制、在线验证完成且没有在途有效任务后 `stop --workspace W`，按创建时间/command/tree/port保有句柄精确结束。不按node/python名称杀进程；保Codex/MCP/用户浏览器/共享/其他项目。拒绝与占用如实cleanup_pending，不绕过。新ZIP探针有自己独立Job及收尾，不用原服务成功冒充。

每案publish后独立交付；批次完成须所有非重复授权案均有真实发布收据，失败逐案报原因。原周F盘归档属于旧技能历史策略，本技能不擅自搬迁新E盘交付；只有用户另明确要求才复制/核验/归档，活跃案不移动。
