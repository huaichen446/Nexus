from __future__ import annotations
from typing import List, Optional, Union, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


# ==========================================
# Sub-Models (Nested Structures)
# ==========================================

class NodeInputContext(BaseModel):
    """
    输入：黄金上下文 (Golden Context / Upstream Payload)。
    这是父节点传递下来的数据快照。
    设计意图：解耦。本节点不关心父节点是如何生成数据的，只关心拿到的是什么。
    """
    content: Union[str, Dict[str, Any], List[Any]] = Field(
        ...,
        description="父节点的 Artifact 内容。本节点不可修改此数据，只能读取。"
    )
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="父节点产出时的元数据（如 Token 消耗、生成时间）"
    )


class NodeOutputArtifact(BaseModel):
    """
    输出：产出物 (Artifact)。
    这是本节点经过 LLM 处理或人工编辑后，决定“暴露”给子节点的最终结果。
    设计意图：这是节点的“返回值”。子节点只能看到这个，看不到本节点的 internal_state。
    """
    content: Union[str, Dict[str, Any], List[Any]] = Field(
        ...,
        description="最终确定的内容 (The Result)"
    )
    mime_type: Literal['text/markdown', 'application/json', 'text/x-python', 'text/plain'] = Field(
        ...,
        description="数据类型，用于下游节点决定如何解析 (Markdown, JSON, PythonCode, SQL)"
    )
    status: Literal['empty', 'generating', 'finalized'] = Field(
        ...,
        description="产出状态：是否已准备好被下游消费"
    )


class ChatMessage(BaseModel):
    """
    单个对话消息结构。
    """
    role: Literal['user', 'assistant', 'system'] = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    timestamp: float = Field(..., description="时间戳 (Epoch)")

    is_disabled: bool = Field(
        default=False,
        description="是否被剪枝/屏蔽。如果为 True，Kernel 在组装 prompt 发给 LLM 时会直接跳过此消息。允许用户“软删除”错误的对话。"
    )


class NodeInternalState(BaseModel):
    """
    内部状态：沙盒环境。
    这里的任何数据都是"私有"的，不会被子节点继承。
    
    Note: 内部实现字段（如 _history_token_cache）存储在数据库中，
    但不会在 API 响应中暴露。这些字段由后端自动管理，前端无需关心。
    """
    system_instruction: str = Field(
        ...,
        description="系统提示词 (System Prompt)。定义该节点的角色设定。"
    )
    chat_history: List[ChatMessage] = Field(
        default_factory=list,
        description="草稿纸对话流。记录用户在该节点内部与 LLM 的反复拉锯、调试过程。"
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="临时变量 (Scratchpad)。用户可以在此存储临时的 JSON 变量或笔记，用于辅助 Prompt 编写。"
    )

    # Pydantic v2 默认 extra = "ignore"，这意味着：
    # - 额外字段（如 _history_token_cache）会被忽略，不会在 API 响应中暴露
    # - 但数据库中的这些字段仍然会被保留（因为直接操作 JSON 字段）
    # 这是期望的行为：内部实现细节不应该暴露给 API


class LlmSettings(BaseModel):
    """
    LLM 调用配置细节。
    """
    provider: Literal['openai', 'google', 'anthropic', 'zhipuai', 'local'] = Field(..., description="模型提供商")
    model: str = Field(..., description="模型名称")
    temperature: float = Field(..., description="随机性参数")
    max_tokens: Optional[int] = Field(None, description="最大生成 Token 数")
    top_p: Optional[float] = Field(None, description="Nucleus sampling 参数")
    tools: Optional[List[Any]] = Field(default_factory=list, description="Function Calling 工具定义")


class AutomationRules(BaseModel):
    """
    自动化触发与停止条件。
    """
    retry_count: int = Field(..., description="最大重试次数")
    exit_condition_regex: Optional[str] = Field(None, description="退出条件的正则匹配规则")


class NodeExecutionConfig(BaseModel):
    """
    执行配置 (Execution Runtime)。
    """
    execution_mode: Literal['manual', 'agent_loop'] = Field(
        ...,
        description="'manual': 人工交互模式; 'agent_loop': 自动化模式"
    )
    llm_settings: LlmSettings = Field(
        ...,
        description="LLM 调用配置。每个节点可以调用不同的模型。"
    )
    automation_rules: Optional[AutomationRules] = Field(
        None,
        description="自动化触发条件。如果是 Agent 模式，定义何时停止。"
    )


# ==========================================
# Main Model: AtomicNode
# ==========================================

