# 提炼记忆流程（extraction flow）

「用户选对话 → 传给队长 → 队长返回候选 → 用户勾选是否保存 → 存库」的**唯一业务逻辑**。
UI（浮窗 / 侧边栏 / popup）不直接碰接口，全部通过 `CT_FLOW_*` 消息调用本目录的 `ExtractionFlowService`（跑在 background）。

## 文件

- `types.ts` — 状态机类型：`ExtractionStep` + `ExtractionFlowState`（全 JSON 可序列化）
- `service.ts` — 编排服务：状态流转 + 队长接口调用 + `chrome.storage.session` 持久化

## 状态机

```
idle ──start()──▶ previewing ──队长返回候选──▶ reviewing ──confirm()──▶ saving ──▶ done
                      │                          │ ▲                        │
                      └──失败──▶ error ◀──失败────┘ └───────reset()──────────┘
```

- `reviewing` 阶段候选**默认全选**，用户逐条取消；内容可编辑（记入 `edits`）
- `done` 后 `reset()` 回 idle，但保留会话选择，方便连续提炼

## 与 API 契约的对应（docs/api-data-contract.md 第 6 节）

| 流程步骤 | 服务方法 | 契约接口 |
|---|---|---|
| ① 选会话 / 勾选消息 | `pickConversation` `toggleMessage` | 本地行为，不走接口 |
| ② 发给队长（不落库） | `start()` | `POST /v1/extractions/preview`，入参 `{conversation_id, message_ids}`，返回 `{preview_id, candidates[]}` |
| ③ 列举候选供用户勾选/编辑 | `toggleCandidate` `setContent` | 本地行为 |
| ④ 确认保存（写数据库） | `confirm()` | `POST /v1/extractions/{preview_id}/commit`，入参 `{candidate_ids, overrides}`；overrides = 用户编辑后的内容 |
| ⑤ 保存结果 | state.savedCount | 保存的记忆立即可在 `GET /v1/memories` 查到 |

## UI 接入（CT_FLOW_* 消息）

| 消息 | 入参 | 返回 |
|---|---|---|
| `CT_FLOW_GET_STATE` | — | 当前状态 |
| `CT_FLOW_LIST_CONVERSATIONS` | — | 会话列表（含消息，远端懒拉） |
| `CT_FLOW_PICK_CONVERSATION` | `{conversationId}` | 状态（默认勾选前 4 条消息） |
| `CT_FLOW_TOGGLE_MESSAGE` | `{messageId, checked}` | 状态 |
| `CT_FLOW_START` | — | 状态（=② 发给队长） |
| `CT_FLOW_TOGGLE_CANDIDATE` | `{candidateId, checked}` | 状态 |
| `CT_FLOW_SET_CONTENT` | `{candidateId, content}` | 状态 |
| `CT_FLOW_CONFIRM` | — | 状态（=④ 保存落库） |
| `CT_FLOW_RESET` | — | 状态 |

未配置队长后端（`mock=true` 或无 baseUrl）时自动降级内置 mock，流程完全一致。
