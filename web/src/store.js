import { reactive } from 'vue'

export const store = reactive({
  // 全局抽屉
  apiDrawerOpen: false,

  // 从对话档案勾选、待提炼的消息
  selectedMessages: [],

  // 已确认保存的记忆
  savedMemories: [
    {
      id: 'm1',
      category: '决策',
      title: '初赛优先保证仓库可复现',
      content: '决定优先使用现有的服务器部署初赛环境，保证本地可复现。这样可以减少申请流程的时间，同时便于后续维护。如果现有资源不足，再考虑申请新的服务器。',
      source: 'DeepSeek',
      conversation: '初赛部署讨论',
      conversationId: 2,
      time: '今天 10:15',
      quote: '建议优先使用现有的服务器，保证环境可复现。这样可以减少申请流程的时间，同时便于后续维护。如果现有资源不足，再考虑申请新的服务器。'
    },
    {
      id: 'm2',
      category: '行动',
      title: '后续考虑申请新的服务器',
      content: '如果本地资源不足，再考虑申请新的服务器，由服务器团队协助测试和部署。',
      source: 'DeepSeek',
      conversation: '初赛部署讨论',
      conversationId: 2,
      time: '今天 10:18',
      quote: '如果现有资源不足，再考虑申请新的服务器。到时候可以请服务器团队协助测试，确认环境稳定后再上线。'
    }
  ],

  // API 设置
  apiSettings: {
    modelType: 'extract',
    provider: '自定义兼容接口',
    baseUrl: '',
    modelName: '',
    apiKey: ''
  },

  toast: { show: false, text: '' },
  showToast(text) {
    this.toast.text = text
    this.toast.show = true
    clearTimeout(this._t)
    this._t = setTimeout(() => (this.toast.show = false), 2400)
  }
})