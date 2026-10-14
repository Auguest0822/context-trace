// 模拟数据 —— 与 UI 图保持一致

export const SOURCES = {
  DeepSeek: { name: 'DeepSeek', color: '#4D6BFE', text: 'D', type: 'letter' },
  Kimi: { name: 'Kimi', color: '#111111', text: 'K', type: 'letter' },
  豆包: { name: '豆包', color: '#F5455C', text: '豆', type: 'letter' },
  Agent: { name: 'Agent', color: '#64748B', text: 'A', type: 'letter' }
}

export const FILTERS = [
  { key: 'all', label: '全部', count: 12 },
  { key: 'DeepSeek', label: 'DeepSeek', count: 4 },
  { key: 'Kimi', label: 'Kimi', count: 3 },
  { key: '豆包', label: '豆包', count: 3 },
  { key: 'Agent', label: 'Agent', count: 2 }
]

export const CONVERSATIONS = [
  {
    id: 1,
    title: '初赛部署讨论',
    summary: '讨论初赛环境部署方案，包括本地复现、依赖安装和运行脚本配置。',
    source: 'DeepSeek',
    time: '今天 10:24',
    createdAt: '创建于 2024-06-18 10:24',
    messageCount: 18,
    badge: '已选 2 条消息'
  },
  {
    id: 2,
    title: '需求评审会议',
    summary: '整理需求文档结构与下一步分工。',
    source: 'Kimi',
    time: '今天 09:17',
    createdAt: '创建于 2024-06-18 09:17',
    messageCount: 26,
    visible: true
  },
  {
    id: 3,
    title: '产品文案优化',
    summary: '优化官网产品介绍文案，突出核心价值和典型使用场景。',
    source: '豆包',
    time: '昨天 18:03',
    createdAt: '创建于 2024-06-17 18:03',
    messageCount: 14,
    visible: true
  }
]

export const MESSAGES = [
  {
    id: 1,
    seq: 1,
    role: '我',
    avatar: 'R',
    time: '10:12',
    text: '我们这次初赛的部署环境，优先考虑什么？\n是用现有的服务器，还是申请一台新的？需要能本地完整复现。'
  },
  {
    id: 2,
    seq: 2,
    role: 'DeepSeek',
    source: 'DeepSeek',
    time: '10:15',
    text: '建议优先使用现有的服务器，保证环境可复现。\n这样可以减少申请流程的时间，同时便于后续维护。\n如果现有资源不足，再考虑申请新的服务器。'
  },
  {
    id: 3,
    seq: 3,
    role: '我',
    avatar: 'R',
    time: '10:18',
    text: '可以，就按这个方案执行。\n请你整理一个部署步骤清单，包括依赖版本、安装命令和启动命令。\n我稍后同步给团队。'
  },
  {
    id: 4,
    seq: 4,
    role: 'DeepSeek',
    source: 'DeepSeek',
    time: '10:21',
    text: '好的，下面是基于现有服务器的本地复现步骤：\n1. 安装基础依赖（Python 3.10、必要的系统库）。\n2. 创建虚拟环境并安装项目依赖。\n3. 配置环境变量，准备数据目录。\n4. 运行启动脚本，验证服务是否正常。'
  }
]

// 记忆提炼页 —— 已选对话内容（默认选中 #2、#3）
export const DEFAULT_SELECTED = [2, 3]

export const CANDIDATES = [
  {
    id: 'c1',
    category: '决策',
    basedOn: [2, 3],
    content: '初赛部署优先使用现有服务器，保证环境可复现；如资源不足再申请新的服务器。',
    citations: [
      { seq: 2, role: 'DeepSeek', text: '建议优先使用现有的服务器，保证环境可复现。这样可以减少申请流程的时间，同时便于后续维护。如果现有资源不足，再考虑申请新的服务器。' },
      { seq: 3, role: '我', text: '可以，就按这个方案执行。' }
    ]
  },
  {
    id: 'c2',
    category: '约束',
    basedOn: [2, 3],
    content: '部署步骤清单需要包含依赖版本和启动命令，并在整理后同步给团队。',
    citations: [
      { seq: 3, role: '我', text: '请你整理一个部署步骤清单，包括依赖版本、安装命令和启动命令。我稍后同步给团队。' }
    ]
  }
]

// 记忆检索页
export const SEARCH_RESULTS = [
  {
    id: 'm1',
    category: '决策',
    title: '初赛优先保证仓库可复现',
    desc: '决定优先使用现有的服务器部署初赛环境，保证本地可复现。这样可以减少申请流程的时间，同时便于后续维护。',
    source: 'DeepSeek',
    conversation: '初赛部署讨论',
    conversationLabel: '对话 #2 初赛部署讨论',
    time: '今天 10:15',
    quote: '建议优先使用现有的服务器，保证环境可复现。这样可以减少申请流程的时间，同时便于后续维护。如果现有资源不足，再考虑申请新的服务器。',
    tokens: 98,
    matchedBy: ['关键词匹配', '向量相似']
  },
  {
    id: 'm2',
    category: '行动',
    title: '后续考虑申请新的服务器',
    desc: '如果本地资源不足，再考虑申请新的服务器，由服务器团队协助测试和部署。',
    source: 'DeepSeek',
    conversation: '初赛部署讨论',
    conversationLabel: '对话 #2 初赛部署讨论',
    time: '今天 10:18',
    quote: '如果现有资源不足，再考虑申请新的服务器。到时候可以请服务器团队协助测试，确认环境稳定后再上线。',
    tokens: 58,
    matchedBy: ['向量相似']
  }
]

export const MATCH_EXPLAIN = [
  { seq: 1, ways: ['关键词匹配', '向量相似'], text: '匹配到关键词：本地复现、优先、初赛、服务器、减少申请流程', target: '#1' },
  { seq: 2, ways: ['向量相似'], text: '语义相似：涉及服务器资源不足、申请新服务器、服务器团队测试', target: '#2' }
]