class AtomicNode(BaseModel):
    """
    AtomicNode: 提示词工程 IDE 的最小算力单元

    设计哲学：
    1. 隔离性 (Isolation): 节点内部的 Trial & Error 不会污染外部。
    2. 函数式 (Functional): Input -> Process -> Output。
    3. 可溯源 (Traceability): 完整的族谱关系。
    """

    # ==========================================
    # 1. 基础拓扑属性 (Topology & Identity)
    # ==========================================

    id: str = Field(
        ...,
        description="全局唯一标识符 (UUID v4)"
    )

    project_id: str = Field(
        ...,
        description="归属的项目/空间 ID，用于做多租户隔离"
    )

    parent_id: Optional[str] = Field(
        None,
        description="父节点引用。如果为 None，则该节点为 Root Node (系统的 System Prompt 入口)。"
    )

    children_ids: List[str] = Field(
        default_factory=list,
        description="子节点列表 (Adjacency List)。存储子节点的 ID，用于快速渲染树状 UI。"
    )

    depth: int = Field(
        ...,
        description="节点深度。Root = 0。用于前端虚拟滚动渲染优化和防止无限递归的熔断机制。"
    )

    # ==========================================
    # 2. 版本与血缘 (Versioning & Lineage)
    # ==========================================

    fork_from_node_id: Optional[str] = Field(
        None,
        description="分支来源。如果用户在某个节点“Fork”出了新分支，这里记录被 Fork 的源节点 ID。这允许构建 Git 风格的版本树。"
    )

    version_hash: str = Field(
        ...,
        description="节点状态快照哈希。每次 artifact 更新时生成，用于判断节点是否发生过变更 (Dirty Check)。"
    )

    tags: List[str] = Field(
        default_factory=list,
        description="节点标签/别名。例如：'Summary_V1', 'Debug_Branch'，方便语义化检索。"
    )

    # ==========================================
    # 3. 输入/输出接口 (The I/O Membrane)
    # ==========================================

    input_context: NodeInputContext = Field(
        ...,
        description="输入：黄金上下文。父节点传递下来的数据快照。"
    )

    output_artifact: NodeOutputArtifact = Field(
        ...,
        description="输出：产出物。本节点处理后的最终结果。"
    )

    # ==========================================
    # 4. 内部状态 (Internal State - The Sandbox)
    # ==========================================

    internal_state: NodeInternalState = Field(
        ...,
        description="内部状态：沙盒环境。私有数据，不被子节点继承。"
    )

    # ==========================================
    # 5. 执行配置 (Execution Runtime)
    # ==========================================

    config: NodeExecutionConfig = Field(
        ...,
        description="执行运行时的相关配置。"
    )

    # ==========================================
    # 6. 节点生命周期状态 (Node Status)
    # ==========================================

    node_status: Literal["active", "archived"] = Field(
        default="active",
        description="节点生命周期状态：active=活跃；archived=已归档（默认视图中隐藏）",
    )

    # ==========================================
    # 7. 元数据 (Metadata)
    # ==========================================

    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    author_id: str = Field(..., description="创建者/作者 ID")


# ==========================================
# Request DTO: 专门用于创建节点的输入模型
# ==========================================
class AtomicNodeCreate(BaseModel):
    """
    前端创建节点时，只需要传这些字段。
    """
    id: str = Field(..., description="客户端生成的 UUID")
    project_id: str
    parent_id: Optional[str] = None

    # 输入输出接口
    input_context: NodeInputContext
    output_artifact: NodeOutputArtifact

    # 内部状态
    internal_state: NodeInternalState

    # 配置
    config: NodeExecutionConfig

    # 其他
    fork_from_node_id: Optional[str] = None
    tags: List[str] = []
    author_id: str

    # 关键点：这里去掉了 depth, children_ids, version_hash, created_at, updated_at
    # 因为这些是后端生成的，前端不需要关心。


class AtomicNodeUpdate(BaseModel):
    """
    节点部分更新模型（用于前端编辑）。

    设计原则：
    - 所有字段都是可选（partial update / PATCH 语义）
    - 不允许直接修改 project_id / parent_id / depth / children_ids 等拓扑结构字段
    """

    # 输入输出接口
    input_context: Optional[NodeInputContext] = None
    output_artifact: Optional[NodeOutputArtifact] = None

    # 内部状态
    internal_state: Optional[NodeInternalState] = None

    # 配置
    config: Optional[NodeExecutionConfig] = None

    # 其他可编辑字段
    fork_from_node_id: Optional[str] = None
    tags: Optional[List[str]] = None
    author_id: Optional[str] = None

    # 允许显式修改节点状态（例如从 archived 恢复为 active）
    node_status: Optional[Literal["active", "archived"]] = None

    class Config:
        extra = "forbid"


class NodeChatRequest(BaseModel):
    """
    专门用于 /nodes/{id}/chat/stream 接口的请求体
    """
    content: str = Field(..., description="用户的聊天输入内容")


class PartialChatRequest(BaseModel):
    """
    专门用于 /nodes/{id}/chat/partial 接口的请求体
    用于保存部分完成的助手消息（当用户取消流式响应时）
    """
    content: str = Field(..., description="部分完成的助手消息内容")