# 言迹 ContextTrace：按功能分类的 API 与数据契约

> 状态：**拟定，待人工审查**。本文固定前后端、浏览器扩展、Agent Plugin、Python 引擎之间的接口。当前仓库中的 `models.py`、`api.py`、`mcp_server.py` 尚未实现，本文描述目标行为，不代表这些接口已经可用。
>
> 范围：两周版本优先交付网页 + MCP；浏览器扩展在这条闭环通过验收后开发。扩展所需的归档字段先保留在契约中，但扩展本身不属于两周必做验收。HTTP 路径统一以 `/v1` 开头；MCP 工具复用同一业务逻辑。整体用户流程见 `project-workflow.md`。若修改字段或语义，先修订本文和示例，再让各端联调。

## 1. 系统边界与术语

```text
手动导入 / Web 控制台 ── HTTP JSON ─────┐
                                      ├─ Python 业务服务 ── seekdb
Agent 宿主 ── MCP 工具/宿主适配 ────────┘

后续浏览器扩展也调用上述 HTTP 归档与检索接口。
```

- **对话**：由用户确认归档的一组消息，记录来源平台和采集完整度；不等同于记忆。
- **消息**：对话中的一条原始发言，保留角色、顺序、正文和平台原始 ID（若可取得）。
- **候选记忆**：从用户选中的消息提炼、尚未确认保存的结果。
- **记忆**：可独立检索的决策、约束、事实、偏好或经验，必须带可定位的出处。
- **来源**：原始对话、文档、Git 提交等。`source_ref` 是定位标识，不等同于摘要。
- **scope**：业务隔离键，如 `project:context-trace`。同一请求只操作一个 scope。
- **检索轨迹**：实际候选、排名、预算取舍形成的记录，控制台据此解释结果。
- **Token 预算**：仅约束返回给 Agent 的 `context_text`；不含用户问题、系统提示词、模型回答。

### 给队员看的通俗解释

| 文档术语 | 直接理解为 | 用户在网页上看到的动作 |
| --- | --- | --- |
| 归档对话 | 把用户选中的聊天原文保存下来 | “保存这段对话” |
| 提炼记忆 | 从选中的消息中找出值得以后再用的结论 | “提取记忆”→预览→“确认保存” |
| 记忆 | 一条已确认、可检索、能指回原文的结论 | 记忆库中的一张记录卡 |
| scope | 当前项目或个人的资料范围 | 顶部“当前项目”选择框 |
| 检索 | 用问题找回相关记忆 | 输入问题并点击“查找记忆” |
| 上下文 | 实际准备交给 AI 的记忆文字 | “最终使用的内容”预览框 |
| 检索轨迹 | 系统为什么选中或舍弃某条记忆的运行记录 | “查看召回依据” |
| 版本替换 / reconcile | 用新结论取代旧结论，保留旧记录 | “更新这条决定” |
| 交接 / handoff | 按接手任务整理已有记忆 | “生成交接摘要” |

**最关键的区别**：对话原文是档案，记忆是从档案中提炼并经用户确认的结论。保存对话、预览候选、确认记忆、查找记忆是四个独立操作；网页不能把其中任何一步假装已完成。

首版服务面向团队可信用户。`scope` 是数据过滤字段，**不是身份认证机制**。公网部署必须在服务前配置认证与访问控制，不能因为传了某个 scope 就授权访问。浏览器只归档获授权网页上实际可取得且经用户确认的消息；MCP/Skill 不自动提供 Agent 的完整历史对话。

## 2. 通用约定

| 项目 | 契约 |
| --- | --- |
| 编码 | UTF-8；HTTP 请求与响应为 `application/json`，健康检查除外 |
| 标识符 | 数据库主键使用 `BIGINT`，API 中统一传**十进制字符串**，避免 JavaScript 数字精度丢失；预览和轨迹 ID 为 UUID 字符串 |
| 时间 | UTC、ISO 8601 格式，例如 `2026-10-11T08:30:00Z`；服务端生成 `created_at`、`updated_at` |
| 分页 | 列表使用 `limit` 与不透明 `next_cursor`；无下一页为 `null` |
| 未知字段 | 请求拒绝未知字段，返回 `VALIDATION_ERROR`，避免拼写错误被静默忽略 |
| 空值 | 可选字段可省略；明确允许为 `null` 的字段才可传 `null` |
| 幂等 | 写入请求可传 `client_request_id`（UUID）；同一 scope、同一 ID、同一请求体重试返回首次结果，不重复写入；请求体不同返回 `IDEMPOTENCY_CONFLICT` |
| 数据库版本 | 团队固定 seekdb 镜像 tag/版本；SQL 以该版本实测通过为验收标准 |

