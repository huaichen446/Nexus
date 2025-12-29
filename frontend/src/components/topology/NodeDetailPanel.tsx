/**
 * 节点详情面板组件
 * 
 * 功能：
 * 1. 显示节点详细信息
 * 2. 溯源链面包屑导航
 * 3. 编辑节点内容
 * 4. 归档分支（宏观剪枝）
 * 5. 删除节点（物理删除）
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Edit2, Archive, Trash2, ChevronRight, X, Save } from 'lucide-react';
import { updateNode, archiveBranch, deleteNode } from '../../api/topology';
import { useNodeLineage } from '../../hooks/useTopology';
import type { AtomicNode } from '../../types/node';
import { ApiError } from '../../api/client';

interface NodeDetailPanelProps {
  /** 当前选中的节点 */
  node: AtomicNode;
  /** 项目 ID（用于创建子节点） */
  projectId: string | null;
  /** 节点更新后的回调 */
  onNodeUpdated?: (node: AtomicNode) => void;
  /** 节点删除后的回调 */
  onNodeDeleted?: () => void;
  /** 节点归档后的回调 */
  onNodeArchived?: () => void;
  /** 刷新节点列表 */
  onRefresh?: () => void;
  /** 选中其他节点的回调（用于面包屑跳转） */
  onSelectNode?: (node: AtomicNode) => void;
}

