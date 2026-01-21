# Nexus Chatbot 项目 - Agent 工作提示词

## 📋 项目概述

这是一个基于 FastAPI + React 的提示词工程 IDE 系统，核心功能是节点化的聊天机器人（Chatbot）。每个节点可以独立配置 LLM 模型和系统提示词，支持多轮对话和历史记录管理。

## 🏗️ 项目架构

### 后端 (Backend)
- **框架**: FastAPI (Python)
- **数据库**: SQLite (通过 SQLAlchemy ORM)
- **LLM 调用**: litellm (支持多提供商：OpenAI, Anthropic, 智谱AI 等)
- **流式输出**: SSE (Server-Sent Events)

### 前端 (Frontend)
- **框架**: React + TypeScript + Vite
- **UI 库**: Tailwind CSS + Framer Motion
- **状态管理**: React Hooks

### 核心概念

1. **AtomicNode (原子节点)**
   - 每个节点是一个独立的聊天单元
   - 包含：系统提示词、聊天历史、LLM 配置
   - 支持树形结构（父子节点关系）

2. **Chat History (聊天历史)**
   - 存储在 `node.internal_state.chat_history`
   - 包含 user 和 assistant 的完整对话记录
   - 每次对话都会追加新的消息

3. **Token 管理**
   - 自动计算消息的 token 数量
   - 支持缓存优化（历史 token 缓存）
   - Token 溢出检测（v1 版本：不自动修复，返回错误）

## 🔑 当前配置

### 智谱AI (GLM-4-Flash) 集成


**配置方式**:
```bash
# 设置环境变量
export ZHIPUAI_API_KEY=#####
```

**节点配置**:
```python
llm_settings = {
    "provider": "zhipuai",
    "model": "glm-4-flash",
    "temperature": 0.7,
    "max_tokens": 1024
}
```

**API 端点**: `https://open.bigmodel.cn/api/paas/v4/chat/completions`

**技术文档**: https://docs.bigmodel.cn/cn/guide/develop/http/introduction

## 📁 关键文件结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── models.py               # 数据库模型（AtomicNodeModel）
│   ├── schemas.py              # Pydantic 数据验证模型
│   ├── database.py             # 数据库连接配置
│   ├── routers/
│   │   ├── chat.py             # 聊天 API 路由
│   │   └── topology.py        # 节点管理 API 路由
│   └── services/
│       ├── chat_executor.py    # ⭐ 核心聊天执行器
│       └── topology_service.py # 节点管理服务
└── tests/
    ├── test_chatbot.py         # Chatbot 功能测试
    ├── test_zhipuai_api.py    # 智谱AI API 验证
    └── README_CHATBOT_TEST.md  # 测试指南

frontend/
├── src/
│   ├── api/
│   │   ├── chat.ts            # 聊天 API 调用
│   │   └── topology.ts        # 节点管理 API
│   ├── components/
│   │   └── topology/
│   │       ├── NodeChatPanel.tsx      # ⭐ 聊天 UI 组件
│   │       └── NodeDetailPanel.tsx    # 节点详情面板
│   └── types/
│       └── node.ts            # TypeScript 类型定义
└── README_CHATBOT.md          # 前端验证指南
```

## 🎯 核心功能实现

### 1. 消息构建 (`_build_messages`)

**位置**: `backend/app/services/chat_executor.py:123-251`

**职责**:
- 拼接 system message + history (user + assistant) + current user
- 计算 token 数量（支持缓存优化）
- 检测 token 溢出（不自动修复，返回错误）

**关键逻辑**:
```python
# 1. 从节点获取历史记录（包含 user 和 assistant）
history = internal_state.get("chat_history", [])

# 2. 转换历史消息格式（保留所有消息，包括 assistant）
for msg in history:
    role = msg.get("role")  # "user" 或 "assistant"
    history_messages.append({"role": role, "content": msg.get("content", "")})

# 3. 拼接：system + history + current user
messages = [system_message] + history_messages + [latest_user_message]

