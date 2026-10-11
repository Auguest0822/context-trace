# D1 样例数据说明

`conversation-import.sample.json` 是一段**虚构的 AI 聊天记录**，结构对应 `POST /v1/conversations` 的请求。四条消息按 `sequence` 排序：用户提问/陈述、AI 回答，再一轮用户陈述、AI 回答。它不是项目真实聊天，也不是已经存入 seekdb 的数据。`manual_import` 表示手动导入的演示内容；`source_url: null` 表示没有真实网页链接，不要给模拟数据编造可点击的来源地址。

**原始对话与提炼后的记忆是两类数据。** 归档上述 JSON 只应生成 `Conversation` 和四条 `Message`，不应自动生成 `Memory`。用户之后选择消息、预览并确认，才可能保存例如以下两条记忆：

| 候选记忆 | 类别 | 可核查出处 |
| --- | --- | --- |
| 初赛以仓库可复现为优先，腾讯云服务器仅用于团队联调。 | `decision` | 本样例第 1 条 `user` 消息中的原文；落库后使用服务端分配的消息 ID |
| 对话归档和记忆提炼分开，用户确认后才保存记忆。 | `constraint` | 本样例第 3 条 `user` 消息中的原文；落库后使用服务端分配的消息 ID |

不要把 AI 的建议直接当成用户已作出的决定。例如第 2 条回答是建议，不能单凭它生成“团队已经完成 README”的记忆。用户也可以不选择任何候选记忆，此时原始对话仍可查看。

前端 B 的 D1 交付可以沿用此格式扩充到 **10–20 条原始消息**，覆盖至少两段对话和两个来源平台，并为其中值得提炼的内容写出预期候选记忆及消息序号。D2 用同一份原始消息生成输入 mock；前端 A 可据此构造列表和详情 mock。真正联调时，以 `docs/api-data-contract.md` 为准，使用后端返回的 `conversation_id`、`message_id` 建立出处关联，不要把 `sequence` 当作数据库 ID。

文件约定：可导入或可供 mock 的 JSON 放在 `data/fixtures/`；样例含义写在本文件；接口字段和流程规则放在 `docs/api-data-contract.md` 与 `docs/project-workflow.md`。真实私人聊天、API Key 和 Cookie 不提交仓库。
