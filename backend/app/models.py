import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from .database import Base


class AtomicNodeModel(Base):
    __tablename__ = 'atomic_nodes'

    # ==========================================
    # 1. 基础拓扑属性 (Topology & Identity)
    # ==========================================
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)  # 建议加索引以支持多租户查询

    # 树形结构核心逻辑
    parent_id = Column(String, ForeignKey("atomic_nodes.id"), nullable=True)

    # [Hybrid Storage]
    # 虽然有了 parent/children relationship，但保留 children_ids 作为 JSON 字段，
    # 用于前端快速渲染树形 UI (Adjacency List)，无需递归查询 SQL。
    children_ids = Column(JSON, default=list, nullable=False)

    depth = Column(Integer, nullable=False, default=0)

    # 节点生命周期状态：active=活跃；archived=已归档（默认视图中隐藏）
    node_status = Column(String, nullable=False, default="active", index=True)

    # ==========================================
    # 2. 版本与血缘 (Versioning & Lineage)
    # ==========================================
    fork_from_node_id = Column(String, nullable=True)
    version_hash = Column(String, nullable=False)
    tags = Column(JSON, default=list, nullable=False)

    # ==========================================
    # 3. 输入/输出接口 (Nested Objects -> JSON)
    # ==========================================
    # 对应 Pydantic: NodeInputContext
    # 策略: 直接存 JSON，避免创建 node_input_contexts 表
    input_context = Column(JSON, nullable=False)

    # 对应 Pydantic: NodeOutputArtifact
    output_artifact = Column(JSON, nullable=False)

    # ==========================================
    # 4. 内部状态 (Internal State -> JSON)
    # ==========================================
    # 对应 Pydantic: NodeInternalState
    # 包含 system_instruction, chat_history(List), variables(Dict)
    # 这些高频变动且结构复杂的数据非常适合 JSON 类型
    internal_state = Column(JSON, nullable=False)

    # ==========================================
    # 5. 执行配置 (Execution Runtime -> JSON)
    # ==========================================
    # 对应 Pydantic: NodeExecutionConfig
    # 包含 llm_settings, automation_rules
    config = Column(JSON, nullable=False)

    # ==========================================
    # 6. 元数据 (Metadata)
    # ==========================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    author_id = Column(String, nullable=False)

    # ==========================================
    # ORM Relationships
    # ==========================================
    # 自关联配置：
    # 1. backref="parent": 子节点可以通过 .parent 访问父节点对象
    # 2. remote_side=[id]: 声明这是一对多的自关联
    # 3. cascade: 删除父节点时，自动清理子节点（根据业务需求可选）
    children = relationship(
        "AtomicNodeModel",
        backref=backref("parent", remote_side=[id]),
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AtomicNode(id={self.id}, project_id={self.project_id}, depth={self.depth})>"