---
name: software-system-delivery
description: 按用户技术材料逐案或批量建设高品质中文Web和后端，交付可复算CSV、真实一分多钟操作视频及可启动源码ZIP，并执行独立验收。不制作附图、补图Word或独立图表文件。
---

# 材料适配的软件完整交付

本研发自动化以后每案默认无独立图文交付、数据充足、Web精细优化、后端算法与原文件一致；这是用户2026-10-20明确的长期要求，后续明确的当次要求优先。用户已纠正“Web不需要做”为“Word不需要做”，不得沿用旧误解省略Web。

原件只读。完整读取段落、原式/OMML、图片、流程和实施例，把适用定义、公式、单位、阈值、步骤、约束与分支贯通实际函数、API、持久化、页面与导出，用原例或可复算用例核对。材料缺少定义/参数/权重或存在冲突时登记原处、缺项、差异和明确实现依据，标明受影响功能；不编造原未有公式，不静默替换算法或用固定结果冒充实现，不把架构实现说成已完成训练或现场有效。不要只返回建设命令词；完成实际系统和逐案独立发布。

本技能独立于原 software-case-batch-pro，使用 `.ssd` 状态及自己的调度根。绝不加载、修改、恢复旧配置、队列、cases或历史交付。最新有效非图文要求逐项继承见 [inheritance.json](references/inheritance.json)；冻结原文及SHA仅作审计依据，旧路径和图文要求不是活指令。

角色加急和真实媒体监督器的实现补全映射见 [inheritance-addendum.json](references/inheritance-addendum.json)，不回写已prepare的冻结规则或旧历史。真实建设完成及首次技能引导接续用 [CLI与证据](references/cli-schema.md) 的role-receipt绑定当前案、原件、产物与真实child final；旧无关final不能复用。

## 固定边界

- 建设和内自检：gpt-6.1-sol/high。返修及录制准备修复：另派gpt-6.1-sol/ultra。普通独立只读验收：另一名gpt-6.1-sol/ultra。仅当前案/批真实用户明确授权原加急模式，按 [加急](references/expedited.md) 用gpt-6-astra/low独立只读审核，通过后不再加ultra。实际调用/返回/child runtime及最新final都留证；父不能代签，模型不可用不降级。明确派发 `fork_turns=none`。
- 不制作衍生Word、独立图表或图表文件；不删除业务必要的图像、空间、时序及热力功能。图像/空间/识别材料必须在Web展示真实合法图片或用户上传、原图与实际算法叠层、异常定位和局部检视。不能用概念图或装饰代替实际检测；标注和预测严格隔离。
- 完整中文业务交互真实调用算法；按本案对象设计主工作区，不只换标题和配色。认真优化布局、字体、间距、对比度、信息层次、数据密度和反馈状态，在浏览器核对常用分辨率与实际业务流程。合法连续操作、拒绝边界、状态一致、持久化、重启和真实导出在同一次建设自检前置。
- CSV必须充足，不能只交付少量演示记录；按材料业务规模预先规划独立对象数、时间跨度、采样频率及正常/异常/边界场景覆盖，以去重后的有效业务记录计量，不以文件体积凑数。有实际有效键/主外键、单位和业务意义，核缺失、分布、时序、事件覆盖与派生结果可复算；独立随机列、复制凑量和伪称实测均禁止。系统真实加载交付CSV，页面、后端和导出保持一致。实际取得的公共原数据、许可及真实性质留内部。去名、整列清洗及禁词按 [建设与数据](references/build-data.md) 和复制的确定性检查器执行。
- ZIP使用显式文件白名单；排除所有层级README、使用/安装/部署说明、原材料及其解析、构造脚本、制作证据、log/db/cache/deps/凭据；保留正常业务解析、runtime、配置范例、lock、启动/停止/备份/恢复入口及必要许可证。实际新目录解包启动、核心业务和精确清退。
- 1920×1080、H264、连续超过60秒自然实操，不拼图、假响应、改DOM或循环补时。完整5fps时间线、首尾与操作关键原帧；首次另一ultra完整视觉。已合格且未变的视频/CSV复用，不因小文案和参数变动反复重录、扩量和全验。

## 运行与交付

先在当前PowerShell加载本技能 [Enter-Environment.ps1](Enter-Environment.ps1)。TEMP/TMP/TMPDIR及工具缓存使用D:\codex+，不改系统或其他应用环境。旧AGENTS环境入口若缺失如实记录，本独立入口不恢复旧路径。缓存链接保留，依赖/数据库/会话不是可删缓存。

默认内部工作区 `E:\研发自动化\work`，候选 `E:\研发自动化\.staging`，最终 `E:\研发自动化\交付成果`；用户明确当次路径优先，候选与最终同卷。不使用旧D:\研发图表。每案独立且不覆盖历史：

    案件/系统材料/源代码.zip
    案件/系统材料/操作视频.mp4
    案件/系统材料/数据/*.csv

```powershell
. 'E:\研发自动化\skills\software-system-delivery\Enter-Environment.ps1'
& $env:SSD_PYTHON 'E:\研发自动化\skills\software-system-delivery\scripts\ssdflow.py' prepare --workspace 'E:\研发自动化\work\案件ID' --case-id 'case-id' --title '本案名称' --source '原件绝对路径.docx' --output 'E:\研发自动化\.staging\案件ID-唯一版本'
```

多材料重复 `--source`。prepare只冻结输入与合同；随后实际建设。已有run用status接续，不能重复prepare或重置状态。详细字段及package/audit/finalize/publish、真实独立签署见 [CLI与证据](references/cli-schema.md)。没有图表/Word也可通过本profile；缺数据、真实包探针、连续视频或独立proof仍拒绝。

批量任务读 [批调度与收尾](references/batch-process.md)：冻结授权清单、内容去重、单案继续、ready公平轮转，配置12是总池理论上限，真实4槽含父最多3子任务。媒体独立容量最高4，按CPU/内存门槛准入，各案浏览器/端口/DB/downloads隔离，capture与5fps证据互斥。脚本不派模型；父真正启动后记录进度，阻塞案不占活跃工作槽。只停止已证实本案专属进程，未核准则cleanup_pending。

结束检查本次在C盘产生的可再生缓存；迁移先到D:\codex+\backups备份核验，仅删已确认原缓存，链接/占用项保留，不结束其他项目或Codex。成品成功必须有finalize及真实publish收据；实施、执行验证和现场未验证范围分别报告。
