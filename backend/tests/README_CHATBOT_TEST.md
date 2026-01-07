# Chatbot 功能验证指南

## 功能完整性检查

### ✅ 已完成的功能

1. **消息构建** (`_build_messages`)
   - ✅ 拼接 system + history + current user
   - ✅ 计算 token 数量
   - ✅ Token 溢出检测
   - ✅ 缓存优化（历史 token 缓存）

2. **流式聊天** (`stream_chat_completion`)
   - ✅ SSE 流式输出
   - ✅ 保存用户和助手消息到历史
   - ✅ 使用统计（tokens, cost, latency）

3. **API 端点** (`/nodes/{node_id}/chat/stream`)
   - ✅ POST 接口
   - ✅ 流式响应
   - ✅ 错误处理

### ⚠️ 需要验证的点

1. **环境变量配置**
   - 需要设置 LLM API Key（OpenAI/Anthropic/Google 等）
   - litellm 会自动读取环境变量

2. **Node 数据结构**
   - 确保 node 存在
   - 确保 `internal_state.system_instruction` 存在
   - 确保 `config.llm_settings` 配置正确

3. **数据库连接**
   - SQLite 数据库文件 `nexus.db` 需要可写

## 验证步骤

### 方法 1: 使用测试脚本（推荐）

```bash
# 1. 设置环境变量
export OPENAI_API_KEY=your_api_key_here
# 或者在项目根目录创建 .env 文件：
# OPENAI_API_KEY=your_api_key_here

# 2. 运行测试脚本
python backend/test_chatbot.py
```

### 方法 2: 使用 API 测试

#### 步骤 1: 启动服务器

```bash
cd backend
python -m uvicorn app.main:app --reload
```

#### 步骤 2: 创建测试节点

```bash
curl -X POST "http://localhost:8000/nodes/" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-node-1",
    "project_id": "test-project",
    "parent_id": null,
    "input_context": {
      "content": "Test input"
    },
    "output_artifact": {
      "content": "",
      "mime_type": "text/plain",
      "status": "empty"
    },
    "internal_state": {
      "system_instruction": "你是一个友好的助手。",
      "chat_history": [],
      "variables": {}
    },
    "config": {
      "execution_mode": "manual",
      "llm_settings": {
        "provider": "zhipuai",
        "model": "glm-4-flash",
        "temperature": 0.7,
        "max_tokens": 1024
      }
    },
    "author_id": "test-user"
  }'
```

#### 步骤 3: 测试聊天接口

```bash
curl -X POST "http://localhost:8000/nodes/test-node-1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"content": "你好"}' \
  --no-buffer
```

### 方法 3: 使用 Python 客户端

```python
import requests
import json

# 1. 创建节点（使用上面的 curl 命令或 API）

# 2. 测试聊天
node_id = "test-node-1"
url = f"http://localhost:8000/nodes/{node_id}/chat/stream"

response = requests.post(
    url,
    json={"content": "你好"},
    stream=True
)

for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            data = json.loads(line_str[6:])
            if 'delta' in data:
                print(data['delta'], end='', flush=True)
            elif data.get('event') == 'done':
                print(f"\n\n完成！使用统计: {data.get('usage')}")
```

## 常见问题排查

### 1. API Key 未设置

**错误**: `litellm.exceptions.AuthenticationError`

**解决**: 
```bash
export OPENAI_API_KEY=your_key
# 或创建 .env 文件
```

### 2. Node 不存在

**错误**: `404: Node {node_id} not found`

**解决**: 先创建节点，确保 node_id 正确

### 3. Token 溢出

**错误**: `Token limit exceeded`

**解决**: 
- 减少 `max_tokens` 设置
- 减少 `system_instruction` 长度
- 清理 `chat_history`

### 4. 数据库错误

**错误**: `sqlite3.OperationalError`

**解决**: 
- 确保 `nexus.db` 文件可写
- 检查数据库文件权限

## 代码检查清单

- [x] `_build_messages` 正确拼接消息
- [x] `stream_chat_completion` 正确处理流式输出
- [x] `_append_chat_message` 正确保存历史
- [x] Token 计算和缓存逻辑
- [x] 错误处理（token 溢出、LLM 调用失败）
- [x] API 路由注册
- [ ] 环境变量配置（需要用户设置）
- [ ] 数据库初始化（首次运行需要）

## 预期行为

1. **第一次对话**:
   - 用户: "你好"
   - 系统构建: `[system] + [当前 user]`
   - LLM 响应
   - 保存: `[user: "你好", assistant: "..."`

2. **第二次对话**:
   - 用户: "请介绍一下你自己"
   - 系统构建: `[system] + [历史 user, 历史 assistant] + [当前 user]`
   - LLM 响应（应该记住之前的对话）
   - 保存: 追加到历史

3. **Token 缓存**:
   - 第一次: 完整计算所有 token
   - 第二次: 使用缓存的历史 token，只计算新增部分
