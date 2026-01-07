/**
 * 节点创建表单组件
 * 
 * 用于创建新节点，包含所有必需字段的输入表单
 */

import { useState, useEffect, useMemo } from 'react';
import { X, Plus, ChevronDown, ChevronUp } from 'lucide-react';
import { createNode } from '../../api/topology';
import type { AtomicNodeCreate } from '../../types/node';
import { ApiError } from '../../api/client';

// 模型列表映射（根据 provider）
const MODEL_OPTIONS: Record<string, Array<{ value: string; label: string }>> = {
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
    { value: 'gpt-4', label: 'GPT-4' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  ],
  anthropic: [
    { value: 'claude-3-opus', label: 'Claude 3 Opus' },
    { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
    { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
  ],
  zhipuai: [
    { value: 'glm-4-flash', label: 'GLM-4 Flash' },
    { value: 'glm-4', label: 'GLM-4' },
    { value: 'glm-3-turbo', label: 'GLM-3 Turbo' },
  ],
  google: [
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
  ],
  local: [
    { value: 'local-llm', label: 'Local LLM' },
  ],
};

interface NodeCreateFormProps {
  /** 项目 ID */
  projectId: string;
  /** 父节点 ID（可选，如果提供则创建子节点） */
  parentId?: string | null;
  /** 创建成功后的回调 */
  onSuccess?: (node: any) => void;
  /** 取消创建的回调 */
  onCancel?: () => void;
  /** 刷新节点列表的函数 */
  onRefresh?: () => void;
}

export function NodeCreateForm({
  projectId,
  parentId = null,
  onSuccess,
  onCancel,
  onRefresh,
}: NodeCreateFormProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 表单状态
  const [formData, setFormData] = useState<Partial<AtomicNodeCreate>>({
    id: crypto.randomUUID(), // 自动生成 UUID
    project_id: projectId,
    parent_id: parentId,
    tags: [],
    author_id: 'user-1', // 默认作者 ID，后续可以从用户上下文获取
    input_context: {
      content: '',
      meta: {},
    },
    output_artifact: {
      content: '',
      mime_type: 'text/markdown',
      status: 'empty',
    },
    internal_state: {
      system_instruction: '',
      chat_history: [],
      variables: {},
    },
    config: {
      execution_mode: 'manual',
      llm_settings: {
        provider: 'openai',
        model: 'gpt-4o',
        temperature: 0.7,
        max_tokens: 1024,
      },
    },
  });

  // 同步 props 的变化到 formData（确保表单显示的信息和实际选择一致）
  useEffect(() => {
    setFormData((prev) => ({
      ...prev,
      project_id: projectId,
      parent_id: parentId,
    }));
  }, [projectId, parentId]);

  // 根据 provider 获取可用的模型列表
  const availableModels = useMemo(() => {
    const provider = formData.config?.llm_settings?.provider || 'openai';
    return MODEL_OPTIONS[provider] || MODEL_OPTIONS.openai;
  }, [formData.config?.llm_settings?.provider]);

  // 当 provider 改变时，自动重置为对应 provider 的第一个模型
  const handleProviderChange = (newProvider: string) => {
    const models = MODEL_OPTIONS[newProvider] || MODEL_OPTIONS.openai;
    const defaultModel = models[0]?.value || 'gpt-4o';
    
    setFormData({
      ...formData,
      config: {
        ...formData.config!,
        llm_settings: {
          ...formData.config!.llm_settings!,
          provider: newProvider as any,
          model: defaultModel,
        },
      },
    });
  };

  // 处理表单提交
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 验证必需字段
      if (!formData.id || !formData.project_id || !formData.author_id) {
        throw new Error('请填写所有必需字段');
      }

      if (!formData.input_context || !formData.output_artifact || !formData.internal_state || !formData.config) {
        throw new Error('请填写所有必需字段');
      }

      // 构建完整的创建数据
      // 关键修复：强制使用 props 的 projectId 和 parentId，而不是 formData 里的
      // 这确保了即使 formData 没有及时更新，提交时也会使用当前选中的项目/父节点
      const nodeData: AtomicNodeCreate = {
        id: formData.id!,
        project_id: projectId, // 使用 props，确保是当前选中的项目
        parent_id: parentId || null, // 使用 props，确保是当前选中的父节点（如果有）
        input_context: formData.input_context!,
        output_artifact: formData.output_artifact!,
        internal_state: formData.internal_state!,
        config: formData.config!,
        fork_from_node_id: formData.fork_from_node_id || null,
        tags: formData.tags || [],
        author_id: formData.author_id!,
      };

      // 调用 API 创建节点
      const newNode = await createNode(nodeData);

      // 成功处理
      setLoading(false);
      setIsOpen(false);
      onSuccess?.(newNode);
      onRefresh?.();

      // 重置表单
      setFormData({
        id: crypto.randomUUID(),
        project_id: projectId,
        parent_id: parentId,
        tags: [],
        author_id: 'user-1',
        input_context: {
          content: '',
          meta: {},
        },
        output_artifact: {
          content: '',
          mime_type: 'text/markdown',
          status: 'empty',
        },
        internal_state: {
          system_instruction: '',
          chat_history: [],
          variables: {},
        },
        config: {
          execution_mode: 'manual',
          llm_settings: {
            provider: 'openai',
            model: 'gpt-4o',
            temperature: 0.7,
            max_tokens: 1024,
          },
        },
      });
    } catch (err) {
      setLoading(false);
      if (err instanceof ApiError) {
        setError(`创建失败: ${err.message}`);
      } else if (err instanceof Error) {
        setError(`创建失败: ${err.message}`);
      } else {
        setError('创建失败: 未知错误');
      }
      console.error('Failed to create node:', err);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
      >
        <Plus className="h-4 w-4" />
        创建节点
      </button>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-lg">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">
            {parentId ? '创建子节点' : '创建根节点'}
          </h3>
          <button
            onClick={() => {
              setIsOpen(false);
              onCancel?.();
            }}
            className="text-slate-400 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="p-4">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {/* 基本信息 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              节点标签（可选）
            </label>
            <input
              type="text"
              value={formData.tags?.join(', ') || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  tags: e.target.value
                    .split(',')
                    .map((tag) => tag.trim())
                    .filter((tag) => tag.length > 0),
                })
              }
              placeholder="例如: Summary_V1, Debug_Branch"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
            />
            <p className="mt-1 text-xs text-slate-500">
              多个标签用逗号分隔
            </p>
          </div>

          {/* 系统提示词 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              系统提示词 *
            </label>
            <textarea
              value={formData.internal_state?.system_instruction || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  internal_state: {
                    ...formData.internal_state!,
                    system_instruction: e.target.value,
                  },
                })
              }
              required
              rows={3}
              placeholder="例如: 你是一个资深 Python 程序员，请基于输入代码写出测试用例。"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
            />
          </div>

          {/* 输入上下文 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              输入上下文（父节点的输出）
            </label>
            <textarea
              value={
                typeof formData.input_context?.content === 'string'
                  ? formData.input_context.content
                  : JSON.stringify(formData.input_context?.content || '')
              }
              onChange={(e) =>
                setFormData({
                  ...formData,
                  input_context: {
                    ...formData.input_context!,
                    content: e.target.value,
                  },
                })
              }
              rows={3}
              placeholder="父节点传递下来的内容（如果是根节点，可以为空）"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
            />
          </div>

          {/* 输出类型 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              输出类型
            </label>
            <select
              value={formData.output_artifact?.mime_type || 'text/markdown'}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  output_artifact: {
                    ...formData.output_artifact!,
                    mime_type: e.target.value as any,
                  },
                })
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
            >
              <option value="text/markdown">Markdown</option>
              <option value="application/json">JSON</option>
              <option value="text/x-python">Python</option>
              <option value="text/plain">Plain Text</option>
            </select>
          </div>

          {/* LLM 配置 */}
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                LLM Provider
              </label>
              <select
                value={formData.config?.llm_settings?.provider || 'openai'}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="zhipuai">智谱AI (ZhipuAI)</option>
                <option value="google">Google</option>
                <option value="local">Local</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                LLM 模型
              </label>
              <select
                value={formData.config?.llm_settings?.model || availableModels[0]?.value || 'gpt-4o'}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    config: {
                      ...formData.config!,
                      llm_settings: {
                        ...formData.config!.llm_settings!,
                        model: e.target.value,
                      },
                    },
                  })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
              >
                {availableModels.map((model) => (
                  <option key={model.value} value={model.value}>
                    {model.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Temperature
                </label>
                <input
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  value={formData.config?.llm_settings?.temperature ?? 0.7}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: {
                        ...formData.config!,
                        llm_settings: {
                          ...formData.config!.llm_settings!,
                          temperature: parseFloat(e.target.value) || 0.7,
                        },
                      },
                    })
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                />
                <p className="mt-1 text-xs text-slate-500">范围: 0-2</p>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Max Tokens
                </label>
                <input
                  type="number"
                  min="1"
                  max="32000"
                  step="1"
                  value={formData.config?.llm_settings?.max_tokens ?? 1024}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: {
                        ...formData.config!,
                        llm_settings: {
                          ...formData.config!.llm_settings!,
                          max_tokens: parseInt(e.target.value) || 1024,
                        },
                      },
                    })
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                />
                <p className="mt-1 text-xs text-slate-500">默认: 1024</p>
              </div>
            </div>
          </div>

          {/* 执行模式 */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              执行模式
            </label>
            <select
              value={formData.config?.execution_mode || 'manual'}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  config: {
                    ...formData.config!,
                    execution_mode: e.target.value as 'manual' | 'agent_loop',
                  },
                })
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
            >
              <option value="manual">手动模式</option>
              <option value="agent_loop">自动化模式</option>
            </select>
          </div>

          {/* 隐藏字段提示 */}
          <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <p className="mb-1 font-medium">自动生成字段：</p>
            <ul className="list-inside list-disc space-y-0.5">
              <li>节点 ID: {formData.id}</li>
              <li>项目 ID: {projectId}</li>
              {parentId && <li>父节点 ID: {parentId}</li>}
              <li>深度、子节点列表、版本哈希等将由后端自动计算</li>
            </ul>
          </div>
        </div>

        {/* 提交按钮 */}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onCancel?.();
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            disabled={loading}
          >
            取消
          </button>
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? '创建中...' : '创建节点'}
          </button>
        </div>
      </form>
    </div>
  );
}