HTTP 成功返回业务 JSON，错误统一为：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "source_ref is required",
    "details": {"field": "source_ref"},
    "request_id": "8e099c4e-1234-4f17-a8ab-111111111111"
  }
}
```

| HTTP 状态 | 代码 | 含义 |
| --- | --- | --- |
| 400 | `VALIDATION_ERROR` | 字段缺失、范围或格式不合法 |
| 401/403 | `UNAUTHORIZED` / `FORBIDDEN` | 开启认证后凭据无效或无权访问 |
| 404 | `NOT_FOUND` | 指定 scope 中无此对话、消息、记忆或轨迹；不泄露其他 scope 是否存在 |
| 409 | `IDEMPOTENCY_CONFLICT` / `STATE_CONFLICT` | 幂等键冲突或版本状态冲突 |
| 410 | `PREVIEW_EXPIRED` | 候选提炼预览已过期，需重新生成 |
| 422 | `EMBEDDING_UNAVAILABLE` / `EXTRACTION_UNAVAILABLE` | 所需 embedding 或抽取服务不可用 |
| 503 | `STORE_UNAVAILABLE` | seekdb 不可用 |

服务日志记录 `request_id`、耗时和错误代码；默认不记录记忆正文、完整对话、API Key 或 embedding。

## 3. 数据模型

### 3.1 `Conversation` 与 `Message`：原始档案

`Conversation` 对外表示：

```json
{
  "id": "201",
  "scope": "project:context-trace",
  "platform": "deepseek",
  "external_conversation_id": "conv-abc",
  "title": "讨论初赛部署方式",
  "source_url": "https://chat.deepseek.com/a/chat/s/conv-abc",
  "capture_method": "browser_extension",
  "capture_completeness": "selected",
  "message_count": 2,
  "memory_count": 0,
  "captured_at": "2026-10-11T08:20:00Z",
  "created_at": "2026-10-11T08:20:00Z",
  "updated_at": "2026-10-11T08:20:00Z"
}
```

`Message` 对外表示：

```json
{
  "id": "301",
  "conversation_id": "201",
  "scope": "project:context-trace",
  "external_message_id": "msg-42",
  "sequence": 42,
  "role": "user",
  "content": "初赛要以仓库可复现为优先。",
  "sent_at": null,
  "captured_at": "2026-10-11T08:20:00Z"
}
```

| 字段 | 类型与约束 | 语义 |
| --- | --- | --- |
| `platform` | `deepseek`、`kimi`、`doubao`、`agent`、`other` | 对话发生的平台；`agent` 可在来源详情补充宿主名称 |
| `external_conversation_id` | 字符串或 `null` | 平台可取得的会话 ID，不假设每站都提供 |
| `title` | 非空字符串，最长 256 字符 | 用户可编辑的归档标题 |
| `source_url` | `http(s)` URL 或 `null` | 可回到原始会话的地址；不能保证他人可访问 |
| `capture_method` | `browser_extension`、`agent_export`、`manual_import` | 消息如何进入系统 |
| `capture_completeness` | `selected`、`visible_page` | 用户只选了部分消息，或确认保存当前页面可见消息；不宣称包含平台全部历史 |
| `message_count` / `memory_count` | 非负整数；服务端生成 | 对话中已归档消息数、已确认记忆数 |
| `role` | `user`、`assistant`、`system`、`tool` | 原始消息角色；无法判定时拒绝自动归档并提示用户修正 |
| `sequence` | 非负整数；同一对话内唯一 | 页面或导出中的消息顺序；允许不连续 |
| `content` | 非空字符串，最长 50,000 字符 | 归档时用户确认的消息文本；首版不归档附件和隐藏推理内容 |
| `external_message_id` | 字符串或 `null` | 可取得时用于增量导入去重；否则按 `sequence` 与正文哈希识别重复 |
| `sent_at` | UTC 时间或 `null` | 平台提供的发送时间；不可取得时保持 `null`，不伪造 |

`id`、`scope`、`created_at`、`updated_at`、`captured_at` 由服务端生成或规范化。**原始消息与提炼后的记忆分别存储**；归档请求不触发记忆自动写入。若平台仅暴露一部分页面内容，不能把未采集内容标为已保存。

### 3.2 `Memory`：对外表示

```json
{
  "id": "101",
  "scope": "project:context-trace",
  "kind": "decision",
  "content": "初赛演示优先保证本地可复现。",
  "summary": "初赛演示需本地可复现。",
  "importance": 0.8,
  "status": "active",
  "superseded_by": null,
  "source_type": "doc",
  "source_ref": "docs/deployment-and-evaluation.md#一、结论",
  "source_excerpt": "初赛自动评测以仓库中的代码、配置说明……为准",
  "source_platform": null,
  "conversation_id": null,
  "source_message_ids": [],
  "valid_from": null,
  "valid_to": null,
  "created_at": "2026-10-11T08:30:00Z",
  "updated_at": "2026-10-11T08:30:00Z"
}
```

| 字段 | 类型与约束 | 语义 |
| --- | --- | --- |
| `id` | 十进制字符串；服务端生成 | 记忆主键 |
| `scope` | 字符串，1–128 字符；必填 | 项目、团队或个人的隔离键；首版不做跨 scope 检索 |
| `kind` | `decision`、`constraint`、`fact`、`preference`、`skill`；必填 | 记忆类别 |
| `content` | 非空字符串，最长 8,000 字符；必填 | 可检索的记忆正文；一条只表达一个可核查的信息点 |
| `summary` | 字符串或 `null`，最长 512 字符 | 预算压缩用摘要；不得加入正文没有的事实 |
| `importance` | 0–1，默认 0.5 | 排序/预算参考值，不覆盖相关性与状态过滤 |
| `status` | `active`、`superseded`、`expired` | 活跃、被替代、过期；默认检索只返回 `active` |
| `superseded_by` | ID 或 `null` | 指向替代它的新记忆；仅 `superseded` 状态非空 |
| `source_type` | `chat`、`doc`、`git`、`issue`、`manual`；必填 | 来源类别 |
| `source_ref` | 非空字符串，最长 512 字符；落库必填 | 稳定可定位标识，如 `conversation:<内部ID>#message:<内部ID>`、`docs/file.md#标题`、`git:<commit>`；聊天来源由后端生成 |
| `source_excerpt` | 非空字符串，最长 1,000 字符；必填 | 支撑这条记忆的原文片段；缺失时拒绝自动写入 |
| `source_platform` | 平台枚举或 `null` | 聊天来源从 Conversation 推导；文档/Git/手动记忆为 `null` |
| `conversation_id` | ID 或 `null` | 聊天来源的内部对话 ID；非聊天来源为 `null` |
| `source_message_ids` | ID 数组 | 支撑记忆的已归档消息；聊天来源至少一条且属于同一对话 |
| `valid_from` / `valid_to` | UTC 时间或 `null` | 内容生效区间；`valid_to` 不得早于 `valid_from` |
| `created_at` / `updated_at` | UTC 时间；服务端生成 | 记录时间，不等同于内容生效时间 |

