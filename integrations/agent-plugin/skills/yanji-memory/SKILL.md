# 言迹记忆 Skill

## 何时写入记忆
- 出现明确结论、决策、约束、踩坑经验时 -> 调用 memory_write
- 必须携带 source_ref（出处），没有出处的信息不得写入

## 何时读取记忆
- 开始新任务前 -> 调用 memory_search 取回相关记忆
- 接手他人工作时 -> 调用 memory_handoff 生成交接清单

## 冲突处理
- 新信息与旧记忆矛盾时 -> 调用 memory_reconcile，不要直接覆盖

## 隐私
- 用户要求删除时 -> 调用 memory_forget
