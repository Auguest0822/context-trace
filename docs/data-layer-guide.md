# 数据层动手指南：先归档原始对话

本阶段只实现 `Conversation` 和 `Message` 的保存与读取。它们是原始档案；`Memory` 必须在后续“用户确认提炼”步骤中单独写入。

## 1. 读一遍调用链

```text
样例 JSON / 未来的 HTTP 请求
  → models.py：检查字段、角色、消息顺序和时间
  → repo.py：按 scope 查重，事务写入 Conversation + Message
  → client.py：创建 seekdb 连接
  → schema.sql：持久化表与唯一索引
```

- [`python/yanji/models.py`](../python/yanji/models.py)：输入模型拒绝未知字段和非法枚举。`messages` 必须有 1–100 条，`sequence` 严格递增；`sent_at` 有值时必须带时区。
- [`python/yanji/store/client.py`](../python/yanji/store/client.py)：读取 `SEEKDB_*` 环境变量并建立连接，统一设置 UTC 会话时间。
- [`python/yanji/store/repo.py`](../python/yanji/store/repo.py)：对话归档、追加消息和分页读取。写入在一个事务中完成；任意一条消息冲突时整次写入回滚。

你阅读 `repo.py` 时，建议按 `capture_conversation` → `_store_messages` → `list_messages` 的顺序。前者决定新建还是合并对话；中间函数用 `sequence` 和可取得的 `external_message_id` 去重；最后按 `sequence` 返回原始顺序。

## 2. 从仓库样例导入

先按 [`reproduction.md`](reproduction.md) 完成依赖安装、数据库连接和建表。在仓库根目录运行：

```powershell
python -m yanji.store.import_fixture data/fixtures/conversation-import.sample.json --prompt-password
```

首次执行应显示 `inserted_count=4`。样例带固定的 `client_request_id`；原样重复执行应显示相同 `conversation_id` 和 `inserted_count=4`，这是**首次请求结果的幂等重放**，不是又插入四条。实际库中的 `message_count` 仍为 4。修改请求体后仍沿用这个 ID，会得到幂等冲突；要提交新请求，生成新的 UUID。

进入 seekdb 后可以核对：

```sql
SELECT id, scope, platform, title, message_count FROM conversations
WHERE scope = 'project:context-trace';

SELECT sequence, role, content FROM messages
WHERE conversation_id = <上一步返回的 ID>
ORDER BY sequence;

SELECT COUNT(*) FROM memories WHERE scope = 'project:context-trace';
```

第三条用于确认归档过程没有创建记忆；若以前已经手工写过记忆，比较导入前后的数量即可。

## 3. 你接下来亲手完成的 HTTP 层

在 `python/yanji/server/api.py` 中只做参数接收和错误映射，直接调用仓储函数，不再写第二套 SQL：

| HTTP 路由 | 调用的函数 | 成功结果 |
| --- | --- | --- |
| `POST /v1/conversations` | `capture_conversation` | 新建时 201、合并时 200；移除内部 `created` 字段后返回契约 JSON |
| `POST /v1/conversations/{id}/messages` | `append_messages` | 200 |
| `GET /v1/conversations` | `list_conversations` | 列表和 `next_cursor` |
| `GET /v1/conversations/{id}` | `get_conversation` | 对话详情 |
| `GET /v1/conversations/{id}/messages` | `list_messages` | 按顺序分页的消息 |

将输入校验异常映射为 `VALIDATION_ERROR`，`NotFound` 映射为 404，`StateConflict` 和 `IdempotencyConflict` 映射为 409。所有列表和详情都必须传 `scope`。接口的完整请求与响应见 [`api-data-contract.md`](api-data-contract.md)。

## 4. 验收时重点看什么

1. 同一 `client_request_id` 原样重试：返回首次结果，数据库行数不变。
2. 同一平台会话 ID、不同请求 ID 再导入相同消息：`inserted_count=0`。
3. 同一 `sequence` 或外部消息 ID 对应不同正文：整个请求回滚，不覆盖原文。
4. 换一个 `scope` 查询已有对话 ID：返回未找到。
5. 消息列表按 `sequence` 而不是数据库插入时间排序。

数据库唯一索引是最后一道防线；请求字段的长度、枚举、来源 URL 等由输入模型检查。业务接口接入后还要用真实 HTTP 请求复测这些行为。