`source_ref` 对 `manual` 类型采用 `manual:<客户端生成UUID>`，`source_excerpt` 填用户亲自确认的原话。对于文档/Git，尽量包含版本或 commit，使原文后续变化仍可追溯。前端仅将受信任的 `http(s)` 来源渲染为可点击外链；其他标识展示为文本或复制按钮。

聊天来源记忆的 `source_ref` 由后端按 `conversation:<id>#message:<首条ID>` 生成；`source_platform` 与 `conversation_id` 从已归档对话推导，不接受客户端随意指定。`source_excerpt` 必须是引用消息中的原文连续片段，不能由模型编造；多条消息可分别记录证据片段，首版至少保存一条可核验主证据。用户修改候选记忆正文不会改变证据关联。

### 3.3 内部存储字段

`embedding`、`embedding_model`、`embedding_dim`、`client_request_id`、内部检索索引等只在存储层使用，不作为普通 HTTP 响应字段。embedding 由 Python 生成；模型与维度是部署配置，写入时校验维度与 `VECTOR(n)` 一致。更换维度需要新表或明确的数据迁移，不能混写。

首版至少有以下持久化对象：

| 对象 | 必须保存的内容 |
| --- | --- |
| `conversations` | 平台、外部会话 ID、标题、URL、采集方法、完整度、scope、时间 |
| `messages` | 所属对话、角色、顺序、正文、平台消息 ID、时间 |
| `extraction_previews` | 预览 ID、所选消息 ID、候选及过期时间；只保存待确认状态，不进入检索 |
| `memories` | 上述 Memory 字段、embedding、模型标识、幂等键 |
| `memory_message_links` | 记忆与证据消息的多对多关联及原文片段 |
| `retrieval_traces` | `trace_id`、scope、查询、模式、候选 ID/排名/分数、预算选择与舍弃原因、Token 统计、创建时间 |

检索轨迹只保存必要的解释元数据；展示记忆内容时按 ID 从 `memories` 读取。硬删除记忆时同步清除相关轨迹中的该记忆引用，避免忘记后在解释记录中残留正文或出处。删除整段对话时，其消息、从这些消息产生的记忆和相关轨迹引用一并删除；不同来源的记忆不受影响。

## 4. HTTP API：按用户功能查接口

队员先按下表找到负责的功能，再看后续请求和响应细节。所有业务接口共用第 2 节的错误格式和第 3 节的数据模型。

| 功能组 | 用户想做什么 | 页面/调用方 | 接口 |
| --- | --- | --- | --- |
| 系统状态 | 确认后端和数据库可用 | 顶部连接状态、部署检查 | `GET /healthz`、`GET /readyz` |
| 对话档案 | 保存选定聊天、查看或删除原始记录 | 手动导入、对话首页/详情、Agent 导出适配；后续浏览器扩展 | `POST /v1/conversations`、`POST /v1/conversations/{id}/messages`、`GET /v1/conversations`、`GET /v1/conversations/{id}`、`GET /v1/conversations/{id}/messages`、`DELETE /v1/conversations/{id}` |
| 形成记忆 | 从选中消息预览候选并由用户确认，或直接写入一条记忆 | 对话详情、记忆库、Agent 工具 | `POST /v1/extractions/preview`、`POST /v1/extractions/{preview_id}/commit`、`POST /v1/memories` |
| 查看记忆 | 按来源、类别和状态浏览已确认内容 | 记忆库、对话详情 | `GET /v1/memories`、`GET /v1/memories/{id}` |
| 找回并使用记忆 | 按问题和范围搜索；由用户决定最终交给 AI 的内容 | 记忆检索页、Agent 工具；后续浏览器扩展 | `POST /v1/memories/search`、`POST /v1/memories/context`、`POST /v1/memories/handoff` |
| 解释结果 | 查看某次搜索的候选、排名和预算取舍 | 召回记录页 | `GET /v1/traces`、`GET /v1/traces/{trace_id}` |
| 更新与忘记 | 新决定替代旧决定；删除不应再保留的记忆 | 版本与冲突页、记忆详情 | `POST /v1/memories/reconcile`、`GET /v1/memories/{id}/history`、`DELETE /v1/memories/{id}` |

**两周常用流程**：手动导入或可靠的宿主导出调用“对话档案”→ 用户在网页对话详情调用“形成记忆”→ 网页和 MCP Agent 调用“找回并使用记忆”→ 需要核查时调用“解释结果”。只有经确认的记忆会被搜索。扩展完成后可增加网页聊天页的归档入口。

### 4.1 系统状态：先确认服务能用

