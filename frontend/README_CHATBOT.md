# 前端 Chatbot 验证指南

## ✅ 前端已准备就绪

### 已完成的组件

1. **API 调用** (`src/api/chat.ts`)
   - ✅ `streamNodeChat` - SSE 流式聊天 API
   - ✅ 完整的错误处理
   - ✅ TypeScript 类型定义

2. **聊天 UI 组件** (`src/components/topology/NodeChatPanel.tsx`)
   - ✅ 聊天消息显示
   - ✅ 流式响应实时显示
   - ✅ 输入框和发送按钮
   - ✅ 使用统计显示（tokens, cost, latency）
   - ✅ 错误提示

3. **集成到节点详情面板** (`src/components/topology/NodeDetailPanel.tsx`)
   - ✅ "聊天" 按钮
   - ✅ 聊天面板切换
   - ✅ 自动刷新节点数据

## 🚀 验证步骤

### 前置条件

1. **启动后端服务器**
   ```bash
   cd 根目录
   python -m uvicorn backend.app.main:app --reload
   ```

2. **设置 LLM API Key**(If you have already set it in the .env file, you can ignore step 2.)
   ```bash
   # 方式 1: 环境变量
   # OpenAI
   export OPENAI_API_KEY=your_api_key_here
   
   # 智谱AI (ZhipuAI)
   export ZHIPUAI_API_KEY=your_api_key_here
   
   # 方式 2: .env 文件（在项目根目录）
   echo "OPENAI_API_KEY=your_api_key_here" >> .env
   echo "ZHIPUAI_API_KEY=your_api_key_here" >> .env
   ```

3. **启动前端开发服务器**
   ```bash
   cd frontend
   npm run dev
   ```

### 验证流程

#### 步骤 1: 创建测试节点

1. 打开前端应用（通常是 `http://localhost:5173`）
2. 创建一个新节点，确保：
   - 设置了 `system_instruction`（系统提示词）
   - 配置了 `llm_settings`：
     - **LLM Provider**: 选择提供商（OpenAI、Anthropic、智谱AI等）
     - **LLM 模型**: 根据选择的 Provider 选择模型
       - OpenAI: `gpt-4o`, `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`
       - Anthropic: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`
       - 智谱AI: `glm-4-flash`, `glm-4`, `glm-3-turbo`
     - **Temperature**: 设置温度值（0-2，默认 0.7）
     - **Max Tokens**: 设置最大 token 数（默认 1024）
     
     示例配置（OpenAI）：
     ```json
     {
       "provider": "openai",
       "model": "gpt-4o",
       "temperature": 0.7,
       "max_tokens": 1024
     }
     ```
     
     示例配置（智谱AI）：
     ```json
     {
       "provider": "zhipuai",
       "model": "glm-4-flash",
       "temperature": 0.7,
       "max_tokens": 1024
     }
     ```

#### 步骤 2: 打开聊天面板

1. 在节点列表中点击一个节点
2. 在节点详情面板中，点击 **"聊天"** 按钮
3. 聊天面板应该显示在节点详情下方

#### 步骤 3: 发送第一条消息

1. 在输入框中输入：`你好`
2. 点击 **"发送"** 或按 `Enter`
3. 应该看到：
   - 你的消息出现在右侧（用户消息）
   - LLM 的回复实时流式显示在左侧（助手消息）
   - 底部显示使用统计（tokens, latency 等）

#### 步骤 4: 验证历史记录

1. 发送第二条消息：`请介绍一下你自己`
2. 应该看到：
   - 第一条对话的历史记录仍然显示
   - LLM 应该能记住之前的对话
   - 新的回复追加到历史记录中

#### 步骤 5: 验证流式输出

1. 发送一条较长的消息，观察：
   - 文本应该逐字显示（流式效果）
   - 不应该等待完整响应后才显示
   - 有一个闪烁的光标表示正在输入

   建议测试消息（复制以下内容测试流式效果）：
   ```
   请详细解释一下什么是 React Hooks，包括 useState、useEffect、useContext 等常用 Hooks 的使用场景和最佳实践。请用具体的代码示例来说明每个 Hook 的用法，并解释它们如何帮助开发者更好地管理组件状态和副作用。同时，请说明 Hooks 相比传统的类组件有哪些优势，以及在什么情况下应该使用自定义 Hooks 来封装可复用的逻辑。
   ```
   
   或者使用这个更长的测试消息：
   ```
   请写一篇关于人工智能发展历史的文章，从 1950 年代的图灵测试开始，详细描述每个重要阶段：包括符号主义时代、专家系统的发展、机器学习的兴起、深度学习的突破、以及当前大语言模型和生成式 AI 的快速发展。请涵盖关键人物、重要里程碑事件、技术突破，以及这些发展如何影响我们今天的生活和工作方式。文章应该至少包含 500 字，结构清晰，逻辑连贯。
   ```

#### 步骤 6: 验证错误处理

1. 如果 API Key 未设置或无效：
   - 应该显示错误提示
   - 不应该崩溃

2. 如果网络断开：
   - 应该显示网络错误
   - 可以点击"取消"按钮停止请求

## 🎯 预期行为

### 正常流程

1. **消息发送**
   - 用户消息立即显示在右侧
   - 助手回复流式显示在左侧
   - 完成后显示使用统计

2. **历史记录**
   - 所有消息按时间顺序显示
   - 用户消息在右侧（深色背景）
   - 助手消息在左侧（浅色背景）
   - 每条消息显示时间戳

3. **自动刷新**
   - 聊天完成后，节点数据自动刷新
   - 历史记录更新到最新状态

### 错误处理

- **Token 溢出**: 显示详细的错误信息，包括当前 token 数和最大限制
- **LLM 调用失败**: 显示错误消息，不崩溃
- **网络错误**: 显示网络错误提示

## 🔍 调试技巧

### 检查浏览器控制台

打开浏览器开发者工具（F12），查看：
- Network 标签：检查 API 请求是否成功
- Console 标签：查看是否有错误日志

### 检查后端日志

在后端服务器终端查看：
- 是否有错误日志
- Token 计算是否正确
- LLM 调用是否成功

### 常见问题

1. **"Failed to fetch"**
   - 检查后端服务器是否运行
   - 检查 CORS 配置
   - 检查 API URL 是否正确

2. **"Token limit exceeded"**
   - 减少 `system_instruction` 长度
   - 清理 `chat_history`
   - 增加 `max_tokens` 设置

3. **"LLM call failed"**
   - 检查 API Key 是否正确设置
   - 检查网络连接
   - 检查模型名称是否正确

## 📝 测试清单

- [ ] 可以打开聊天面板
- [ ] 可以发送消息
- [ ] 可以看到流式响应
- [ ] 历史记录正确显示
- [ ] 使用统计正确显示
- [ ] 错误处理正常工作
- [ ] 节点数据自动刷新
- [ ] 多条消息对话正常

## 🎉 完成！

如果以上所有步骤都正常工作，说明前端 chatbot 功能已经完全准备好了！
