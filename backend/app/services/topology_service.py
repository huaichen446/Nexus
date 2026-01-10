from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update, text
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime
from backend.app.models import AtomicNodeModel
from backend.app.schemas import AtomicNode, AtomicNodeCreate, AtomicNodeUpdate
from backend.app.core.engines.pruning import pruning_engine
from backend.app.core.engines.forking import forking_engine

logger = logging.getLogger(__name__)



class TopologyService:

    def create_node_from_full_data(self, db: Session, node_data: AtomicNode) -> AtomicNodeModel:
        """
        创建一个新节点 (生产级实现)。

        逻辑：
        1. 检查 Parent 是否存在。
        2. 计算 Depth。
        3. 维护父节点的 children_ids (JSON字段)。
        4. 将 Pydantic 的嵌套对象转为 Dict 存入 JSON 字段。

        并发控制：
        - 使用 PostgreSQL 行级悲观锁 (FOR UPDATE) 保证 parent_node.children_ids 不出现竞态。
        - 即使在 SQLite 下运行，此代码也是安全的（SQLite 会退化为库级锁）。
        """
        try:
            depth = 0

            # ==========================================
            # 1. 父节点处理 (带悲观锁)
            # ==========================================
            if node_data.parent_id:
                # 使用 select(...).with_for_update() 锁定父节点行
                # 这确保了在读取 children_ids 和更新它之间，没有其他事务能修改这行数据
                stmt = (
                    select(AtomicNodeModel)
                    .where(AtomicNodeModel.id == node_data.parent_id)
                    .with_for_update()
                )
                parent_node = db.execute(stmt).scalar_one_or_none()

                if not parent_node:
                    error_msg = f"Parent node {node_data.parent_id} not found"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # 计算深度
                depth = parent_node.depth + 1

                # [Hybrid Storage Sync]
                # 获取当前 children_ids，确保不是 None
                current_children = list(parent_node.children_ids) if parent_node.children_ids else []

                if node_data.id not in current_children:
                    current_children.append(node_data.id)
                    parent_node.children_ids = current_children
                    db.add(parent_node)  # 标记父节点为脏数据 (Dirty)

            # ==========================================
            # 2. 构建并插入当前节点
            # ==========================================
            db_node = AtomicNodeModel(
                id=node_data.id,
                project_id=node_data.project_id,
                parent_id=node_data.parent_id,
                children_ids=node_data.children_ids or [],  # 默认为空列表
                depth=depth,

                # Versioning
                fork_from_node_id=node_data.fork_from_node_id,
                version_hash=node_data.version_hash,
                tags=node_data.tags,

                # Nested JSON Structures (Pydantic -> Dict)
                input_context=node_data.input_context.model_dump(),
                output_artifact=node_data.output_artifact.model_dump(),
                internal_state=node_data.internal_state.model_dump(),
                config=node_data.config.model_dump(),

                # Metadata
                created_at=node_data.created_at,
                updated_at=node_data.updated_at,
                author_id=node_data.author_id
            )

            db.add(db_node)

            # ==========================================
            # 3. 提交事务
            # ==========================================
            # 注意：不使用 with db.begin()，因为这会与 Session 的隐式事务冲突
            db.commit()

            # 刷新对象以获取数据库生成的字段（如有）
            db.refresh(db_node)

            logger.info(f"Node {db_node.id} created successfully (Depth: {depth})")
            return db_node

        except SQLAlchemyError as e:
            logger.exception("Database error during node creation")
            db.rollback()  # 遇到 DB 错误，回滚事务
            raise e

        except Exception as e:
            logger.exception("Unexpected error during node creation")
            db.rollback()  # 遇到逻辑错误，回滚事务
            raise e

    # 注意参数类型变了：node_data: AtomicNodeCreate
    def create_node(self, db: Session, node_data: AtomicNodeCreate) -> AtomicNodeModel:
        """
        接收前端的简化数据，补全系统字段，存入数据库。
        """
        try:
            depth = 0

            # 1. 父节点处理 (逻辑不变)
            if node_data.parent_id:
                stmt = (
                    select(AtomicNodeModel)
                    .where(AtomicNodeModel.id == node_data.parent_id)
                    .with_for_update()
                )
                parent_node = db.execute(stmt).scalar_one_or_none()

                if not parent_node:
                    error_msg = f"Parent node {node_data.parent_id} not found"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # 计算深度
                depth = parent_node.depth + 1

                # [Hybrid Storage Sync]
                # 获取当前 children_ids，确保不是 None
                current_children = list(parent_node.children_ids) if parent_node.children_ids else []

                if node_data.id not in current_children:
                    current_children.append(node_data.id)
                    parent_node.children_ids = current_children
                    db.add(parent_node)  # 标记父节点为脏数据 (Dirty)

            # 2. 构建 DB 模型 (这里是关键变化！)
            # 我们需要把 Create Schema 里没有、但 DB 需要的字段手动补上
            db_node = AtomicNodeModel(
                # --- 来自前端的数据 ---
                id=node_data.id,
                project_id=node_data.project_id,
                parent_id=node_data.parent_id,
                fork_from_node_id=node_data.fork_from_node_id,
                tags=node_data.tags,
                author_id=node_data.author_id,

                # 嵌套对象转 Dict
                input_context=node_data.input_context.model_dump(),
                output_artifact=node_data.output_artifact.model_dump(),
                internal_state=node_data.internal_state.model_dump(),
                config=node_data.config.model_dump(),

                # --- [重点] 后端自动补全的数据 ---
                depth=depth,  # 计算出来的
                children_ids=[],  # 新节点还没孩子，初始化为空
                version_hash="init_v1",  # 初始版本号
                created_at=datetime.now(),  # 当前时间
                updated_at=datetime.now(),  # 当前时间
            )

            db.add(db_node)
            db.commit()
            db.refresh(db_node)

            logger.info(f"Node {db_node.id} created successfully (Depth: {depth})")
            return db_node

        except SQLAlchemyError as e:
            logger.exception("Database error during node creation")
            db.rollback()  # 遇到 DB 错误，回滚事务
            raise e

        except Exception as e:
            logger.exception("Unexpected error during node creation")
            db.rollback()  # 遇到逻辑错误，回滚事务
            raise e


    def get_node(self, db: Session, node_id: str) -> Optional[AtomicNodeModel]:
        return db.query(AtomicNodeModel).filter(AtomicNodeModel.id == node_id).first()

    def get_children(self, db: Session, node_id: str) -> List[AtomicNodeModel]:
        """
        获取直接子节点。
        可以直接查 children_ids JSON，也可以查 parent_id 索引。
        这里使用 SQL 查询 parent_id 更稳健。
        """
        return (
            db.query(AtomicNodeModel)
            .filter(
                AtomicNodeModel.parent_id == node_id,
                AtomicNodeModel.node_status != "archived",
            )
            .all()
        )

    def get_root_nodes(self, db: Session, project_id: str) -> List[AtomicNodeModel]:
        """
        获取项目的所有根节点（parent_id 为 None 的节点）。
        用于前端显示项目的节点树。
        """
        return (
            db.query(AtomicNodeModel)
            .filter(
                AtomicNodeModel.project_id == project_id,
                AtomicNodeModel.parent_id == None,
                AtomicNodeModel.node_status != "archived",
            )
            .all()
        )

    def get_all_nodes_by_project(self, db: Session, project_id: str) -> List[AtomicNodeModel]:
        """
        获取项目的所有节点（用于前端构建完整的节点树）。
        """
        return (
            db.query(AtomicNodeModel)
            .filter(
                AtomicNodeModel.project_id == project_id,
                AtomicNodeModel.node_status != "archived",
            )
            .all()
        )

    # ==========================================
    # 节点更新 / 删除 / 宏观剪枝
    # ==========================================

    def update_node(self, db: Session, node_id: str, node_update: AtomicNodeUpdate) -> AtomicNodeModel:
        """
        部分更新节点内容（不修改拓扑结构，如 parent_id/depth/children_ids）。
        """
        node: Optional[AtomicNodeModel] = (
            db.query(AtomicNodeModel).filter(AtomicNodeModel.id == node_id).first()
        )

        if not node:
            raise ValueError(f"Node {node_id} not found")

        data = node_update.model_dump(exclude_unset=True)

        try:
            # 嵌套结构需要先转 dict
            if "input_context" in data and data["input_context"] is not None:
                node.input_context = data["input_context"]
            if "output_artifact" in data and data["output_artifact"] is not None:
                node.output_artifact = data["output_artifact"]
            if "internal_state" in data and data["internal_state"] is not None:
                # A. 取出当前数据库里的完整字典 (包含 _history_token_cache)
                # 使用 dict() 确保我们拿到的是 Python 字典副本
                current_state = dict(node.internal_state or {})
                
                # B. 取出前端传来的新数据 (不包含 cache)
                new_state_data = data["internal_state"]
                
                # C. 执行字典更新 (Merge)
                # 这会用新数据覆盖旧数据中已有的 key (如 system_instruction)，
                # 但会保留新数据中没有的 key (如 _history_token_cache)
                current_state.update(new_state_data)
                
                # D. 赋值回 ORM 对象，触发 SQLAlchemy 更新
                node.internal_state = current_state
            if "config" in data and data["config"] is not None:
                current_config = dict(node.config or {})
                current_config.update(data["config"])
                node.config = current_config

            # 简单字段
            if "fork_from_node_id" in data:
                node.fork_from_node_id = data["fork_from_node_id"]
            if "tags" in data and data["tags"] is not None:
                node.tags = data["tags"]
            if "author_id" in data and data["author_id"] is not None:
                node.author_id = data["author_id"]
            if "node_status" in data and data["node_status"] is not None:
                node.node_status = data["node_status"]

            # 更新时间戳
            node.updated_at = datetime.now()

            db.add(node)
            db.commit()
            db.refresh(node)
            logger.info(f"Node {node.id} updated successfully")
            return node

        except SQLAlchemyError as e:
            logger.exception("Database error during node update")
            db.rollback()
            raise e
        except Exception as e:
            logger.exception("Unexpected error during node update")
            db.rollback()
            raise e

    def delete_node(self, db: Session, node_id: str) -> None:
        """
        物理删除单个节点（以及 ORM 级联的子节点）。
        同时从父节点的 children_ids 中移除该节点。
        """
        node: Optional[AtomicNodeModel] = (
            db.query(AtomicNodeModel).filter(AtomicNodeModel.id == node_id).first()
        )

        if not node:
            raise ValueError(f"Node {node_id} not found")

        try:
            # 更新父节点的 children_ids
            if node.parent_id:
                parent = (
                    db.query(AtomicNodeModel)
                    .filter(AtomicNodeModel.id == node.parent_id)
                    .first()
                )
                if parent and parent.children_ids:
                    parent.children_ids = [
                        cid for cid in parent.children_ids if cid != node_id
                    ]
                    db.add(parent)

            db.delete(node)
            db.commit()
            logger.info(f"Node {node_id} deleted successfully")

        except SQLAlchemyError as e:
            logger.exception("Database error during node deletion")
            db.rollback()
            raise e
        except Exception as e:
            logger.exception("Unexpected error during node deletion")
            db.rollback()
            raise e

    def archive_branch(self, db: Session, node_id: str) -> int:
        """
        宏观剪枝：将当前节点及其所有子孙节点标记为 archived。
        返回被影响的节点数量。
        """
        root = (
            db.query(AtomicNodeModel).filter(AtomicNodeModel.id == node_id).first()
        )
        if not root:
            raise ValueError(f"Node {node_id} not found")

        affected = 0

        try:
            # 使用 BFS / 队列遍历子树
            queue: List[AtomicNodeModel] = [root]
            while queue:
                current = queue.pop(0)
                if current.node_status != "archived":
                    current.node_status = "archived"
                    db.add(current)
                    affected += 1

                # 加载子节点（不区分当前状态，全部继续往下遍历）
                children = (
                    db.query(AtomicNodeModel)
                    .filter(AtomicNodeModel.parent_id == current.id)
                    .all()
                )
                queue.extend(children)

            db.commit()
            logger.info(f"Archived branch from node {node_id}, affected={affected}")
            return affected

        except SQLAlchemyError as e:
            logger.exception("Database error during branch archive")
            db.rollback()
            raise e
        except Exception as e:
            logger.exception("Unexpected error during branch archive")
            db.rollback()
            raise e

    def get_ancestor_chain(self, db: Session, node_id: str) -> List[AtomicNodeModel]:
        """
        寻址与溯源：获取从 Root 到当前节点的所有祖先列表。
        返回顺序: [Root, Node_Level_1, ..., Parent, Self]
        使用 PostgreSQL 的递归 CTE，一次性找到：Root → ... → Parent → Self
        性能远优于循环 N 次查询
        """

        sql = text("""
               WITH RECURSIVE ancestors AS (
                   SELECT *
                   FROM atomic_nodes
                   WHERE id = :node_id

                   UNION ALL

                   SELECT parent.*
                   FROM atomic_nodes AS parent
                   JOIN ancestors AS child
                     ON parent.id = child.parent_id
               )
               SELECT *
               FROM ancestors;
               """)

        rows = db.execute(sql, {"node_id": node_id}).fetchall()

        if not rows:
            logger.error(f"Node {node_id} not found in ancestor CTE query")
            raise ValueError(f"Node {node_id} not found")

        # 转 ORM 对象（因为原 SQL 返回 Row，而不是 Model）
        models = [db.query(AtomicNodeModel).get(row.id) for row in rows]

        # 递归 CTE 是 Self → Parent → ... → Root，所以反转
        models.reverse()
        return models

    # ==========================================
    # 消息修剪 (Micro-Pruning)
    # ==========================================

    def prune_message(
        self,
        db: Session,
        node_id: str,
        message_id: str
    ) -> dict:
        """
        删除指定的用户消息及其所有后续消息（包括对应的 assistant 回复）。
        
        Args:
            db: 数据库会话
            node_id: 节点 ID
            message_id: 要删除的消息 ID
        
        Returns:
            dict: 包含删除统计信息的字典
        
        Raises:
            ValueError: 如果节点或消息不存在，或消息不符合要求
        """
        # 1. 获取节点
        node = self.get_node(db, node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        
        try:
            # 2. 调用修剪引擎
            result = pruning_engine.prune_conversation(
                db=db,
                node=node,
                message_id=message_id,
                include_target=True  # 删除消息时包含目标消息本身
            )
            
            # 3. 提交事务
            db.commit()
            
            logger.info(
                f"Pruned message {message_id} from node {node_id}: "
                f"deleted {result.deleted_count} messages"
            )
            
            return {
                "node_id": node_id,
                "message_id": message_id,
                "deleted_count": result.deleted_count,
                "remaining_messages": len(result.remaining_messages)
            }
            
        except ValueError as e:
            # 业务逻辑错误（消息不存在、角色不符合等）
            db.rollback()
            logger.error(f"Pruning failed: {str(e)}")
            raise e
        except SQLAlchemyError as e:
            db.rollback()
            logger.exception("Database error during message pruning")
            raise e
        except Exception as e:
            db.rollback()
            logger.exception("Unexpected error during message pruning")
            raise e

    # ==========================================
    # 对话分叉 (Deep Branching)
    # ==========================================

    def fork_branch(
        self,
        db: Session,
        node_id: str,
        message_id: str,
        user_id: str
    ) -> dict:
        """
        在指定消息处创建新分支（Sibling Strategy）。
        
        Args:
            db: 数据库会话
            node_id: 源节点 ID
            message_id: 目标消息 ID（分叉点，必须是 LLM 响应）
            user_id: 用户 ID（新节点的创建者）
        
        Returns:
            dict: 包含新节点信息的字典
        
        Raises:
            ValueError: 如果节点或消息不存在，或消息不符合要求（必须是 LLM 响应）
        """
        try:
            # 调用分叉引擎
            new_node_id = forking_engine.fork_conversation(
                db=db,
                source_node_id=node_id,
                target_message_id=message_id,
                user_id=user_id
            )
            
            # 提交事务
            db.commit()
            
            logger.info(
                f"Forked branch from node {node_id} at message {message_id}: "
                f"created new node {new_node_id}"
            )
            
            return {
                "source_node_id": node_id,
                "message_id": message_id,
                "new_node_id": new_node_id
            }
            
        except ValueError as e:
            # 业务逻辑错误（节点不存在、消息不存在、角色不符合等）
            db.rollback()
            logger.error(f"Forking failed: {str(e)}")
            raise e
        except SQLAlchemyError as e:
            db.rollback()
            logger.exception("Database error during branch forking")
            raise e
        except Exception as e:
            db.rollback()
            logger.exception("Unexpected error during branch forking")
            raise e

# 单例导出
topology_service = TopologyService()