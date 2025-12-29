/**
 * 节点树组件
 * 
 * 以树形结构显示节点（使用 children_ids 快速渲染）
 */

import { useState, useMemo } from 'react';
import { ChevronRight, ChevronDown, FileText } from 'lucide-react';
import { useTopology } from '../../hooks/useTopology';
import type { AtomicNode } from '../../types/node';

interface NodeTreeProps {
  /** 项目 ID */
  projectId: string | null;
  /** 选中节点的回调 */
  onSelectNode?: (node: AtomicNode) => void;
  /** 刷新回调（当节点创建后调用） */
  onRefresh?: () => void;
}

interface TreeNode extends AtomicNode {
  /** 是否展开 */
  expanded?: boolean;
}

export function NodeTree({ projectId, onSelectNode, onRefresh }: NodeTreeProps) {
  const { nodes, loading, error, refresh } = useTopology(projectId);
  
  // 如果提供了外部刷新回调，在刷新时也调用它
  const handleRefresh = () => {
    refresh();
    onRefresh?.();
  };
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // 构建节点映射表（用于快速查找）
  const nodeMap = useMemo(() => {
    const map = new Map<string, TreeNode>();
    nodes.forEach((node) => {
      map.set(node.id, { ...node, expanded: expandedNodes.has(node.id) });
    });
    return map;
  }, [nodes, expandedNodes]);

  // 获取根节点（parent_id 为 null 的节点）
  const rootNodes = useMemo(() => {
    return nodes.filter((node) => node.parent_id === null);
  }, [nodes]);

  // 切换节点展开/折叠
  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  // 渲染单个节点
  const renderNode = (node: AtomicNode, depth: number = 0): JSX.Element => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children_ids.length > 0;

    return (
      <div key={node.id}>
        <div
          className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50"
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
        >
          {/* 展开/折叠按钮 */}
          {hasChildren ? (
            <button
              onClick={() => toggleNode(node.id)}
              className="flex h-5 w-5 items-center justify-center text-slate-400 hover:text-slate-600"
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          ) : (
            <div className="h-5 w-5" /> // 占位符，保持对齐
          )}

          {/* 节点图标 */}
          <FileText className="h-4 w-4 text-slate-400" />

          {/* 节点信息 */}
          <button
            onClick={() => onSelectNode?.(node)}
            className="flex-1 text-left text-sm text-slate-700 hover:text-slate-900"
          >
            <div className="flex items-center gap-2">
              <span className="font-medium">
                {node.tags.length > 0 ? node.tags[0] : `Node ${node.id.slice(0, 6)}`}
              </span>
              <span className="text-xs text-slate-400">
                ({node.children_ids.length})
              </span>
              {node.output_artifact.status === 'finalized' && (
                <span className="rounded-full bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                  完成
                </span>
              )}
            </div>
          </button>
        </div>

        {/* 子节点（如果展开） */}
        {hasChildren && isExpanded && (
          <div>
            {node.children_ids.map((childId) => {
              const childNode = nodeMap.get(childId);
              if (!childNode) return null;
              return renderNode(childNode, depth + 1);
            })}
          </div>
        )}
      </div>
    );
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

  if (rootNodes.length === 0) {
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
            节点树 ({nodes.length} 个节点)
          </h3>
          <button
            onClick={handleRefresh}
            className="text-xs text-slate-600 hover:text-slate-900"
          >
            刷新
          </button>
        </div>
      </div>

      <div className="max-h-[600px] overflow-y-auto p-2">
        {rootNodes.map((node) => renderNode(node))}
      </div>
    </div>
  );
}

