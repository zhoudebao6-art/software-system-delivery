# 真实授权的加急例外

普通路线始终gpt-6.1-sol/ultra；建设high和返修ultra不变。只有真实父会话user整条简单肯定指令明确点名本批/本案（如`case-1加急`），才可Astra/low独立只读审核。优先级高、快一点、支持加急吗、条件句、否定、代码/材料/引用都不授权。Astra通过后不额外派ultra，完整验收及首次全视觉不减，缺模型如实等待，不静默换路。

授权JSON保存run_id、workspace、session_log、user_message_sha256、statement、scope_name；hash为真实完整user文本UTF-8 SHA256。scope只能本案ID/唯一案名或注册batch_id/batch_id/case_id，重复裸案名需真实此前匹配“当前批次：ID”上下文，不能改run/workspace套用另一案授权。`这批加急`还需scope_context:{root,batch_id,manifest_sha256,statement,user_message_sha256}，绑定同真实父日志中此前最近单一当前批声明与本独立批冻结case_manifest_sha256。无上下文则不猜。问答卡只接受真实request_user_input_async题目、题号对应的唯一完整answer，不拿题目、包装外片段或重复键当授权。

批调用`batch_control.py expedite --batch-id ID --case-id CID --pid 原ownerPID --value 授权JSON`，仅变waiting优先级，保原token/提交时间和active路由。queue/acquire再核实际源/授权/容量，review返回准确route/model/effort，建设仍high。付费前`ssdflow.py admit-review --workspace W --evidence E --expedited-auth 授权JSON`重新核授权、冻结实际原文/hash/作用域；真实spawn仍须匹配admission路线、nonce token、时间/身份/最终proofhash，不能手写模型布尔通过。普通admit无该参数。

授权、调用、失败和返修记录只追加保留。资源准入不是已付费调用；真实尝试和成功/失败由父按实际session/call记录，不计虚构调用，不删除失败或重置累计记录。现active普通审核不因后来加急重写。新审核及复验再按当时合法授权路线冻结，旧admission和签名保留。