这一组只回答“Python 服务是否活着、能否连到 seekdb”，不读取聊天或记忆。

`GET /healthz`：进程存活，返回 `{"status":"ok"}`。`GET /readyz`：检查 seekdb 连接，正常为 200，不可用为 503。二者不返回凭据或内部地址。

### 4.2 对话档案：保存和查看用户选中的原始聊天

“归档”指保留原文、平台、会话标题和消息顺序，方便以后在网页里找回。这里**不调用模型提炼记忆**。两周版本由手动导入或可靠的 Agent 宿主导出提供消息；后续浏览器扩展只上传用户确认且当前网页实际可取得的消息。Agent 导出适配只上传宿主确实提供的消息。

`POST /v1/conversations`：只归档用户本次确认的消息，**不自动提炼或写入记忆**。请求示例：

```json
{
  "scope": "project:context-trace",
  "platform": "deepseek",
  "external_conversation_id": "conv-abc",
  "title": "讨论初赛部署方式",
  "source_url": "https://chat.deepseek.com/a/chat/s/conv-abc",
  "capture_method": "browser_extension",
  "capture_completeness": "selected",
  "messages": [
    {"external_message_id": "msg-42", "sequence": 42, "role": "user", "content": "初赛要以仓库可复现为优先。", "sent_at": null},
    {"external_message_id": "msg-43", "sequence": 43, "role": "assistant", "content": "我们决定初赛优先保证本地复现，云服务器只用于团队联调。", "sent_at": null}
  ],
  "client_request_id": "8b31c0e1-12ab-4a64-8211-555555555555"
}
```

`messages` 必须有 1–100 条，按 `sequence` 升序且不能重复。首次创建返回 201 `{"conversation": <Conversation>, "messages": [<Message>], "inserted_count": 2}`。同一 scope、platform、非空 `external_conversation_id` 重新归档时合并未见过的消息并返回 200；相同 `external_message_id` 的正文不同或同一 sequence 对应不同正文返回 `STATE_CONFLICT`，不静默覆盖历史。同一请求重试遵守 `client_request_id` 幂等语义。无外部会话 ID 的来源，每次创建新对话；后续增加消息使用下述接口。归档成功不意味着平台历史记录已完整获取。

`POST /v1/conversations/{id}/messages`：向指定 scope 的已归档对话追加 1–100 条消息；请求 `{"scope":"project:context-trace","messages":[<上述消息输入>],"client_request_id":"<UUID>"}`。返回 200 `{"conversation": <Conversation>, "messages": [<本次提交对应的 Message>], "inserted_count": 1}`；已存在的相同消息计入结果但不重复插入。

`GET /v1/conversations?scope=project:context-trace&platform=deepseek&q=部署&captured_from=2026-10-01T00:00:00Z&limit=20&cursor=...`：返回 `{"items":[<Conversation>],"next_cursor":null}`。`platform`、标题关键词 `q`（1–100 字符）、`captured_from`、`captured_to` 可选；时间区间按 `captured_at` 过滤，条件取交集；按最近更新倒序；`limit` 为 1–100、默认 20。网页首页使用此接口。

`GET /v1/conversations/{id}?scope=project:context-trace`：返回 `{"conversation":<Conversation>}`。`GET /v1/conversations/{id}/messages?scope=project:context-trace&limit=50&cursor=...`：返回 `{"items":[<Message>],"next_cursor":null}`，按 `sequence ASC, id ASC` 排序；`limit` 为 1–100、默认 50。页面以消息 ID 作为记忆证据定位锚点。

`DELETE /v1/conversations/{id}?scope=project:context-trace`：用户确认后硬删除对话、其消息、这些消息产生的记忆及相关轨迹引用，并修复受影响的版本链；返回 200 `{"deleted":true,"conversation_id":"201","deleted_messages":2,"deleted_memories":1}`。不接受仅凭平台 URL 删除。

### 4.3 形成记忆：先预览候选，再由用户确认

这一组负责把一段对话里的原话变成较短、可检索的结论。用户先勾选消息；系统给出候选；用户可以删掉或修改候选；点击确认后才写入 `memories`。前端不要在“预览成功”时显示“已保存”。

`POST /v1/extractions/preview`：用户选择一段已归档对话中的消息后调用。请求：

```json
{
  "scope": "project:context-trace",
  "conversation_id": "201",
  "message_ids": ["301", "302"]
}
```

`message_ids` 为 1–50 个不重复 ID，必须均属于指定 scope 和同一 conversation。后端仅使用这些消息作为抽取输入，返回 200：

```json
{
  "preview_id": "fa9b129d-12ab-4113-a701-666666666666",
  "expires_at": "2026-10-12T08:20:00Z",
  "conversation_id": "201",
  "selected_message_ids": ["301", "302"],
  "candidates": [
    {
      "candidate_id": "6c134d5a-12ab-4b1f-9899-777777777777",
      "kind": "decision",
      "content": "初赛优先保证仓库可复现。",
      "summary": "优先仓库可复现。",
      "source_message_ids": ["301"],
      "source_excerpt": "初赛要以仓库可复现为优先。"
    }
  ]
}
```

候选可以为空；预览**不写入 `memories`，也不进入记忆检索**。候选的 `source_message_ids` 必须是本次选中的消息，`source_excerpt` 必须能在其中逐字找到。预览在服务端保留 24 小时，过期返回 `PREVIEW_EXPIRED`；保存候选证据时不新增超出选中范围的对话内容。模型或抽取服务不可用时返回 `EXTRACTION_UNAVAILABLE`，原始对话仍然已归档。

