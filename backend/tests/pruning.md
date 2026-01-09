# 修剪功能测试文档

## 概述

本文档描述了修剪功能（Manual Pruning）的测试用例和实现细节。

## 功能说明

修剪功能允许用户删除或编辑历史消息。当用户删除消息 X 时，系统会删除 X 及其所有后续消息。当用户编辑消息 X 时，系统会删除 X 之后的所有消息，更新 X 的内容，然后重新生成响应。

## 测试用例

### 测试用例 1: 微修剪（线性截断）

**场景**：
- 创建对话历史: `[A(user), B(assistant), C(user), D(assistant)]`
- 删除消息 C
- **期望**: C 和 D 被删除，保留 `[A, B]`

**验证点**：
- ✅ 删除的消息数量 = 2（C 和 D）
- ✅ 剩余的消息数量 = 2（A 和 B）
- ✅ 消息 C 和 D 的 ID 不在剩余消息中
- ✅ 消息 A 和 B 的内容和顺序保持不变

### 测试用例 2: 边界情况

#### 2.1 删除第一条消息
- **场景**: 删除对话中的第一条消息
- **期望**: 清空所有消息（因为第一条消息被删除，后续所有消息也被删除）

#### 2.2 删除最后一条消息
- **场景**: 删除对话中的最后一条 user 消息
- **期望**: 只删除该消息（没有后续消息）

#### 2.3 删除不存在的消息
- **场景**: 尝试删除一个不存在的消息 ID
- **期望**: 抛出 `ValueError` 异常，提示消息未找到

#### 2.4 尝试删除 assistant 消息
- **场景**: 尝试删除 assistant 角色的消息
- **期望**: 抛出 `ValueError` 异常，提示只能删除 user 消息

## 运行测试

```bash
# 在项目根目录下运行
python -m backend.tests.test_pruning
```

## 实现细节

### 核心组件

1. **PruningEngine** (`backend/app/core/engines/pruning.py`)
   - `validate_message()`: 验证消息是否存在且符合要求
   - `prune_conversation()`: 执行修剪操作

2. **TopologyService** (`backend/app/services/topology_service.py`)
   - `prune_message()`: 服务层接口，处理事务和错误

3. **Messages Router** (`backend/app/routers/messages.py`)
   - `DELETE /nodes/{node_id}/messages/{message_id}`: 删除消息
   - `PATCH /nodes/{node_id}/messages/{message_id}`: 编辑消息并重新生成

### 数据流

1. **删除消息流程**:
   ```
   用户请求 → Router → Service → Engine → 数据库更新
   ```

2. **编辑消息流程**:
   ```
   用户请求 → Router → Engine (修剪) → 添加编辑后的消息 → ChatExecutor (重新生成) → 流式返回
   ```

### 事务处理

- 删除操作：在 Service 层提交事务
- 编辑操作：修剪和添加编辑后的消息在同一事务中，重新生成在另一个事务中（如果失败会回滚）

### 消息 ID 处理

- 新消息：在 `ChatExecutor._append_chat_message()` 中生成 UUID
- 编辑消息：保留原 `message_id`，更新 `timestamp` 和 `content`

## 注意事项

1. **只允许操作 user 消息**: 系统会验证消息的 role，只允许删除/编辑 user 消息
2. **包含目标消息**: 删除消息 X 时，X 本身也会被删除
3. **Token Cache 清理**: 修剪后会清除 `_history_token_cache`，下次聊天时重新计算
4. **时间戳更新**: 编辑后的消息使用新的 `timestamp`，但保留原 `message_id`