# 4. 计算 token（包含所有消息，包括 assistant 的回答）
total_tokens = self._count_tokens(messages, model_name)
```

**重要**: 
- ✅ 历史记录包含 user 和 assistant 的所有消息
- ✅ Token 计算包含所有消息（包括 assistant 的回答）
- ✅ 使用缓存优化：只计算新增部分（system + current user）

### 2. 流式聊天 (`stream_chat_completion`)

**位置**: `backend/app/services/chat_executor.py:390-516`

**流程**:
1. 构建消息列表
2. 检查 token 溢出（如果溢出，返回错误）
3. 保存用户消息到 `chat_history`
4. 调用 litellm 流式 API
5. 实时流式返回给前端（SSE 格式）
6. 保存 assistant 消息到 `chat_history`
7. 返回使用统计

**SSE 格式**:
```
data: {"delta": "文本片段"}\n\n
data: {"delta": "更多文本"}\n\n
data: {"event": "done", "usage": {...}}\n\n
```

### 3. 智谱AI 集成

**模型名称格式**: `glm-4-flash` (在节点配置中使用)

**环境变量**: `ZHIPUAI_API_KEY`

**实现方式**: 直接 HTTP 调用（不使用 litellm）
- litellm 不支持智谱AI格式，因此使用直接的 HTTP 请求
- 代码位置: `_zhipuai_stream_completion()` 方法
- API 端点: `https://open.bigmodel.cn/api/paas/v4/chat/completions`
- 支持流式输出（SSE 格式）
- 自动从环境变量读取 `ZHIPUAI_API_KEY`

## 🧪 测试验证

### 1. API Key 验证

运行测试脚本验证 API Key:
```bash
python backend/tests/test_zhipuai_api.py
```

**测试内容**:
- ✅ 直接 API 调用（使用 requests）
- ✅ litellm 调用
- ✅ 流式响应
- ✅ 多轮对话

### 2. Chatbot 功能测试

运行完整功能测试:
```bash
# 设置环境变量
export ZHIPUAI_API_KEY=####

# 运行测试
python backend/tests/test_chatbot.py
```

### 3. 前端验证

1. 启动后端: `cd backend && python -m uvicorn app.main:app --reload`
2. 启动前端: `cd frontend && npm run dev`
3. 打开浏览器: `http://localhost:5173`
4. 创建节点并测试聊天功能

## 🔧 开发工作流

### 创建测试节点

```python
from backend.app.schemas import AtomicNodeCreate, NodeInternalState, NodeInputContext, NodeOutputArtifact, NodeExecutionConfig, LlmSettings

node_data = AtomicNodeCreate(
    id="test-node-1",
    project_id="test-project",
    parent_id=None,
    input_context=NodeInputContext(content="Test input"),
    output_artifact=NodeOutputArtifact(content="", mime_type="text/plain", status="empty"),
    internal_state=NodeInternalState(
        system_instruction="你是一个友好的助手。",
        chat_history=[],
        variables={}
    ),
    config=NodeExecutionConfig(
        execution_mode="manual",
        llm_settings=LlmSettings(
            provider="zhipuai",
            model="glm-4-flash",
            temperature=0.7,
            max_tokens=1024
        )
    ),
    author_id="test-user"
)
```

### 调用聊天 API

```bash
curl -X POST "http://localhost:8000/nodes/{node_id}/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"content": "你好"}' \
  --no-buffer
```

## ⚠️ 重要注意事项

### 1. Token 溢出处理

**v1 设计原则**: 不自动修复，明确失败

- 如果 `total_tokens > max_tokens`，返回 `overflow=True`
- **不**自动截断历史
- **不**自动总结消息
- **不**删除任何消息
- 调用方必须处理溢出状态

### 2. 历史记录完整性

- `chat_history` 包含**所有**历史消息（user + assistant）
- Token 计算包含**所有**消息（包括 assistant 的回答）
- 缓存优化只计算新增部分，但历史包含完整对话

### 3. output_artifact

**当前状态**: Chatbot 功能不使用

- Chatbot 功能**不**更新 `output_artifact`
- 只保存到 `chat_history`
- `output_artifact` 用于节点间的数据传递（当前 chatbot 功能不使用）
- 创建节点时仍需要提供 `output_artifact`（数据结构要求），但不会被 chatbot 更新

### 4. 环境变量

**必须设置**:
```bash
# Windows PowerShell
$env:ZHIPUAI_API_KEY="443c25f8fad94dc7aa6b2594fff2808c.TVfiGGDtRLdth2qX"

# Linux/Mac
export ZHIPUAI_API_KEY=443c25f8fad94dc7aa6b2594fff2808c.TVfiGGDtRLdth2qX

# 或在项目根目录创建 .env 文件
echo "ZHIPUAI_API_KEY=443c25f8fad94dc7aa6b2594fff2808c.TVfiGGDtRLdth2qX" > .env
```

