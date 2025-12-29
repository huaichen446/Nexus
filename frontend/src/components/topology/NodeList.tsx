/**
 * 节点列表组件
 * 
 * 显示项目的所有节点（简单列表形式）
 */

import { useTopology } from '../../hooks/useTopology';
import type { AtomicNode } from '../../types/node';

interface NodeListProps {
  /** 项目 ID */
  projectId: string | null;
  /** 选中节点的回调 */
  onSelectNode?: (node: AtomicNode) => void;
  /** 刷新回调（当节点创建后调用） */
  onRefresh?: () => void;
}

export function NodeList({ projectId, onSelectNode, onRefresh }: NodeListProps) {
  const { nodes, loading, error, refresh } = useTopology(projectId);
  
  // 如果提供了外部刷新回调，在刷新时也调用它
  const handleRefresh = () => {
    refresh();
    onRefresh?.();
  };

  if (!projectId) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-center text-slate-500">
        请选择一个项目
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-center text-slate-500">
        加载中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <div className="mb-2 text-sm font-medium text-red-900">加载失败</div>
        <div className="mb-4 text-sm text-red-700">{error}</div>
        <button
          onClick={handleRefresh}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          重试
        </button>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-center text-slate-500">
        <p className="mb-2">暂无节点</p>
        <p className="text-xs text-slate-400">创建第一个节点开始使用</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">
            节点列表 ({nodes.length})
          </h3>
          <button
            onClick={handleRefresh}
            className="text-xs text-slate-600 hover:text-slate-900"
          >
            刷新
          </button>
        </div>
      </div>

      <div className="divide-y divide-slate-200">
        {nodes.map((node) => (
          <button
            key={node.id}
            onClick={() => onSelectNode?.(node)}
            className="w-full px-4 py-3 text-left transition-colors hover:bg-slate-50"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-900">
                    {node.id.slice(0, 8)}...
                  </span>
                  {node.tags.length > 0 && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                      {node.tags[0]}
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500">
                  深度: {node.depth} | 子节点: {node.children_ids.length} | 状态:{' '}
                  {node.output_artifact.status}
                </div>
              </div>
              <div className="ml-4 text-xs text-slate-400">
                {new Date(node.created_at).toLocaleDateString()}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