`POST /v1/extractions/{preview_id}/commit`：用户确认想保存的候选；请求：

```json
{
  "scope": "project:context-trace",
  "selected": [
    {"candidate_id": "6c134d5a-12ab-4b1f-9899-777777777777", "kind": "decision", "content": "初赛优先保证仓库可复现。", "summary": "优先仓库可复现。"}
  ],
  "client_request_id": "cdf3a109-12ab-4dab-9043-888888888888"
}
```

`selected` 可为 0–20 条；空数组表示放弃该预览并返回 200 `{"memories":[]}`。`candidate_id` 必须属于预览且不重复。用户可修改 `kind`、`content`、`summary`，但不能在确认请求中修改引用消息或证据片段；后端再次校验证据、生成 embedding，并在同一事务中保存全部选中记忆。成功返回 201 `{"memories":[<Memory>]}`；同一预览第二次用不同内容提交返回 `STATE_CONFLICT`，幂等重试返回首次结果。用户关闭预览而不确认时，不产生记忆。

### 4.4 形成记忆：直接录入一条已有结论

当来源是文档、Git 或用户明确确认的手动输入时，可跳过对话提炼流程直接写一条记忆。Agent 工具也可调用这个接口，但聊天来源仍须能指向已归档的原始消息。

`POST /v1/memories`。请求：

```json
{
  "scope": "project:context-trace",
  "kind": "decision",
  "content": "初赛演示优先保证本地可复现。",
  "summary": "初赛演示需本地可复现。",
  "importance": 0.8,
  "source_type": "doc",
  "source_ref": "docs/deployment-and-evaluation.md#一、结论",
  "source_excerpt": "初赛自动评测以仓库中的代码、配置说明……为准",
  "valid_from": null,
  "valid_to": null,
  "client_request_id": "9fca3894-12ab-4f39-a255-222222222222"
}
```

返回 201：`{"memory": <Memory>}`。幂等重放返回 200，内容与首次结果一致。缺少出处或原文片段返回 400。该接口供文档/Git/手动输入，或 Agent 主动提供已确认的记忆使用。非聊天来源必须提交 `source_ref`。若 `source_type=chat`，请求**不传** `source_ref`，必须传 `conversation_id` 和 `source_message_ids`；服务端按已归档消息验证证据并推导 `source_ref`、`source_platform`。不能仅凭 Agent 声称的聊天记录直接伪造出处。写入不会自动改写旧记忆；需要替代旧结论时使用 reconcile 接口。

### 4.5 查看记忆：浏览已确认的结论和出处

记忆库显示的是已经确认入库的结论，而非整个聊天记录。点击聊天来源的记忆时，前端利用 `conversation_id` 和 `source_message_ids` 回到原对话消息。

- `GET /v1/memories/{id}?scope=project:context-trace`：返回 `{"memory": <Memory>}`；必须传 scope。
- `GET /v1/memories?scope=project:context-trace&status=active&kind=decision&platform=deepseek&conversation_id=201&limit=20&cursor=...`：返回 `{"items": [<Memory>], "next_cursor": null}`。`status`、`kind`、`platform`、`conversation_id` 可选；多个过滤条件取交集；`limit` 范围 1–100，默认 20；按 `created_at DESC, id DESC` 排序。记忆库与对话详情使用此接口。

### 4.6 找回记忆：输入问题并限定搜索范围

用户可以只搜索某个平台、某段对话、某类记忆或某个时间段。服务返回最终建议使用的记忆，也记录其他候选为什么没有被选中。`budget_tokens` 限制交给 AI 的文本长度，**不是**数据库最多查多少条。

`POST /v1/memories/search`。请求：

```json
{
  "scope": "project:context-trace",
  "query": "初赛评测是否必须能离线复现？",
  "mode": "hybrid",
  "top_k": 1,
  "budget_tokens": 1200,
  "filters": {
    "platforms": ["deepseek", "kimi"],
    "conversation_ids": ["201"],
    "kinds": ["decision", "constraint"],
    "created_from": "2026-10-01T00:00:00Z",
    "created_to": null
  }
}
```

`query` 为 1–4,000 字符；`mode` 为 `keyword`、`vector`、`hybrid`，默认 `hybrid`；`top_k` 范围 1–20，默认 5；`budget_tokens` 范围 100–8,192，默认由服务配置给出。`filters` 可省略，省略表示当前 scope 内全部活跃记忆；数组字段如出现则必须非空且元素不重复；`conversation_ids` 最多 20 个且均需属于该 scope；`created_from`/`created_to` 是记忆入库时间过滤，二者同时给出时前者不得晚于后者。多个字段取交集；平台条件只匹配聊天来源，文档/Git/手动记忆在指定平台过滤时不参与。返回 200：

