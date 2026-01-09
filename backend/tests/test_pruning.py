"""
修剪功能测试

测试用例：
1. 微修剪（线性截断）：删除消息及其后续消息
2. 边界情况：删除第一条消息、最后一条消息等
"""

import os
import sys
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from backend.app.models import AtomicNodeModel
from backend.app.services.topology_service import topology_service
from backend.app.core.engines.pruning import pruning_engine
from backend.app.schemas import (
    AtomicNodeCreate,
    NodeInternalState,
    NodeInputContext,
    NodeOutputArtifact,
    NodeExecutionConfig,
    LlmSettings,
    ChatMessage
)

# 设置项目路径
current_file = Path(__file__).resolve()
project_root = current_file.parents[2]
sys.path.insert(0, str(project_root))

# 加载环境变量
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[OK] 已加载 .env 文件: {env_path}")
else:
    print(f"[WARN] 未找到 .env 文件，路径: {env_path}")

load_dotenv()

# ==========================================
# 创建测试专用的内存数据库
# ==========================================
# 使用 SQLite 内存数据库，测试完成后自动销毁，不影响现有数据库
TEST_DATABASE_URL = "sqlite:///:memory:"

# 创建测试数据库引擎
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# 创建测试数据库会话工厂
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

# 获取 Base（从 database 导入，确保使用相同的 Base 和模型定义）
from backend.app.database import Base

# 在内存数据库中创建所有表
# 注意：SQLite 内存数据库（:memory:）在连接关闭后会自动销毁，无需手动清理
# 这确保了测试不会影响现有的 nexus.db 文件
Base.metadata.create_all(bind=test_engine)

print("[OK] 已创建测试内存数据库（测试完成后自动销毁，不影响现有数据库）")


def create_test_node_with_messages(db: Session, messages: list) -> AtomicNodeModel:
    """创建测试节点并添加消息历史"""
    node_id = str(uuid.uuid4())
    project_id = "test-project"
    
    # 创建节点
    node_data = AtomicNodeCreate(
        id=node_id,
        project_id=project_id,
        parent_id=None,
        input_context=NodeInputContext(content="", meta={}),
        output_artifact=NodeOutputArtifact(
            content="",
            mime_type="text/plain",
            status="empty"
        ),
        internal_state=NodeInternalState(
            system_instruction="You are a helpful assistant.",
            chat_history=messages,
            variables={}
        ),
        config=NodeExecutionConfig(
            execution_mode="manual",
            llm_settings=LlmSettings(
                provider="openai",
                model="gpt-4o",
                temperature=0.7
            )
        ),
        author_id="test-user"
    )
    
    node = topology_service.create_node(db, node_data)
    return node


def test_micro_pruning_linear_truncation():
    """
    测试用例 2: 微修剪（线性截断）
    
    场景：
    - 创建对话历史: [A(user), B(assistant), C(user), D(assistant)]
    - 删除消息 C
    - 期望: C 和 D 被删除，保留 [A, B]
    """
    print("\n" + "="*60)
    print("测试用例 2: 微修剪（线性截断）")
    print("="*60)
    
    db = TestSessionLocal()
    try:
        # 1. 创建测试数据
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                role="user",
                content="Message A",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Response B",
                timestamp=time.time() - 240,
                is_disabled=False
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                role="user",
                content="Message C",
                timestamp=time.time() - 180,
                is_disabled=False
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Response D",
                timestamp=time.time() - 120,
                is_disabled=False
            ),
        ]
        
        # 转换为字典格式（因为数据库存储的是字典）
        messages_dict = [msg.model_dump() for msg in messages]
        
        node = create_test_node_with_messages(db, messages_dict)
        print(f"[OK] 创建测试节点: {node.id}")
        print(f"   初始消息数量: {len(messages_dict)}")
        
        # 2. 执行修剪（删除消息 C）
        message_c_id = messages[2].id
        print(f"\n[TEST] 删除消息 C (ID: {message_c_id})")
        
        result = topology_service.prune_message(
            db=db,
            node_id=node.id,
            message_id=message_c_id
        )
        
        # 3. 验证结果
        db.refresh(node)
        remaining_history = node.internal_state.get("chat_history", [])
        
        print(f"\n[RESULT] 修剪结果:")
        print(f"   - 删除的消息数量: {result['deleted_count']}")
        print(f"   - 剩余的消息数量: {result['remaining_messages']}")
        print(f"   - 实际剩余消息: {len(remaining_history)}")
        
        # 验证：应该只剩下 A 和 B
        assert len(remaining_history) == 2, f"期望剩余 2 条消息，实际 {len(remaining_history)}"
        assert remaining_history[0]["content"] == "Message A", "第一条消息应该是 A"
        assert remaining_history[1]["content"] == "Response B", "第二条消息应该是 B"
        
        # 验证消息 C 和 D 已被删除
        remaining_ids = [msg.get("id") for msg in remaining_history]
        assert message_c_id not in remaining_ids, "消息 C 应该被删除"
        assert messages[3].id not in remaining_ids, "消息 D 应该被删除"
        
        print("[OK] 测试通过：消息 C 和 D 已删除，保留 A 和 B")
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        # 清理测试数据
        if 'node' in locals():
            try:
                db.delete(node)
                db.commit()
                print(f"[CLEAN] 清理测试节点: {node.id}")
            except:
                pass
        db.close()


