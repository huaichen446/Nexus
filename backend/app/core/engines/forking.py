"""
分叉引擎 (Forking Engine)

负责处理对话历史的分叉逻辑（Deep Branching）。
当用户在某个 LLM 响应处创建新分支时，会创建一个新的节点，继承相同的父节点（Sibling Strategy），
并复制从开始到目标消息的所有消息历史。
"""

import logging
import uuid
from typing import List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.models import AtomicNodeModel

logger = logging.getLogger(__name__)


class ForkingEngine:
    """
    分叉引擎：处理对话历史的分叉操作。
    
    核心功能：
    1. 验证目标消息是否存在且为 LLM 响应（不允许在用户消息处分叉）
    2. 创建新节点（Sibling Strategy：继承相同的父节点）
    3. 复制模型配置
    4. 复制并截断消息历史（从开始到目标消息，包含目标消息）
    5. 为所有消息生成新的 UUID
    """

    def validate_message(
        self,
        node: AtomicNodeModel,
        message_id: str,
        allowed_roles: List[str] = ["assistant", "system"]
    ) -> Tuple[Dict[str, Any], int]:
        """
        验证消息是否存在且符合要求。
        
        Args:
            node: 节点对象
            message_id: 消息 ID
            allowed_roles: 允许的角色列表（默认只允许 "assistant" 和 "system"）
        
        Returns:
            (message_dict, index) - 消息字典和在数组中的索引
        
        Raises:
            ValueError: 如果消息不存在或角色不符合要求
        """
        internal_state: Dict[str, Any] = node.internal_state or {}
        history: List[Dict[str, Any]] = internal_state.get("chat_history", []) or []
        
        # 查找消息
        for index, msg in enumerate(history):
            if msg.get("id") == message_id:
                # 验证角色
                role = msg.get("role", "")
                if role not in allowed_roles:
                    raise ValueError(
                        f"Cannot fork at message with role '{role}'. "
                        f"Forking is only allowed on LLM responses (assistant/system). "
                        f"Allowed roles: {allowed_roles}"
                    )
                return msg, index
        
        # 消息未找到
        raise ValueError(f"Message {message_id} not found in node {node.id}")

    def fork_conversation(
        self,
        db: Session,
        source_node_id: str,
        target_message_id: str,
        user_id: str
    ) -> str:
        """
        分叉对话：基于源节点创建新节点，复制消息历史到目标消息（包含目标消息）。
        
        Args:
            db: 数据库会话
            source_node_id: 源节点 ID
            target_message_id: 目标消息 ID（分叉点）
            user_id: 用户 ID（新节点的创建者）
        
        Returns:
            str: 新节点的 ID
        
        Raises:
            ValueError: 如果节点或消息不存在，或消息不符合要求
        """
        # 1. 获取源节点
        source_node = db.query(AtomicNodeModel).filter(
            AtomicNodeModel.id == source_node_id
        ).first()
        
        if not source_node:
            raise ValueError(f"Source node {source_node_id} not found")
        
        # 2. 验证目标消息（必须是 LLM 响应，不能是用户消息）
        target_msg, target_index = self.validate_message(
            source_node,
            target_message_id,
            allowed_roles=["assistant", "system"]  # 只允许在 LLM 响应处分叉
        )
        
        # 3. 获取源节点的消息历史
        internal_state: Dict[str, Any] = source_node.internal_state or {}
        history: List[Dict[str, Any]] = list(internal_state.get("chat_history", []) or [])
        
        # 4. 截取消息历史（从开始到目标消息，包含目标消息）
        ancestor_messages = history[:target_index + 1]
        
        # 5. 深拷贝消息并生成新的 UUID
        copied_messages = []
        for msg in ancestor_messages:
            # 创建消息的深拷贝
            new_msg = dict(msg)
            # 生成新的 UUID
            new_msg["id"] = str(uuid.uuid4())
            # 保留其他字段（role, content, timestamp, is_disabled 等）
            copied_messages.append(new_msg)
        
        # 6. 准备新节点的数据
        # 6.1 模型配置：复制源节点的模型配置
        config: Dict[str, Any] = dict(source_node.config or {})
        
        # 6.2 内部状态：复制系统指令和变量，但使用新的消息历史
        new_internal_state: Dict[str, Any] = dict(internal_state)
        new_internal_state["chat_history"] = copied_messages
        # 清除 token cache（因为历史已改变）
        if "_history_token_cache" in new_internal_state:
            del new_internal_state["_history_token_cache"]
        
        # 6.3 输入上下文：复制源节点的输入上下文
        input_context: Dict[str, Any] = dict(source_node.input_context or {})
        
        # 6.4 输出产物：初始化为空状态
        output_artifact: Dict[str, Any] = {
            "content": "",
            "mime_type": "text/plain",
            "status": "empty"
        }
        
        # 6.5 计算深度（与源节点相同，因为是兄弟节点）
        depth = source_node.depth
        
        # 6.6 父节点 ID（Sibling Strategy：使用相同的父节点）
        parent_id = source_node.parent_id
        
        # 6.7 项目 ID
        project_id = source_node.project_id
        
        # 7. 创建新节点
        new_node_id = str(uuid.uuid4())
        new_node = AtomicNodeModel(
            id=new_node_id,
            project_id=project_id,
            parent_id=parent_id,  # Sibling Strategy: 相同的父节点
            children_ids=[],  # 新节点还没有子节点
            depth=depth,  # 与源节点相同的深度
            
            # Versioning
            fork_from_node_id=source_node_id,  # 记录分叉来源
            version_hash="fork_v1",  # 初始版本号
            tags=[],  # 可以后续添加标签
            
            # Nested JSON Structures
            input_context=input_context,
            output_artifact=output_artifact,
            internal_state=new_internal_state,
            config=config,
            
            # Metadata
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            author_id=user_id,
            
            # Status
            node_status="active"
        )
        
        # 8. 如果新节点有父节点，需要更新父节点的 children_ids
        if parent_id:
            parent_node = db.query(AtomicNodeModel).filter(
                AtomicNodeModel.id == parent_id
            ).with_for_update().first()
            
            if parent_node:
                current_children = list(parent_node.children_ids) if parent_node.children_ids else []
                if new_node_id not in current_children:
                    current_children.append(new_node_id)
                    parent_node.children_ids = current_children
                    db.add(parent_node)
        
        # 9. 保存新节点
        db.add(new_node)
        # 注意：不在这里 commit，由调用者负责事务管理
        
        logger.info(
            f"Forked conversation from node {source_node_id} at message {target_message_id}: "
            f"created new node {new_node_id} with {len(copied_messages)} messages"
        )
        
        return new_node_id


# 单例导出
forking_engine = ForkingEngine()