```json
{
  "trace_id": "6d0aa31d-12ab-4bf5-a801-333333333333",
  "scope": "project:context-trace",
  "query": "初赛评测是否必须能离线复现？",
  "mode_requested": "hybrid",
  "mode_used": "hybrid",
  "filters_applied": {"platforms": ["deepseek", "kimi"], "conversation_ids": ["201"], "kinds": ["decision", "constraint"], "created_from": "2026-10-01T00:00:00Z", "created_to": null},
  "items": [
    {
      "memory": {"id": "101", "scope": "project:context-trace", "kind": "decision", "content": "初赛优先保证仓库可复现。", "summary": "优先仓库可复现。", "importance": 0.8, "status": "active", "superseded_by": null, "source_type": "chat", "source_ref": "conversation:201#message:301", "source_excerpt": "初赛要以仓库可复现为优先。", "source_platform": "deepseek", "conversation_id": "201", "source_message_ids": ["301"], "valid_from": null, "valid_to": null, "created_at": "2026-10-11T08:30:00Z", "updated_at": "2026-10-11T08:30:00Z"},
      "rank": 1,
      "channels": {"keyword_rank": 2, "vector_rank": 1},
      "fusion_score": 0.0325,
      "selected_form": "summary",
      "token_count": 42,
      "reason_codes": ["KEYWORD_MATCH", "VECTOR_MATCH", "BUDGET_SUMMARY"]
    }
  ],
  "context_text": "[memory:101 | source:conversation:201#message:301]\n优先仓库可复现。",
  "budget": {"limit_tokens": 1200, "used_tokens": 42, "tokenizer": "<部署时固定的tokenizer标识>", "is_estimate": true},
  "elapsed_ms": 85
}
```

`items` 仅包含最终纳入 `context_text` 的记忆，顺序与上下文一致。`selected_form` 为 `content` 或 `summary`。`token_count` 是该条注入片段（含来源标签）的 Token 数；`budget.used_tokens` 是完整 `context_text` 的 Token 数，因此可能包含条目间分隔符。若没有候选或预算装不下任何完整片段，`items=[]`、`context_text=""`，仍返回轨迹。禁止截断到一半而失去出处。

首版检索步骤固定为：先按 scope、`status=active`、有效期及用户指定的 `filters` 过滤；关键词和向量各自取候选；`hybrid` 对两组候选去重并按 RRF 排序；按 `top_k` 和预算选择正文或摘要。关键词与向量通道的候选深度、RRF 常数及 tokenizer 在配置和 `RESULTS.md` 中记录。**不得把全文命中作为向量候选的硬性前提**。若请求 `vector`/`hybrid` 而 embedding 不可用，返回 `EMBEDDING_UNAVAILABLE`；不静默退化成关键词检索。前端显示 `mode_used`，不得据此冒称执行了混合检索。

### 4.7 使用记忆：用户勾选最终交给 AI 的内容

搜索结果只是系统建议。用户取消勾选后，此接口按剩余记忆重新组装文本；不重新搜索、不自动加入其他条目。浏览器扩展插入的是返回的 `context_text`，并由用户决定是否发送。

`POST /v1/memories/context`：用户在检索结果中取消或重新勾选记忆后调用，**只组装指定 ID，不再执行新检索**。请求 `{"scope":"project:context-trace","memory_ids":["101","108"],"budget_tokens":1200}`。`memory_ids` 是有序且不重复的 0–20 个 ID；空数组返回空上下文。所有 ID 必须属于该 scope 且当前有效，否则返回 `NOT_FOUND` 或 `STATE_CONFLICT`。返回 200 `{"requested_memory_ids":["101","108"],"included_memory_ids":["101"],"items":[{"memory_id":"101","selected_form":"summary","token_count":42}],"excluded":[{"memory_id":"108","reason_code":"BUDGET_EXCEEDED"}],"context_text":"<带出处的文本>","budget":{"limit_tokens":1200,"used_tokens":42,"tokenizer":"<标识>","is_estimate":true}}`。预算不足时保留顺序，按正文→摘要→跳过的规则处理，`items` 只列实际纳入的记忆。网页将未纳入及原因直接显示给用户；手动取消的条目不得被自动补回。

### 4.8 解释结果：查看系统为什么选了这些记忆

“检索轨迹”是实际运行日志。它记录候选来自关键词还是向量、融合排名、Token 预算下的取舍原因；网页只能解释这些真实字段，不能事后生成一个看起来合理的理由。

`GET /v1/traces?scope=project:context-trace&limit=20&cursor=...`：按 `created_at DESC` 返回 `{"items":[<轨迹摘要>],"next_cursor":null}`。摘要包含 `trace_id`、`query`、`mode_used`、`filters_applied`、选中数、候选数、`budget.used_tokens`、`elapsed_ms`、`created_at`；`limit` 为 1–100，默认 20。召回记录页面使用此接口。

`GET /v1/traces/{trace_id}?scope=project:context-trace`。返回候选轨迹：

```json
{
  "trace_id": "6d0aa31d-12ab-4bf5-a801-333333333333",
  "scope": "project:context-trace",
  "query": "初赛评测是否必须能离线复现？",
  "mode_requested": "hybrid",
  "mode_used": "hybrid",
  "filters_applied": {"platforms": ["deepseek", "kimi"], "conversation_ids": ["201"], "kinds": ["decision", "constraint"], "created_from": "2026-10-01T00:00:00Z", "created_to": null},
  "candidates": [
    {"memory_id": "101", "keyword_rank": 2, "vector_rank": 1, "fusion_score": 0.0325, "decision": "selected", "selected_form": "summary", "reason_codes": ["KEYWORD_MATCH", "VECTOR_MATCH", "BUDGET_SUMMARY"]},
    {"memory_id": "102", "keyword_rank": null, "vector_rank": 3, "fusion_score": 0.0156, "decision": "excluded", "selected_form": null, "reason_codes": ["TOP_K_EXCEEDED"]}
  ],
  "budget": {"limit_tokens": 1200, "used_tokens": 42, "tokenizer": "<部署时固定的tokenizer标识>", "is_estimate": true},
  "elapsed_ms": 85,
  "created_at": "2026-10-11T08:31:00Z"
}
```

