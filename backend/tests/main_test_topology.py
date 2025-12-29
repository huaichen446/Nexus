import os
import uuid
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.schemas import (
    AtomicNode, NodeInputContext, NodeOutputArtifact, 
    NodeInternalState, NodeExecutionConfig, LlmSettings, 
    AutomationRules, ChatMessage
)
from backend.app.services.topology_service import topology_service

# ================= Configuration =================
# 开关：True 使用内存库（CI/自动测试），False 使用文件库（方便用 DB Browser 查看数据）
USE_MEMORY_DB = True

if USE_MEMORY_DB:
    DATABASE_URL = "sqlite:///:memory:"
else:
    # 每次运行前清理旧文件，保证幂等性
    if os.path.exists("./test_debug.db"):
        os.remove("./test_debug.db")
    DATABASE_URL = "sqlite:///./test_debug.db"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= Setup =================
def get_test_db():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    # autocommit=True is often safer when the code under test uses 'with db.begin():' explicitly,
    # because 'autocommit=False' (default) implicitly starts a transaction on first access,
    # which conflicts with 'db.begin()'.
    # However, production uses autocommit=False.
    # In SA 1.4+, 'with db.begin()' on an autocommit=False session works IF no transaction is in progress.
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal()

def create_mock_node_data(parent_id=None, node_id=None) -> AtomicNode:
    """Helper to create valid Pydantic node data"""
    if not node_id:
        node_id = str(uuid.uuid4())
        
    return AtomicNode(
        id=node_id,
        project_id="test_project_alpha",
        parent_id=parent_id,
        children_ids=[],
        depth=0, # Service should calculate this, but schema requires it. We pass 0.
        version_hash="hash_v1",
        input_context=NodeInputContext(
            content="Test input",
            meta={"token_count": 10}
        ),
        output_artifact=NodeOutputArtifact(
            content="Pending output",
            mime_type="text/plain",
            status="empty"
        ),
        internal_state=NodeInternalState(
            system_instruction="You are a test bot.",
            chat_history=[],
            variables={}
        ),
        config=NodeExecutionConfig(
            execution_mode="manual",
            llm_settings=LlmSettings(
                provider="openai",
                model="gpt-4",
                temperature=0.7
            )
        ),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        author_id="tester_01"
    )


def run_tests():
    logger.info(f"🚀 Starting Topology Tests (Mode: {'MEMORY' if USE_MEMORY_DB else 'FILE'})...")
    db = get_test_db()

    try:
        # [Test 1] Create Root
        logger.info("--- Test 1: Root Node ---")
        root_data = create_mock_node_data(parent_id=None)
        root_db = topology_service.create_node_from_full_data(db, root_data)
        assert root_db.depth == 0
        logger.info("Root created successfully.")

        # [Test 2] Create Child
        logger.info("--- Test 2: Child Node ---")
        child_data = create_mock_node_data(parent_id=root_data.id)
        child_db = topology_service.create_node_from_full_data(db, child_data)

        # 验证深度
        assert child_db.depth == 1
        # 验证父节点关联
        # 关键：必须 refresh root 才能看到 JSON 字段的更新
        db.refresh(root_db)
        assert child_data.id in root_db.children_ids
        logger.info("Child created and Parent adjacency list updated.")

        # [Test 3] Ancestor Chain
        logger.info("--- Test 3: Ancestor Chain ---")
        chain = topology_service.get_ancestor_chain(db, child_db.id)
        # 预期: [Root, Child]
        assert len(chain) == 2
        assert chain[0].id == root_data.id
        assert chain[1].id == child_data.id
        logger.info("✅ Ancestor chain verified.")

    except AssertionError as e:
        logger.error(f"Assertion Failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        raise
    finally:
        db.close()
        logger.info("Tests Finished.")


if __name__ == "__main__":
    run_tests()