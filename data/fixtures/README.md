# 可复现的虚构样例

这里的 JSON 都是**人工编写的模拟内容**，不代表真实 AI 平台的完整聊天历史，也不包含私人对话。两段原始对话共 12 条消息，满足 D1 要求的“两段对话、两个平台、10–20 条消息”：

| 文件 | 平台 | 消息数 | 主题 |
| --- | --- | ---: | --- |
| `conversation-import.sample.json` | DeepSeek | 4 | 初赛部署和原始对话归档 |
| `conversation-import.kimi.sample.json` | Kimi | 8 | 记忆检索、用户勾选和召回解释 |

这两个文件均符合 `POST /v1/conversations` 输入格式：`capture_method=manual_import`、`capture_completeness=selected`、`source_url=null`。每个文件有自己的固定 `client_request_id`，原样重试应返回首次结果且不重复写入；若修改正文，请同时换一个 UUID。因为手动模拟数据没有平台提供的真实会话/消息 ID，`external_conversation_id` 和 `external_message_id` 都为 `null`，不要伪造浏览器 URL。

从仓库根目录导入：

```powershell
python -m yanji.store.import_fixture data/fixtures/conversation-import.sample.json --prompt-password
python -m yanji.store.import_fixture data/fixtures/conversation-import.kimi.sample.json --prompt-password
```

归档只生成 `Conversation` 和 `Message`，**不自动写入 `Memory`**。记忆候选及其预期证据在 [`docs/samples/memories.sample.json`](../../docs/samples/memories.sample.json)。聊天候选使用“对话样例路径 + 消息 sequence”定位；真正调用记忆写入接口时，先取得数据库返回的 `conversation_id` 和 `message_id`，由后端推导 `source_ref` 与 `source_platform`。`sequence` 不是消息主键。

[`memory-write.doc.sample.json`](memory-write.doc.sample.json) 是一条可直接用作 `POST /v1/memories` 请求的**文档来源**记忆样例；其出处片段能在文档原文中逐字找到。记忆业务接口完成后再执行该请求。

运行静态校验，无需连接数据库：

```powershell
python -m unittest discover -s python/tests -p test_fixture_contract.py -v
```

真实私人聊天、API Key 和 Cookie 不提交仓库。完整字段规则以 [`docs/api-data-contract.md`](../../docs/api-data-contract.md) 为准。
