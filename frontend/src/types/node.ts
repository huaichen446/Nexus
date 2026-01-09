/**
 * AtomicNode: 提示词工程 IDE 的最小算力单元
 * 
 * 设计哲学：
 * 1. 隔离性 (Isolation): 节点内部的 Trial & Error 不会污染外部。
 * 2. 函数式 (Functional): Input -> Process -> Output。
 * 3. 可溯源 (Traceability): 完整的族谱关系。
 */

// ==========================================
// Sub-Types (Nested Structures)
// ==========================================

export interface NodeInputContext {
  /**
   * 输入：黄金上下文 (Golden Context / Upstream Payload)。
   * 这是父节点传递下来的数据快照。
   * @readonly 本节点不可修改此数据，只能读取。
   * 设计意图：解耦。本节点不关心父节点是如何生成数据的，只关心拿到的是什么。
   */
  /** 父节点的 Artifact 内容 */
  content: string | Record<string, any> | any[];
  /** 父节点产出时的元数据（如 Token 消耗、生成时间） */
  meta: Record<string, any>;
}

export interface NodeOutputArtifact {
  /**
   * 输出：产出物 (Artifact)。
   * 这是本节点经过 LLM 处理或人工编辑后，决定"暴露"给子节点的最终结果。
   * 设计意图：这是节点的"返回值"。子节点只能看到这个，看不到本节点的 internal_state。
   */
  /** 最终确定的内容 (The Result) */
  content: string | Record<string, any> | any[];
  /** 数据类型，用于下游节点决定如何解析 (Markdown, JSON, PythonCode, SQL) */
  mime_type: 'text/markdown' | 'application/json' | 'text/x-python' | 'text/plain';
  /** 产出状态：是否已准备好被下游消费 */
  status: 'empty' | 'generating' | 'finalized';
}

export interface ChatMessage {
  /**
   * 单个对话消息结构。
   */
  /** 消息唯一标识符 (UUID) */
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  
  /**
   * [新增字段] 是否被剪枝/屏蔽
   * Default: false
   * 如果为 true，Kernel 在组装 prompt 发给 LLM 时会直接跳过此消息。
   * 这允许用户"软删除"错误的对话，实现 Context 瞬间修复。
   */
  is_disabled?: boolean;
}

export interface NodeInternalState {
  /**
   * 内部状态：沙盒环境。
   * 这里的任何数据都是"私有"的，不会被子节点继承。
   */
  /** 系统提示词 (System Prompt)。定义该节点的角色设定。 */
  system_instruction: string;
  /** 草稿纸对话流。记录用户在该节点内部与 LLM 的反复拉锯、调试过程。 */
  chat_history: ChatMessage[];
  /** 临时变量 (Scratchpad)。用户可以在此存储临时的 JSON 变量或笔记，用于辅助 Prompt 编写。 */
  variables: Record<string, any>;
}

export interface LlmSettings {
  /**
   * LLM 调用配置细节。
   */
  provider: 'openai' | 'google' | 'anthropic' | 'local' | 'zhipuai';
  model: string; // e.g., "gpt-4-turbo", "gemini-1.5-pro", "glm-4-flash"
  temperature: number;
  max_tokens?: number;
  top_p?: number;
  /** 支持 Function Calling 定义 */
  tools?: any[];
}

export interface AutomationRules {
  /**
   * 自动化触发与停止条件。
   */
  retry_count: number;
  exit_condition_regex?: string;
}

export interface NodeExecutionConfig {
  /**
   * 执行配置 (Execution Runtime)。
   */
  /** 运行模式。'manual': 人工交互模式；'agent_loop': 自动化模式 */
  execution_mode: 'manual' | 'agent_loop';
  /** LLM 调用配置。每个节点可以调用不同的模型。 */
  llm_settings: LlmSettings;
  /** 自动化触发条件。如果是 Agent 模式，定义何时停止。 */
  automation_rules?: AutomationRules;
}

// ==========================================
// Main Type: AtomicNode (Response)
// ==========================================

export interface AtomicNode {
  // ==========================================
  // 1. 基础拓扑属性 (Topology & Identity)
  // ==========================================
  
  /** 全局唯一标识符 (UUID v4) */
  id: string;

  /** 归属的项目/空间 ID，用于做多租户隔离 */
  project_id: string;

  /**
   * 父节点引用。
   * 如果为 null，则该节点为 Root Node (系统的 System Prompt 入口)。
   */
  parent_id: string | null;

  /**
   * 子节点列表 (Adjacency List)。
   * 存储子节点的 ID，用于快速渲染树状 UI。
   */
  children_ids: string[];

  /**
   * 节点深度。
   * Root = 0。用于前端虚拟滚动渲染优化和防止无限递归的熔断机制。
   */
  depth: number;

  // ==========================================
  // 2. 版本与血缘 (Versioning & Lineage)
  // ==========================================

  /**
   * 分支来源。
   * 如果用户在某个节点"Fork"出了新分支，这里记录被 Fork 的源节点 ID。
   * 这允许我们构建 Git 风格的版本树，而不仅仅是对话树。
   */
  fork_from_node_id?: string | null;

  /**
   * 节点状态快照哈希。
   * 每次 artifact 更新时生成，用于判断节点是否发生过变更 (Dirty Check)。
   */
  version_hash: string;
  
  /**
   * 节点标签/别名。
   * 例如："Summary_V1", "Debug_Branch"，方便语义化检索。
   */
  tags: string[];

  // ==========================================
  // 3. 输入/输出接口 (The I/O Membrane)
  // ==========================================

  /**
   * 输入：黄金上下文 (Golden Context / Upstream Payload)。
   * 这是父节点传递下来的数据快照。
   */
  input_context: NodeInputContext;

  /**
   * 输出：产出物 (Artifact)。
   * 这是本节点经过 LLM 处理或人工编辑后，决定"暴露"给子节点的最终结果。
   */
  output_artifact: NodeOutputArtifact;

  // ==========================================
  // 4. 内部状态 (Internal State - The Sandbox)
  // ==========================================

  /**
   * 内部状态：沙盒环境。
   * 这里的任何数据都是"私有"的，不会被子节点继承。
   */
  internal_state: NodeInternalState;

  // ==========================================
  // 5. 执行配置 (Execution Runtime)
  // ==========================================

  config: NodeExecutionConfig;

  // ==========================================
  // 6. 节点生命周期状态 (Node Status)
  // ==========================================

  /**
   * 节点生命周期状态。
   * - active: 活跃节点，在默认视图中显示
   * - archived: 已归档节点，在默认视图中隐藏（宏观剪枝）
   */
  node_status: 'active' | 'archived';

  // ==========================================
  // 7. 元数据 (Metadata)
  // ==========================================
  
  /** 创建时间（ISO 8601 字符串，前端会自动转换为 Date） */
  created_at: string;
  /** 最后更新时间（ISO 8601 字符串，前端会自动转换为 Date） */
  updated_at: string;
  /** 创建者/作者 ID */
  author_id: string;
}

// ==========================================
// Request DTO: AtomicNodeCreate
// ==========================================

/**
 * 前端创建节点时，只需要传这些字段。
 * 后端会自动补全：depth, children_ids, version_hash, created_at, updated_at, node_status
 */
export interface AtomicNodeCreate {
  id: string;
  project_id: string;
  parent_id?: string | null;

  // 输入输出接口
  input_context: NodeInputContext;
  output_artifact: NodeOutputArtifact;

  // 内部状态
  internal_state: NodeInternalState;

  // 配置
  config: NodeExecutionConfig;

  // 其他
  fork_from_node_id?: string | null;
  tags?: string[];
  author_id: string;
}

