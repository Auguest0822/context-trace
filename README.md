# 言迹 ContextTrace

> 可追溯的 Agent 长期记忆层 —— Traceable long-term memory for AI agents
> 让 AI 助手记住"上周我们为什么这么决定"，跨会话、跨人交接都不丢上下文，且每条记忆都能指回出处。

## 快速开始
```bash
make install
make demo
```

## 目录导航
| 目录 | 内容 | 负责人 |
| --- | --- | --- |
| `python/yanji/` | 记忆引擎（采集/抽取/存储/检索/裁决/压缩/注入/可解释）+ MCP Server | 队长 |
| `integrations/agent-plugin/` | Agent Plugin 包（plugin.json + mcp.json + SKILL.md） | 前端 B |
| `web/` | 可视化控制台（时间线 / 召回回放 / 压缩对比 / 冲突档案 / 成本看板） | 前端 A |
| `extensions/chat-memory/` | 浏览器扩展（Demo 外壳，可选） | 前端 A |
| `bench/` | 评测（LoCoMo 对比、消融实验、自建数据集） | 队长 |
| `docs/` | 架构、实验数据、AI 使用说明、复现步骤 | 前端 B |

## 实验数据
见 [docs/RESULTS.md](docs/RESULTS.md)。

## 许可
Apache-2.0
