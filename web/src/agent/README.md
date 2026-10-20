# 前端与 Agent 的交互逻辑

本文件夹存放「前端 ↔ Agent ↔ 记忆库」两条链路的交互代码，页面组件只调用这里的函数，不直接处理请求细节。

## 链路一：选择性记忆提取

```
用户勾选对话消息
  → memoryFlow.previewCandidates()        Agent 提炼候选记忆（后端未实现时走 mockAgent）
  → 前端展示候选，用户勾选/修改类别与正文
  → memoryFlow.saveConfirmedCandidates()  走契约接口 POST /v1/extractions/{preview_id}/commit 落库
```

**保存必须走接口，不能前端直连数据库。** 原因（见 `docs/api-data-contract.md` 4.3）：

1. 后端要再次校验证据片段确实来自所选消息，防止模型编造出处；
2. `source_ref`、`source_platform`、`conversation_id` 由后端从已归档对话推导；
3. 记忆与证据消息的关联在同一数据库事务内写入，并有 `client_request_id` 幂等保护；
4. 直连数据库会绕过以上全部校验，且后续接入 embedding 时无法自动补齐。

**当前桥接说明**：契约的 `POST /v1/extractions/preview` 只有 `manual` 模式（逐条复制原文当草稿）；Agent 自动提炼是后端待实现能力（计划端点 `POST /v1/agent/extract`）。在它落地前：

- 展示层用 `previewCandidates()`（Agent/mock 的候选）给用户看；
- 真正提交时必须使用 `previewManual()` 返回的 `preview_id` 与候选 `candidate_id`（commit 会校验候选属于该预览）。后端实现 `mode: auto` 后，这两步会合并为一次调用。

## 链路二：提问问答 + 记忆引用

```
用户提问
  → askFlow.askWithMemories(question)
      1. POST /v1/memories/search   按问题检索记忆（契约已定义，含 trace_id 与 reason_codes）
      2. POST /v1/agent/ask         把问题 + 检索到的记忆发给 Agent（未实现时走 mock）
  → 前端展示：
      - AI 回复（人话表述）
      - 引用了哪些记忆（可展开查看原文 sourceExcerpt，点击跳回对话详情）
      - 为什么引用这段记忆（reasonCodes.js 把契约的 reason_codes 翻译成人话，不编造理由）
用户取消部分记忆片段
  → askFlow.recomposeAnswer(question, kept)
      1. POST /v1/memories/context  只重组保留的记忆，不重新检索、不自动补回（契约 4.7）
      2. POST /v1/agent/ask         基于剩余记忆让 Agent 重新生成回答
```

## 文件说明

| 文件 | 职责 |
| --- | --- |
| `http.js` | 共享请求封装（baseUrl、scope、契约错误格式） |
| `agentClient.js` | Agent 通信层：extract / ask / context / search，后端不可用时自动降级 mock |
| `mockAgent.js` | mock 数据，前端可先于后端开发联调 |
| `memoryFlow.js` | 链路一编排：预览候选 → 确认保存 |
| `askFlow.js` | 链路二编排：提问 → 引用展示 → 取消片段 → 重新作答 |
| `reasonCodes.js` | `reason_codes` → 中文解释（只翻译契约内的代码） |

## 环境变量

- `VITE_AGENT_BASE_URL`：Agent 服务地址（默认复用 `VITE_API_BASE_URL`，即 `http://127.0.0.1:8000`）
- `VITE_AGENT_ENABLED=false`：强制 mock 模式，不请求后端
