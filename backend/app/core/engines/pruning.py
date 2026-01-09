"""
修剪引擎 (Pruning Engine)

负责处理对话历史的修剪逻辑（Micro-Pruning）。
当用户删除或编辑消息时，需要删除目标消息及其所有后续消息。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.models import AtomicNodeModel

logger = logging.getLogger(__name__)


class PruneResult:
    """修剪操作的结果"""
    def __init__(
        self,
        deleted_count: int,
        remaining_messages: List[Dict[str, Any]],
        target_index: int
    ):
        self.deleted_count = deleted_count
        self.remaining_messages = remaining_messages
        self.target_index = target_index


class PruningEngine:
    """
    修剪引擎：处理对话历史的修剪操作。
    
    核心功能：
    1. 验证消息是否存在且符合要求（role 验证）
    2. 修剪对话历史（删除目标消息及其后续所有消息）
    3. 更新节点的 internal_state 和 updated_at
    """

    def validate_message(
        self,
        node: AtomicNodeModel,
        message_id: str,
        allowed_roles: List[str] = ["user"]
    ) -> Tuple[Dict[str, Any], int]:
        """
        验证消息是否存在且符合要求。
        
        Args:
            node: 节点对象
            message_id: 消息 ID
            allowed_roles: 允许的角色列表（默认只允许 "user"）
        
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
                        f"Cannot operate on message with role '{role}'. "
                        f"Allowed roles: {allowed_roles}"
                    )
                return msg, index
        
        # 消息未找到
        raise ValueError(f"Message {message_id} not found in node {node.id}")

    def prune_conversation(
        self,
        db: Session,
        node: AtomicNodeModel,
        message_id: str,
        include_target: bool = True
    ) -> PruneResult:
        """
        修剪对话历史：删除目标消息及其所有后续消息。
        
        Args:
            db: 数据库会话
            node: 节点对象
            message_id: 目标消息 ID
            include_target: 是否包含目标消息本身（默认 True）
        
        Returns:
            PruneResult: 修剪结果
        
        Raises:
            ValueError: 如果消息不存在或不符合要求
        """
        # 1. 验证消息
        target_msg, target_index = self.validate_message(
            node, 
            message_id, 
            allowed_roles=["user"]  # 只允许操作 user 消息
        )
        
        # 2. 获取当前历史
        internal_state: Dict[str, Any] = dict(node.internal_state or {})
        history: List[Dict[str, Any]] = list(internal_state.get("chat_history", []) or [])
        
        # 3. 计算删除范围
        if include_target:
            # 删除目标消息及其所有后续消息
            remaining_messages = history[:target_index]
            deleted_count = len(history) - target_index
        else:
            # 只删除目标消息之后的消息
            remaining_messages = history[:target_index + 1]
            deleted_count = len(history) - target_index - 1
        
        # 4. 更新 internal_state
        internal_state["chat_history"] = remaining_messages
        
        # 5. 清除 token cache（因为历史已改变）
        if "_history_token_cache" in internal_state:
            del internal_state["_history_token_cache"]
        
        # 6. 更新节点
        node.internal_state = internal_state
        node.updated_at = datetime.utcnow()
        
        db.add(node)
        # 注意：不在这里 commit，由调用者负责事务管理
        
        logger.info(
            f"Pruned conversation for node {node.id}: "
            f"deleted {deleted_count} messages, "
            f"remaining {len(remaining_messages)} messages"
        )
        
        return PruneResult(
            deleted_count=deleted_count,
            remaining_messages=remaining_messages,
            target_index=target_index
        )


# 单例导出
pruning_engine = PruningEngine()
