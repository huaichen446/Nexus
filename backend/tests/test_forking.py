"""
分叉功能测试

测试用例：
1. Sibling Strategy: 新节点继承相同的父节点，而不是成为源节点的子节点
2. Model Inheritance: 新节点继承相同的模型配置
3. Message Copying: 正确复制消息历史到目标消息（包含目标消息）
4. Independence: 源节点保持不变
5. Edge Case: 尝试在用户消息处分叉应该失败

python -m backend.tests.test_forking
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
from backend.app.core.engines.forking import forking_engine
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
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

from backend.app.database import Base
Base.metadata.create_all(bind=test_engine)

print("[OK] 已创建测试内存数据库（测试完成后自动销毁，不影响现有数据库）")


def create_test_node_with_messages(
    db: Session,
    messages: list,
    model: str = "gpt-4",
    parent_id: str = None,
    project_id: str = "test-project"
) -> AtomicNodeModel:
    """创建测试节点并添加消息历史"""
    node_id = str(uuid.uuid4())
    
    node_data = AtomicNodeCreate(
        id=node_id,
        project_id=project_id,
        parent_id=parent_id,
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
                model=model,
                temperature=0.7
            )
        ),
        author_id="test-user"
    )
    
    node = topology_service.create_node(db, node_data)
    return node


def test_sibling_strategy():
    """
    测试用例：Sibling Strategy
    
    场景：
    - Node A (Model='gpt-4', Parent=None)
    - Messages in Node A: [User_1, AI_2, User_3, AI_4]
    - Fork at AI_2
    
    期望：
    - 新节点 Node B 被创建
    - Node B 的 parent_node_id 是 None（与 Node A 相同），而不是 Node A 的 ID
    - Node B 的 model 是 'gpt-4'
    - Node B 有 2 条消息（User_1 和 AI_2 的副本）
    - Node A 保持不变（仍有 4 条消息）
    """
    print("\n" + "="*60)
    print("测试用例：Sibling Strategy")
    print("="*60)
    
    db = TestSessionLocal()
    try:
        # 1. 创建 Node A
        user_1_id = str(uuid.uuid4())
        ai_2_id = str(uuid.uuid4())
        user_3_id = str(uuid.uuid4())
        ai_4_id = str(uuid.uuid4())
        
        messages_a = [
            ChatMessage(
                id=user_1_id,
                role="user",
                content="Message User_1",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
            ChatMessage(
                id=ai_2_id,
                role="assistant",
                content="Response AI_2",
                timestamp=time.time() - 240,
                is_disabled=False
            ),
            ChatMessage(
                id=user_3_id,
                role="user",
                content="Message User_3",
                timestamp=time.time() - 180,
                is_disabled=False
            ),
            ChatMessage(
                id=ai_4_id,
                role="assistant",
                content="Response AI_4",
                timestamp=time.time() - 120,
                is_disabled=False
            ),
        ]
        
        messages_a_dict = [msg.model_dump() for msg in messages_a]
        node_a = create_test_node_with_messages(
            db, messages_a_dict, model="gpt-4", parent_id=None
        )
        print(f"[OK] 创建 Node A: {node_a.id}")
        print(f"   Parent ID: {node_a.parent_id}")
        print(f"   Model: {node_a.config['llm_settings']['model']}")
        print(f"   消息数量: {len(messages_a_dict)}")
        
        # 2. 在 AI_2 处分叉
        print(f"\n[TEST] 在消息 AI_2 (ID: {ai_2_id}) 处分叉")
        
        result = topology_service.fork_branch(
            db=db,
            node_id=node_a.id,
            message_id=ai_2_id,
            user_id="test-user"
        )
        
        new_node_id = result["new_node_id"]
        print(f"[OK] 创建新节点: {new_node_id}")
        
        # 3. 获取新节点
        node_b = topology_service.get_node(db, new_node_id)
        assert node_b is not None, "新节点应该存在"
        
        # 4. 验证 Parent Consistency (Sibling Strategy)
        print(f"\n[VERIFY] Parent Consistency (Sibling Strategy)")
        print(f"   Node A parent_id: {node_a.parent_id}")
        print(f"   Node B parent_id: {node_b.parent_id}")
        assert node_b.parent_id == node_a.parent_id, (
            f"Node B 的 parent_id ({node_b.parent_id}) 应该与 Node A 的 parent_id ({node_a.parent_id}) 相同"
        )
        assert node_b.parent_id is None, "两个节点都应该是根节点（parent_id=None）"
        assert node_b.parent_id != node_a.id, "Node B 不应该是 Node A 的子节点"
        print("[OK] Parent Consistency 验证通过：Node B 是 Node A 的兄弟节点")
        
        # 5. 验证 Model Inheritance
        print(f"\n[VERIFY] Model Inheritance")
        node_a_model = node_a.config["llm_settings"]["model"]
        node_b_model = node_b.config["llm_settings"]["model"]
        print(f"   Node A model: {node_a_model}")
        print(f"   Node B model: {node_b_model}")
        assert node_b_model == node_a_model, (
            f"Node B 的 model ({node_b_model}) 应该与 Node A 的 model ({node_a_model}) 相同"
        )
        assert node_b_model == "gpt-4", "Node B 的 model 应该是 'gpt-4'"
        print("[OK] Model Inheritance 验证通过：Node B 继承了 Node A 的模型配置")
        
        # 6. 验证 Message Content
        print(f"\n[VERIFY] Message Content")
        db.refresh(node_a)
        db.refresh(node_b)
        
        node_a_history = node_a.internal_state.get("chat_history", [])
        node_b_history = node_b.internal_state.get("chat_history", [])
        
        print(f"   Node A 消息数量: {len(node_a_history)}")
        print(f"   Node B 消息数量: {len(node_b_history)}")
        
        # Node A 应该保持不变
        assert len(node_a_history) == 4, f"Node A 应该有 4 条消息，实际 {len(node_a_history)}"
        
        # Node B 应该有 2 条消息（User_1 和 AI_2）
        assert len(node_b_history) == 2, f"Node B 应该有 2 条消息，实际 {len(node_b_history)}"
        
        # 验证消息内容
        assert node_b_history[0]["role"] == "user", "第一条消息应该是 user"
        assert node_b_history[0]["content"] == "Message User_1", "第一条消息内容应该是 User_1"
        assert node_b_history[1]["role"] == "assistant", "第二条消息应该是 assistant"
        assert node_b_history[1]["content"] == "Response AI_2", "第二条消息内容应该是 AI_2"
        
        print("[OK] Message Content 验证通过：Node B 有正确的消息历史")
        
        # 7. 验证 Independence (Deep Copy)
        print(f"\n[VERIFY] Independence (Deep Copy)")
        # 新节点的消息应该有新的 UUID
        node_b_msg_ids = [msg.get("id") for msg in node_b_history]
        node_a_msg_ids = [msg.get("id") for msg in node_a_history]
        
        # Node B 的消息 ID 不应该与 Node A 的消息 ID 相同（因为是深拷贝）
        assert node_b_msg_ids[0] != user_1_id, "Node B 的消息应该有新的 UUID"
        assert node_b_msg_ids[1] != ai_2_id, "Node B 的消息应该有新的 UUID"
        
        # Node A 的消息 ID 应该保持不变
        assert node_a_msg_ids[0] == user_1_id, "Node A 的消息 ID 应该保持不变"
        assert node_a_msg_ids[1] == ai_2_id, "Node A 的消息 ID 应该保持不变"
        
        print("[OK] Independence 验证通过：消息是深拷贝，有新的 UUID")
        
        # 8. 验证 fork_from_node_id
        print(f"\n[VERIFY] Fork From Node ID")
        assert node_b.fork_from_node_id == node_a.id, (
            f"Node B 的 fork_from_node_id ({node_b.fork_from_node_id}) 应该是 Node A 的 ID ({node_a.id})"
        )
        print("[OK] Fork From Node ID 验证通过")
        
        print("\n[OK] 所有 Sibling Strategy 测试通过！")
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        # 清理测试数据
        if 'node_a' in locals():
            try:
                db.delete(node_a)
                db.commit()
            except:
                pass
        if 'node_b' in locals():
            try:
                db.delete(node_b)
                db.commit()
            except:
                pass
        db.close()


def test_fork_at_user_message_should_fail():
    """
    测试用例：尝试在用户消息处分叉应该失败
    
    场景：
    - Node A: [User_1, AI_2]
    - 尝试在 User_1 处分叉
    
    期望：
    - 应该抛出 ValueError
    """
    print("\n" + "="*60)
    print("测试用例：尝试在用户消息处分叉应该失败")
    print("="*60)
    
    db = TestSessionLocal()
    try:
        # 1. 创建 Node A
        user_1_id = str(uuid.uuid4())
        ai_2_id = str(uuid.uuid4())
        
        messages_a = [
            ChatMessage(
                id=user_1_id,
                role="user",
                content="Message User_1",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
            ChatMessage(
                id=ai_2_id,
                role="assistant",
                content="Response AI_2",
                timestamp=time.time() - 240,
                is_disabled=False
            ),
        ]
        
        messages_a_dict = [msg.model_dump() for msg in messages_a]
        node_a = create_test_node_with_messages(db, messages_a_dict)
        print(f"[OK] 创建 Node A: {node_a.id}")
        
        # 2. 尝试在 User_1 处分叉（应该失败）
        print(f"\n[TEST] 尝试在用户消息 User_1 (ID: {user_1_id}) 处分叉")
        
        try:
            topology_service.fork_branch(
                db=db,
                node_id=node_a.id,
                message_id=user_1_id,
                user_id="test-user"
            )
            assert False, "应该在用户消息处分叉时抛出异常"
        except ValueError as e:
            error_msg = str(e).lower()
            assert "user" in error_msg or "role" in error_msg or "fork" in error_msg, (
                f"错误消息应该提到用户消息或角色问题，实际: {str(e)}"
            )
            print(f"[OK] 正确抛出异常: {str(e)}")
        
        print("[OK] 测试通过：在用户消息处分叉会抛出异常")
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        # 清理测试数据
        if 'node_a' in locals():
            try:
                db.delete(node_a)
                db.commit()
            except:
                pass
        db.close()


def test_fork_with_parent_node():
    """
    测试用例：有父节点时的 Sibling Strategy
    
    场景：
    - Parent Node (Root)
    - Node A (Parent=Parent Node, Model='gpt-4')
    - Messages in Node A: [User_1, AI_2]
    - Fork at AI_2
    
    期望：
    - 新节点 Node B 的 parent_id 应该是 Parent Node 的 ID（与 Node A 相同）
    """
    print("\n" + "="*60)
    print("测试用例：有父节点时的 Sibling Strategy")
    print("="*60)
    
    db = TestSessionLocal()
    try:
        # 1. 创建父节点
        parent_node = create_test_node_with_messages(
            db, [], model="gpt-3.5", parent_id=None
        )
        print(f"[OK] 创建父节点: {parent_node.id}")
        
        # 2. 创建 Node A（父节点是 Parent Node）
        user_1_id = str(uuid.uuid4())
        ai_2_id = str(uuid.uuid4())
        
        messages_a = [
            ChatMessage(
                id=user_1_id,
                role="user",
                content="Message User_1",
                timestamp=time.time() - 300,
                is_disabled=False
            ),
            ChatMessage(
                id=ai_2_id,
                role="assistant",
                content="Response AI_2",
                timestamp=time.time() - 240,
                is_disabled=False
            ),
        ]
        
        messages_a_dict = [msg.model_dump() for msg in messages_a]
        node_a = create_test_node_with_messages(
            db, messages_a_dict, model="gpt-4", parent_id=parent_node.id
        )
        print(f"[OK] 创建 Node A: {node_a.id}")
        print(f"   Parent ID: {node_a.parent_id}")
        
        # 3. 在 AI_2 处分叉
        result = topology_service.fork_branch(
            db=db,
            node_id=node_a.id,
            message_id=ai_2_id,
            user_id="test-user"
        )
        
        new_node_id = result["new_node_id"]
        print(f"[OK] 创建新节点: {new_node_id}")
        
        # 4. 验证 Parent Consistency
        node_b = topology_service.get_node(db, new_node_id)
        assert node_b is not None, "新节点应该存在"
        
        print(f"\n[VERIFY] Parent Consistency")
        print(f"   Parent Node ID: {parent_node.id}")
        print(f"   Node A parent_id: {node_a.parent_id}")
        print(f"   Node B parent_id: {node_b.parent_id}")
        
        assert node_b.parent_id == node_a.parent_id, (
            f"Node B 的 parent_id ({node_b.parent_id}) 应该与 Node A 的 parent_id ({node_a.parent_id}) 相同"
        )
        assert node_b.parent_id == parent_node.id, (
            f"Node B 的 parent_id ({node_b.parent_id}) 应该是父节点的 ID ({parent_node.id})"
        )
        
        print("[OK] Parent Consistency 验证通过：Node B 和 Node A 有相同的父节点")
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        # 清理测试数据
        if 'node_b' in locals():
            try:
                db.delete(node_b)
                db.commit()
            except:
                pass
        if 'node_a' in locals():
            try:
                db.delete(node_a)
                db.commit()
            except:
                pass
        if 'parent_node' in locals():
            try:
                db.delete(parent_node)
                db.commit()
            except:
                pass
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("开始分叉功能测试")
    print("="*60)
    
    try:
        # 运行测试
        test_sibling_strategy()
        test_fork_at_user_message_should_fail()
        test_fork_with_parent_node()
        
        print("\n" + "="*60)
        print("[OK] 所有测试通过！")
        print("="*60)
    except Exception as e:
        print("\n" + "="*60)
        print(f"[FAIL] 测试失败: {str(e)}")
        print("="*60)
        sys.exit(1)