def test_pruning_edge_cases():
    """测试边界情况"""
    print("\n" + "="*60)
    print("测试边界情况")
    print("="*60)
    
    db = TestSessionLocal()
    try:
        # 测试 1: 删除第一条消息（应该清空所有消息）
        print("\n[TEST] 测试 1: 删除第一条消息")
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                role="user",
                content="First message",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Response",
                timestamp=time.time() - 240,
                is_disabled=False
            ),
        ]
        messages_dict = [msg.model_dump() for msg in messages]
        node = create_test_node_with_messages(db, messages_dict)
        
        result = topology_service.prune_message(
            db=db,
            node_id=node.id,
            message_id=messages[0].id
        )
        
        db.refresh(node)
        remaining_history = node.internal_state.get("chat_history", [])
        
        assert len(remaining_history) == 0, "删除第一条消息后应该清空所有消息"
        assert result["deleted_count"] == 2, "应该删除 2 条消息"
        print("[OK] 测试通过：删除第一条消息清空所有消息")
        
        # 清理
        db.delete(node)
        db.commit()
        
        # 测试 2: 删除最后一条消息（只删除最后一条）
        print("\n[TEST] 测试 2: 删除最后一条 user 消息")
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                role="user",
                content="Message 1",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Response 1",
                timestamp=time.time() - 240,
                is_disabled=False
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                role="user",
                content="Message 2",
                timestamp=time.time() - 180,
                is_disabled=False
            ),
        ]
        messages_dict = [msg.model_dump() for msg in messages]
        node = create_test_node_with_messages(db, messages_dict)
        
        result = topology_service.prune_message(
            db=db,
            node_id=node.id,
            message_id=messages[2].id
        )
        
        db.refresh(node)
        remaining_history = node.internal_state.get("chat_history", [])
        
        assert len(remaining_history) == 2, "应该保留前 2 条消息"
        assert result["deleted_count"] == 1, "应该只删除 1 条消息"
        print("[OK] 测试通过：删除最后一条消息只删除该消息")
        
        # 清理
        db.delete(node)
        db.commit()
        
        # 测试 3: 尝试删除不存在的消息
        print("\n[TEST] 测试 3: 删除不存在的消息")
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                role="user",
                content="Message",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
        ]
        messages_dict = [msg.model_dump() for msg in messages]
        node = create_test_node_with_messages(db, messages_dict)
        
        try:
            topology_service.prune_message(
                db=db,
                node_id=node.id,
                message_id="non-existent-id"
            )
            assert False, "应该抛出异常"
        except ValueError as e:
            assert "not found" in str(e).lower(), "应该返回消息未找到的错误"
            print("[OK] 测试通过：删除不存在的消息会抛出异常")
        
        # 清理
        db.delete(node)
        db.commit()
        
        # 测试 4: 尝试删除 assistant 消息（应该失败）
        print("\n[TEST] 测试 4: 尝试删除 assistant 消息")
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                role="user",
                content="Message",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Response",
                timestamp=time.time() - 240,
                is_disabled=False
            ),
        ]
        messages_dict = [msg.model_dump() for msg in messages]
        node = create_test_node_with_messages(db, messages_dict)
        
        try:
            topology_service.prune_message(
                db=db,
                node_id=node.id,
                message_id=messages[1].id  # assistant 消息
            )
            assert False, "应该抛出异常"
        except ValueError as e:
            assert "role" in str(e).lower() or "cannot" in str(e).lower(), "应该返回角色不符合的错误"
            print("[OK] 测试通过：删除 assistant 消息会抛出异常")
        
        # 清理
        db.delete(node)
        db.commit()
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("开始修剪功能测试")
    print("="*60)
    
    try:
        # 运行测试
        test_micro_pruning_linear_truncation()
        test_pruning_edge_cases()
        
        print("\n" + "="*60)
        print("[OK] 所有测试通过！")
        print("="*60)
    except Exception as e:
        print("\n" + "="*60)
        print(f"[FAIL] 测试失败: {str(e)}")
        print("="*60)
        sys.exit(1)
