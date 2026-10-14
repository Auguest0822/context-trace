# 记忆预期样例的用途

[`memories.sample.json`](memories.sample.json) 有 15 条**待用户确认的预期记忆**，五种 `kind` 各三条。它用于前端候选卡片、证据核对和后续检索评测的标准答案准备；它**不是**可以整份直接发送到 `POST /v1/memories` 的请求，也不是已落库的 `Memory` 响应。原始对话另存于 [`data/fixtures/`](../../data/fixtures/README.md)，归档对话时不得把本文件的候选自动保存为记忆。

每条记忆的 `fixture_key` 是测试用稳定标识。文档来源记录使用真实 `source_ref` 与文档中可逐字查到的 `source_excerpt`。聊天来源记录使用 `conversation_fixture` 和 `source_message_sequences` 定位原话；不写死数据库分配的 ID，也不在请求中伪造聊天 `source_ref`、`source_platform`。

验证聊天记忆的顺序：

1. 先导入两段对话，得到服务端返回的对话与消息 ID。
2. 在对应对话中按 `source_message_sequences` 选消息，并核对 `source_excerpt` 是所选消息的连续片段。
3. 预览候选；只有用户确认后才调用提交接口。后端用真实 ID 生成 `source_ref`，并从对话推导平台。
4. 读回 `Memory` 时再核对 `id`、`status`、`source_platform`、`conversation_id`、`source_message_ids` 和时间等服务端字段。

需要直接测试文档来源的 `POST /v1/memories` 时，使用 [`memory-write.doc.sample.json`](../../data/fixtures/memory-write.doc.sample.json)。如果将本文件用于网页 mock，应先按 API 契约转换成响应形状，不能把 `fixture_key` 或 `source_message_sequences` 当作实际接口字段。

静态出处检查运行 `python -m unittest discover -s python/tests -p test_fixture_contract.py -v`。抽取模型可能用不同措辞表达同一事实，因此本文件主要核对**用户确认后的内容、类别与证据关联**，不能要求模型在未确认前逐字生成全部 15 条。

[`search-cases.sample.json`](search-cases.sample.json) 另列六个问题和预期记忆 `fixture_key`：D5 可先验证关键词、平台过滤与 scope 隔离；D8 再验证混合检索的语义改写问题。执行前须将预期记忆经用户确认写入数据库，并记录 `fixture_key` 到真实记忆 ID 的映射。`expected_include`/`expected_exclude` 是验收断言，不是 HTTP 请求字段，也不规定其他候选的精确排名。