`reason_codes` 首版集合：`KEYWORD_MATCH`、`VECTOR_MATCH`、`BUDGET_SUMMARY`、`BUDGET_EXCEEDED`、`TOP_K_EXCEEDED`。页面可把代码翻译成人话，但不能另行编造召回原因。若被引用记忆已被硬删除，轨迹里相应候选也不再返回。

### 4.9 更新记忆：新决定替代旧决定

这不是编辑旧记录的正文。新决定作为新记忆写入，旧决定标成 `superseded` 并保留来源；以后默认检索只用新决定。首版由用户明确选定被替代的旧记忆，系统不自行猜测冲突。

`POST /v1/memories/reconcile`。首版只支持明确指定旧记忆的替换；自动发现语义冲突留到后续。请求：

```json
{
  "scope": "project:context-trace",
  "old_memory_id": "101",
  "new_memory": {
    "kind": "decision",
    "content": "初赛优先保证本地复现，云服务器用于团队联调。",
    "summary": "本地复现优先，云服务器用于联调。",
    "importance": 0.8,
    "source_type": "chat",
    "conversation_id": "201",
    "source_message_ids": ["302"],
    "source_excerpt": "我们决定初赛优先保证本地复现，云服务器只用于团队联调。",
    "valid_from": null,
    "valid_to": null
  },
  "reason": "团队明确更新了部署方案，并以消息 302 为依据",
  "client_request_id": "f70cffb9-12ab-4421-9919-444444444444"
}
```

返回 200：`{"old_memory": <Memory(status=superseded)>, "new_memory": <Memory(status=active)>, "reason": "团队明确更新了部署方案，并以消息 302 为依据"}`。要求旧记忆属于相同 scope 且当前为 `active`；聊天来源的新记忆必须引用已归档消息，后端生成 `source_ref`；新记忆写入与旧记忆改状态在一个数据库事务内完成。否则返回 `NOT_FOUND` 或 `STATE_CONFLICT`。`reason` 必填，1–500 字符，并随版本变更记录保存。新记忆正文必须由引用消息支持，不能仅凭 `reason` 声称已验证。

`GET /v1/memories/{id}/history?scope=project:context-trace`：返回 `{"items":[{"memory":<Memory>,"superseded_by":"<ID或null>","reason":"<替换理由或null>"}]}`，按版本从旧到新排列；冲突档案页使用此接口。若版本链含已被硬删除的节点，结果跳过已删除正文并保持剩余节点可读。

### 4.10 使用记忆：给接手人整理交接摘要

“交接”是针对一个接手任务，从现有记忆中挑出相关决定、约束和经验，组成带出处的短文本。它使用已保存的记忆，不会凭空编写新的项目事实。

`POST /v1/memories/handoff`：请求 `{"scope":"project:context-trace","objective":"接手检索模块","budget_tokens":1200,"filters":{"platforms":["deepseek"]}}`。`filters` 与 search 相同且可省略。返回 `{"trace_id":"<UUID>","context_text":"<带出处的交接文本>","memory_ids":["101","108"],"budget":{...}}`。内部使用与 search 相同的有效性过滤、预算与轨迹机制。首版不要求 LLM 生成新事实；可按记忆类别组织已有内容。

### 4.11 忘记记忆：按用户要求彻底删除

“忘记”与“旧版本失效”不同：失效记忆仍可查历史，忘记会删除正文、embedding 和相关轨迹引用。前端应在调用前明确提示删除范围。

`DELETE /v1/memories/{id}?scope=project:context-trace`：**硬删除**指定记忆及其 embedding，并清除相关轨迹引用；返回 200 `{"deleted":true,"memory_id":"101"}`。目标不存在返回 404。前端应在用户确认后调用。`superseded` 是保留历史的版本管理；`DELETE` 是删除请求，两者不能混淆。若删除旧版本链中的节点，服务须修复或清除悬空的 `superseded_by` 引用，不得留下无效外键。

## 5. Agent 能调用的 MCP 工具

MCP 工具对应第 4 节的用户功能，只是入口从网页按钮变成 Agent 工具调用。安装 Skill 不会让服务自动读取 Agent 的完整会话历史。

MCP 端点：`/mcp`，Streamable HTTP。工具输入使用与 HTTP 对应接口相同的字段与校验，输出为同一业务 JSON 对象；MCP 的传输封装由 SDK 处理。工具异常保留第 2 节的业务错误代码，供 Agent 判断。

| 给队员的功能名 | 工具名 | 何时调用、能做什么 | 对应 HTTP |
| --- | --- | --- | --- |
| 保存选定聊天 | `conversation_capture` | 宿主实际提供了消息，且用户确认归档时提交；**不能自动读取完整历史** | `POST /v1/conversations` |
| 保存一条结论 | `memory_write` | Agent 已有明确结论及可核验出处时写入；可传幂等键 | `POST /v1/memories` |
| 找回旧结论 | `memory_search` | 开始任务前按 scope、问题和可选来源范围找记忆；返回上下文及轨迹 ID | `POST /v1/memories/search` |
| 用新决定替换旧决定 | `memory_reconcile` | 用户/Agent 明确指定旧记忆，并提供新结论及替换理由 | `POST /v1/memories/reconcile` |
| 生成接手摘要 | `memory_handoff` | 有明确接手目标时汇总相关决定、约束和经验 | `POST /v1/memories/handoff` |
| 删除一条记忆 | `memory_forget` | 用户明确要求忘记某条记忆时硬删除 | `DELETE /v1/memories/{id}` |

