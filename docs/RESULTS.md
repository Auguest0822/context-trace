# 每日验收与实验结果

日期：2026-10-24（Asia/Shanghai）。Windows / PowerShell / Python 3.12.14；真实数据库 `5.7.25-OceanBase seekdb-v1.4.0.0`，容器 `contexttrace-seekdb`，端口 2881。既有 API 8000 的 `/readyz` 为 `ok`；另启动启用字符向量基线的验收 API 8007，网页 5180 连接 8007。

| 天数 | 实际证据 | 结论 |
| --- | --- | --- |
| D1 | 契约、样例已存在，真实连接检查成功；按队长决定移除整段对话级联删除 | 连接与契约核对通过 |
| D2 | 新 scope 归档 4 条消息，角色与顺序正确，原样重试不重复新增 | 真实 seekdb 通过 |
| D3 | 列表、详情、消息 API 顺序读回；网页显示项目两段真实归档（4/8 条消息） | API 与网页通过 |
| D4 | 预览前后记忆为空，确认后保存证据关联；网页保存 #2000021 后可定位原消息 #2000001 | 数据库与网页通过 |
| D5 | 关键词检索返回确认记忆和来源；网页找到本轮人工保存记忆 | 检索与网页通过 |
| D6 | MCP 写入 #2000005，HTTP 读回同 ID，再由 MCP 搜索到；6 个工具可发现 | 协议与同库通过；实际 Agent 宿主配置待人工验证 |
| D7 | 网页选消息→人工候选编辑确认→记忆库→检索→溯源；MCP 找回网页记忆 #2000021 | 网页与 MCP 协议闭环通过；干净环境和 Agent 宿主待验 |
| D8 | `live_acceptance --vector` 实测三种模式；独立数据集三路对照完成 | seekdb 向量与混合通过 |
| D9 | 空选择为空上下文；长正文在 100 Token 下用带出处摘要；网页取消首项后 4→3 条，Token 213→162；点击复制后实际粘贴，取消的 #2000021 不在文本中且其余来源保留 | 组装、网页选择与复制粘贴通过 |
| D10 | 替代后旧记忆不在 active 列表，历史可读；遗忘自身新建测试记忆后 GET 为 404 | 单条版本与遗忘通过；整段对话删除不实现 |
| D11 | 真实轨迹列表/详情、交接通过；网页展示实际排名、方式和预算 | 数据库与网页通过 |
| D12 | 独立 scope，15 条记忆、30 题，三种模式×两档预算，共 180 次查询 | 真实评测完成 |
| D13 | 真实截图、复现命令、架构和 AI 记录已更新；测试与构建通过 | 当前机器通过；队友独立安装、Agent 宿主与演示录屏待完成 |
| D14 | 尚未打 tag，待 D13 人工复走和冻结 | 未完成 |

## 可核查的闭环标识

- 后端验收 scope：`acceptance:233bb08a-a3e8-485b-bbf2-54ff226f241f`；对话 #3000005，确认记忆 #2000040。
- MCP scope：`mcp-acceptance:44a28529-45b3-43e3-a645-924014f8e6cb`；记忆 #2000005。
- 网页确认：`project:context-trace` 中记忆 #2000021，出处 `conversation:2000001#message:2000001`；MCP 搜索与 HTTP 读回同 ID，轨迹 `7436f0d9-61c3-4bae-a05a-37725a7163ba`。
- [网页搜索](screenshots/live-search.png)、[原始消息定位](screenshots/live-source.png)、[真实召回记录](screenshots/live-recall.png)、[取消勾选后的上下文](screenshots/live-context-selection.png)。

## 固定 30 题评测

最终明细：[benchmark-results.json](benchmark-results.json)。scope 为 `benchmark:context-trace-v1`，与日常网页隔离，实查恰好 15 条记忆；问题集 `data/fixtures/search-eval.json`，每题一个标准记忆，`top_k=5`。

| 模式 | 预算 | Hit@1 | Hit@5 | 中位数 ms | P95 ms | 平均估算 Token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| keyword | 1200 | 83.33% | 96.67% | 33.0 | 59 | 179.27 |
| keyword | 8192 | 83.33% | 96.67% | 29.5 | 49 | 179.27 |
| vector | 1200 | 76.67% | 96.67% | 30.5 | 58 | 247.87 |
| vector | 8192 | 76.67% | 96.67% | 29.0 | 48 | 247.87 |
| hybrid | 1200 | 80.00% | 100.00% | 31.0 | 53 | 249.60 |
| hybrid | 8192 | 80.00% | 100.00% | 31.0 | 53 | 249.60 |

配置：`char-ngram-hash-v1`，1024 维；seekdb L2 向量候选最多 100，关键词命中候选最多 200，RRF 常数 60。关键词使用中文二元片段/英文词的 INSTR 命中后重排；向量是字符特征哈希，**不是神经语义 embedding**。Token 为 `utf8-bytes/3` 估算。P95 采用 nearest-rank（30 条中的第 29 条）。耗时覆盖检索和上下文组装，不含后续轨迹持久化、事务提交及 HTTP 往返。

限制：这是 15 条人工样例的小规模回归集，不能推导生产规模或泛化效果。1200/8192 都能装下短记忆，所以两档预算结果相同，不能声称压缩提高命中率；D9 另用长正文和 100 Token 验证摘要降级。hybrid 的 Hit@1 低于 keyword，混合并非所有指标都更好。

## 复跑命令

先按 [启动说明](python-api-startup.md) 配置数据库环境变量，密码不写入仓库。

```powershell
.\.venv\Scripts\python.exe -m yanji.eval.live_acceptance --base-url http://127.0.0.1:8007 --vector
.\.venv\Scripts\python.exe -m yanji.eval.mcp_acceptance --base-url http://127.0.0.1:8007
$env:YANJI_EMBEDDING_BACKEND = 'hash'
.\.venv\Scripts\python.exe -m yanji.store.seed_demo --scope benchmark:context-trace-v1
.\.venv\Scripts\python.exe -m yanji.eval.run_benchmark --scope benchmark:context-trace-v1
```

8007 为本轮独立验收服务；也可在启动 8000 前启用 hash，再改上述 base URL。验收脚本使用新 scope 留存记录，只遗忘自身生成的单条测试记忆。修复后复核：Python 单测 27 项、前端测试 9 项、ruff、mypy、Vite build 均通过。

## 本轮修复与保留事项

1. MCP SDK 2.3 使用 Python 字段 `is_error` / `structured_content`；修复验收脚本旧字段名后，同库实测通过。
2. 网页最终上下文误展示证据片段，已改为实际正文或摘要，并避免旧请求覆盖新勾选结果。
3. 提炼页“不生成向量”的固定提示已改为由服务端配置决定。
4. 评测原先混入日常 scope 数据，已在独立 scope 重跑；P95 修为 nearest-rank。

队长于 2026-10-24 明确不批准整段对话级联永久删除，已移出本轮契约交付，无须再次申请批准。真实 Agent 宿主、队友干净环境复走及演示录屏仍待验证；未打 tag，也未推送。IAB 的剪贴板工具读取曾返回空值，之后通过真实 Ctrl+V 粘贴验证复制内容和取消勾选均正确，不把该工具空值归因于产品故障。