**litellm 自动读取**: litellm 会自动从环境变量读取 `ZHIPUAI_API_KEY`

**验证环境变量**:
```bash
# Windows PowerShell
echo $env:ZHIPUAI_API_KEY

# Linux/Mac
echo $ZHIPUAI_API_KEY
```

## 🐛 常见问题排查

### 1. API Key 验证失败

**症状**: `litellm.exceptions.AuthenticationError`

**解决**:
- 检查环境变量: `echo $ZHIPUAI_API_KEY`
- 运行验证脚本: `python backend/tests/test_zhipuai_api.py`
- 确认 API Key 格式正确

### 2. 模型名称错误

**症状**: `Model not found` 或调用失败

**解决**:
- 检查 provider 配置: `provider="zhipuai"`
- 检查 model 配置: `model="glm-4-flash"` (不需要 `zhipuai/` 前缀)
- 检查环境变量: `ZHIPUAI_API_KEY` 是否设置
- 智谱AI 使用直接 HTTP 调用，不通过 litellm

### 3. Token 溢出

**症状**: `Token limit exceeded`

**解决**:
- 减少 `system_instruction` 长度
- 清理 `chat_history`
- 增加 `max_tokens` 设置
- 或实现 v2 版本的自动截断（当前 v1 不支持）

### 4. 流式输出不工作

**症状**: 前端收不到流式数据

**检查**:
- 后端日志: 是否调用了 litellm
- 网络请求: 检查 SSE 响应头
- 前端代码: 检查 SSE 解析逻辑

## 📚 代码阅读指南

### 理解消息流程

1. **前端发送**: `NodeChatPanel.tsx` → `chat.ts` → POST `/nodes/{id}/chat/stream`
2. **路由处理**: `routers/chat.py` → `chat_executor.stream_chat_completion()`
3. **消息构建**: `_build_messages()` → 拼接 system + history + current user
4. **LLM 调用**: `litellm.completion()` → 流式返回
5. **保存历史**: `_append_chat_message()` → 更新 `chat_history` 和缓存

### 理解 Token 计算

1. **首次调用**: 完整计算所有消息的 token
2. **后续调用**: 使用缓存的历史 token + 计算新增部分
3. **缓存更新**: 每次保存消息后更新缓存

### 理解数据存储

- **chat_history**: `node.internal_state.chat_history` (JSON 字段)
- **缓存**: `node.internal_state._history_token_cache` (内部字段)
- **不存储**: `output_artifact` (已移除相关功能)

## 🎓 学习路径

### 新手入门

1. 阅读 `backend/tests/test_zhipuai_api.py` - 理解 API 调用
2. 阅读 `backend/app/services/chat_executor.py` - 理解核心逻辑
3. 阅读 `frontend/src/components/topology/NodeChatPanel.tsx` - 理解前端实现

### 深入理解

1. 研究 `_build_messages` 的 token 缓存机制
2. 研究 SSE 流式输出的实现
3. 研究 litellm 的多提供商支持

## 🔗 相关资源

- **智谱AI 文档**: https://docs.bigmodel.cn/cn/guide/develop/http/introduction
- **litellm 文档**: https://docs.litellm.ai/
- **FastAPI 文档**: https://fastapi.tiangolo.com/
- **React 文档**: https://react.dev/

## ✅ 验证清单

在开始开发前，确保：

- [ ] API Key 已验证（运行 `test_zhipuai_api.py`）
- [ ] 环境变量已设置（`ZHIPUAI_API_KEY`）
- [ ] 数据库已初始化（`nexus.db` 存在）
- [ ] 依赖已安装（`pip install -r requirements.txt`）
- [ ] 后端服务器可启动（`uvicorn app.main:app --reload`）
- [ ] 前端服务器可启动（`npm run dev`）

## 🚀 快速开始

```bash
# 1. 设置环境变量
export ZHIPUAI_API_KEY=443c25f8fad94dc7aa6b2594fff2808c.TVfiGGDtRLdth2qX

# 2. 验证 API Key
python backend/tests/test_zhipuai_api.py

# 3. 启动后端
cd backend
python -m uvicorn app.main:app --reload

# 4. 启动前端（新终端）
cd frontend
npm run dev

# 5. 打开浏览器
# http://localhost:5173
```

---
**版本**: v1.0