Skill 只规定何时调用这些工具，不负责数据库连接，也不自动赋予访问宿主历史对话的权限。`conversation_capture` 只接收工具参数中的消息；若宿主没有可靠的会话导出或事件接口，Agent 接入仅提供记忆读写，完整对话归档需另走用户导出/手动导入。现有 `integrations/agent-plugin/skills/yanji-memory/SKILL.md` 中的调用说明应按本文同步更新。

## 6. 网页前端与后续浏览器扩展约定

| 页面/能力 | 读取接口 | 写入接口 |
| --- | --- | --- |
| 对话首页 | `GET /v1/conversations` | `POST /v1/conversations` |
| 对话详情与选择性提炼 | `GET /v1/conversations/{id}`、`GET /v1/conversations/{id}/messages`、`GET /v1/memories?conversation_id=...` | `POST /v1/extractions/preview`、`POST /v1/extractions/{preview_id}/commit`、`DELETE /v1/conversations/{id}` |
| 记忆库与时间线 | `GET /v1/memories`、`GET /v1/memories/{id}` | `POST /v1/memories`、`DELETE /v1/memories/{id}` |
| 召回回放 | `POST /v1/memories/search`、`GET /v1/traces`、`GET /v1/traces/{trace_id}` | 无 |
| 最终上下文选择 | 检索结果与记忆详情 | `POST /v1/memories/context` |
| 压缩对比 | search 的 `selected_form`、`token_count`、`budget`，以及原记忆 `content`/`summary` | 无 |
| 冲突档案 | `GET /v1/memories/{id}/history`，记忆的 `status` 与 `superseded_by` | `POST /v1/memories/reconcile` |
| 成本看板 | 检索轨迹中的 Token 与耗时 | 无 |
| 浏览器扩展（后续） | 读取获授权当前网页的可见消息；按用户选择调用 search 并预览 `context_text` | 用户确认后调用 conversation 归档；需要提炼时调用 preview/commit；插入输入框不自动发送 |

浏览器扩展在网页 + MCP 闭环通过验收后开发，再为 DeepSeek、Kimi、豆包网页分别实现适配器。适配器只负责页面读取、来源定位和输入框插入；抽取、检索、冲突与压缩归 Python 服务。扩展采用用户点击保存/提炼/插入的显式流程，**不自动上传整段聊天记录**。跨域来源白名单和认证方式由部署配置明确列出，不能使用任意来源的宽松 CORS 配置。

## 7. 首版验收用例

1. 从仓库样例手动导入至少两条消息，归档后网页对话列表与详情显示平台、标题、角色、消息和 `capture_completeness`；归档本身不生成记忆。
2. 对选中消息生成候选，关闭预览不入库；确认一条候选后，记忆能指回原对话和消息，证据原文可核验。
3. 从样例文档直接写入一条带 `source_ref`、`source_excerpt` 的记忆，读回字段一致；缺任一出处字段拒绝写入。
4. 同一 `client_request_id` 重试不重复写入；相同 ID 配不同正文返回冲突；重复归档不会重复生成消息。
5. 不同 scope 中有同词条时，对话、消息、记忆、检索和轨迹均不会跨 scope 泄露。
6. 以平台、对话、类别和时间过滤检索；混合模式允许仅由向量命中的候选进入结果。
7. 预算缩小后优先采用摘要或排除候选；用户取消勾选的记忆在最终上下文中不出现。
8. 显式替代后旧记忆仍能在时间线查到，但默认检索只返回新记忆；失败时事务回滚。
9. MCP 与 HTTP 调用同一业务逻辑；未提供消息的 Agent 宿主不能通过 MCP 凭空归档历史对话。
10. 硬删除一条记忆或整段对话后，相应正文、embedding、证据和轨迹引用不可再读取。
11. 在无腾讯云配置、无浏览器扩展的干净环境中，从样例对话完成归档、网页选取/提炼/检索/溯源，并让 Agent 经 MCP 搜索到同一份记忆。

## 8. 与现有文件的关系及待审查决定

- `python/yanji/store/schema.sql` 当前只有记忆草案表，缺 `conversations`、`messages`、`memory_message_links`、`extraction_previews`、`source_excerpt`、`embedding_model`、幂等键和轨迹表；实施时需迁移到本文模型，并在固定 seekdb 版本上验证 DDL。
- `.env.example` 当前仅有 `SEEKDB_PATH`。需要补服务模式的 host/port/user/password/database、embedding 模型与维度、Token 计数器及认证配置。
- 现有项目方案写“一条 SQL 完成混合检索”。本文首版采用**同一 seekdb 内两路候选、Python 融合排序**，以保证关键词未命中的语义结果仍可召回。若实测证明单 SQL 方案同时满足召回与性能，可在后续版本改实现，不改变 API。
- 需队长审查并最终确定：① seekdb 固定版本与 embedding/抽取模型；② 对话正文的保存范围与数据保留期限；③ 检索候选深度、RRF 常数与 tokenizer；④ 联调和演示环境的认证方式；⑤ 自动评测要求的启动命令与数据准备流程；⑥ 首个可靠的浏览器站点适配器。