export function NodeDetailPanel({
  node,
  projectId,
  onNodeUpdated,
  onNodeDeleted,
  onNodeArchived,
  onRefresh,
  onSelectNode,
}: NodeDetailPanelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 编辑表单状态
  const [editForm, setEditForm] = useState({
    tags: node.tags.join(', '),
    system_instruction: node.internal_state.system_instruction,
    output_content:
      typeof node.output_artifact.content === 'string'
        ? node.output_artifact.content
        : JSON.stringify(node.output_artifact.content),
  });

  // 溯源链数据
  const { lineage, loading: lineageLoading } = useNodeLineage(node.id);

  // 保存编辑
  const handleSaveEdit = async () => {
    setLoading(true);
    setError(null);

    try {
      const updated = await updateNode(node.id, {
        tags: editForm.tags
          .split(',')
          .map((t) => t.trim())
          .filter((t) => t.length > 0),
        internal_state: {
          ...node.internal_state,
          system_instruction: editForm.system_instruction,
        },
        output_artifact: {
          ...node.output_artifact,
          content: editForm.output_content,
        },
      });

      setIsEditing(false);
      onNodeUpdated?.(updated);
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`更新失败: ${err.message}`);
      } else {
        setError('更新失败: 未知错误');
      }
      console.error('Failed to update node:', err);
    } finally {
      setLoading(false);
    }
  };

  // 归档分支
  const handleArchiveBranch = async () => {
    const confirmed = window.confirm(
      `确定要归档该分支吗？\n\n这将归档节点 "${node.tags[0] || node.id.slice(0, 8)}" 及其所有 ${node.children_ids.length} 个子节点。\n归档后，这些节点将从树视图中隐藏，但数据仍会保留。`
    );

    if (!confirmed) return;

    setLoading(true);
    setError(null);

    try {
      const result = await archiveBranch(node.id);
      alert(`已归档 ${result.archived_count} 个节点`);
      onNodeArchived?.();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`归档失败: ${err.message}`);
      } else {
        setError('归档失败: 未知错误');
      }
      console.error('Failed to archive branch:', err);
    } finally {
      setLoading(false);
    }
  };

  // 删除节点
  const handleDeleteNode = async () => {
    const confirmed = window.confirm(
      `⚠️ 警告：确定要永久删除该节点吗？\n\n这将删除节点 "${node.tags[0] || node.id.slice(0, 8)}" 及其所有 ${node.children_ids.length} 个子节点。\n此操作不可恢复！\n\n如果只是想隐藏节点，建议使用"归档分支"功能。`
    );

    if (!confirmed) return;

    const doubleConfirm = window.confirm('请再次确认：此操作将永久删除数据，无法恢复！');

    if (!doubleConfirm) return;

    setLoading(true);
    setError(null);

    try {
      await deleteNode(node.id);
      alert('节点已删除');
      onNodeDeleted?.();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`删除失败: ${err.message}`);
      } else {
        setError('删除失败: 未知错误');
      }
      console.error('Failed to delete node:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 rounded-lg border border-slate-200 bg-white shadow-sm"
    >
      {/* 头部：标题和操作按钮 */}
      <div className="border-b border-slate-200 bg-slate-50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-slate-900">
              {node.tags.length > 0 ? node.tags[0] : `节点 ${node.id.slice(0, 8)}`}
            </h3>
            {node.tags.length > 1 && (
              <p className="mt-1 text-xs text-slate-500">
                其他标签: {node.tags.slice(1).join(', ')}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* 编辑按钮 */}
            {!isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                disabled={loading}
                className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <Edit2 className="h-4 w-4" />
                编辑
              </button>
            )}

            {/* 归档分支按钮（推荐操作） */}
            {!isEditing && (
              <button
                onClick={handleArchiveBranch}
                disabled={loading}
                className="flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                <Archive className="h-4 w-4" />
                归档分支
              </button>
            )}

            {/* 删除按钮（危险操作） */}
            {!isEditing && (
              <button
                onClick={handleDeleteNode}
                disabled={loading}
                className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                删除
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 溯源链面包屑 */}
      {lineageLoading ? (
        <div className="border-b border-slate-200 bg-slate-50 px-6 py-3 text-sm text-slate-500">
          加载溯源链...
        </div>
      ) : lineage && lineage.length > 0 ? (
        <div className="border-b border-slate-200 bg-slate-50 px-6 py-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-slate-600">溯源链:</span>
            {lineage.map((ancestor, index) => (
              <div key={ancestor.id} className="flex items-center gap-2">
                <button
                  onClick={() => onSelectNode?.(ancestor)}
                  className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                    ancestor.id === node.id
                      ? 'bg-slate-900 text-white'
                      : ancestor.node_status === 'archived'
                      ? 'bg-slate-200 text-slate-500 line-through'
                      : 'bg-white text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {ancestor.tags.length > 0
                    ? ancestor.tags[0]
                    : `Node ${ancestor.id.slice(0, 6)}`}
                  {ancestor.node_status === 'archived' && ' (已归档)'}
                </button>
                {index < lineage.length - 1 && (
                  <ChevronRight className="h-4 w-4 text-slate-400" />
                )}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* 错误提示 */}
      {error && (
        <div className="border-b border-red-200 bg-red-50 px-6 py-3 text-sm text-red-900">
          {error}
        </div>
      )}

      {/* 内容区域 */}
      <div className="p-6">
        {isEditing ? (
          /* 编辑模式 */
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                标签（用逗号分隔）
              </label>
              <input
                type="text"
                value={editForm.tags}
                onChange={(e) =>
                  setEditForm({ ...editForm, tags: e.target.value })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                系统提示词 *
              </label>
              <textarea
                value={editForm.system_instruction}
                onChange={(e) =>
                  setEditForm({ ...editForm, system_instruction: e.target.value })
                }
                required
                rows={4}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                输出内容
              </label>
              <textarea
                value={editForm.output_content}
                onChange={(e) =>
                  setEditForm({ ...editForm, output_content: e.target.value })
                }
                rows={6}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
              />
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setIsEditing(false);
                  setError(null);
                  // 重置表单
                  setEditForm({
                    tags: node.tags.join(', '),
                    system_instruction: node.internal_state.system_instruction,
                    output_content:
                      typeof node.output_artifact.content === 'string'
                        ? node.output_artifact.content
                        : JSON.stringify(node.output_artifact.content),
                  });
                }}
                disabled={loading}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={loading}
                className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                {loading ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        ) : (
          /* 查看模式 */
          <div className="space-y-4">
            {/* 基本信息 */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium text-slate-700">节点 ID:</span>
                <span className="ml-2 text-slate-600 font-mono text-xs">
                  {node.id}
                </span>
              </div>
              <div>
                <span className="font-medium text-slate-700">状态:</span>
                <span
                  className={`ml-2 rounded-full px-2 py-0.5 text-xs font-medium ${
                    node.node_status === 'archived'
                      ? 'bg-slate-200 text-slate-600'
                      : 'bg-green-100 text-green-700'
                  }`}
                >
                  {node.node_status === 'archived' ? '已归档' : '活跃'}
                </span>
              </div>
              <div>
                <span className="font-medium text-slate-700">深度:</span>
                <span className="ml-2 text-slate-600">{node.depth}</span>
              </div>
              <div>
                <span className="font-medium text-slate-700">子节点数:</span>
                <span className="ml-2 text-slate-600">
                  {node.children_ids.length}
                </span>
              </div>
              <div>
                <span className="font-medium text-slate-700">产出状态:</span>
                <span className="ml-2 text-slate-600">
                  {node.output_artifact.status}
                </span>
              </div>
              <div>
                <span className="font-medium text-slate-700">创建时间:</span>
                <span className="ml-2 text-slate-600 text-xs">
                  {new Date(node.created_at).toLocaleString('zh-CN')}
                </span>
              </div>
            </div>

            {/* 系统提示词 */}
            <div>
              <h4 className="mb-2 text-sm font-semibold text-slate-900">
                系统提示词
              </h4>
              <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
                {node.internal_state.system_instruction || (
                  <span className="text-slate-400">（未设置）</span>
                )}
              </div>
            </div>

            {/* 输出内容 */}
            <div>
              <h4 className="mb-2 text-sm font-semibold text-slate-900">
                输出内容 ({node.output_artifact.mime_type})
              </h4>
              <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700 font-mono whitespace-pre-wrap break-words">
                {typeof node.output_artifact.content === 'string'
                  ? node.output_artifact.content || (
                      <span className="text-slate-400">（空）</span>
                    )
                  : JSON.stringify(node.output_artifact.content, null, 2)}
              </div>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

