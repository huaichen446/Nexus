/**
 * React Hook: 用于获取和管理拓扑节点数据
 * 
 * 功能：
 * 1. 获取项目的所有节点
 * 2. 管理加载状态和错误状态
 * 3. 提供刷新功能
 */

import { useState, useEffect, useCallback } from 'react';
import { getProjectAllNodes, getLineage } from '../api/topology';
import type { AtomicNode } from '../types/node';
import type { ApiError } from '../api/client';

interface UseTopologyResult {
  /** 节点列表 */
  nodes: AtomicNode[];
  /** 是否正在加载 */
  loading: boolean;
  /** 错误信息（如果有） */
  error: string | null;
  /** 刷新数据 */
  refresh: () => Promise<void>;
}

/**
 * 获取项目的所有节点
 * 
 * @param projectId - 项目 ID（如果为 null 或空字符串，则不加载数据）
 * @returns UseTopologyResult
 */
export function useTopology(projectId: string | null): UseTopologyResult {
  const [nodes, setNodes] = useState<AtomicNode[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadNodes = useCallback(async () => {
    // 如果没有 projectId，不加载数据
    if (!projectId) {
      setNodes([]);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getProjectAllNodes(projectId);
      setNodes(data);
    } catch (err) {
      const errorMessage =
        err instanceof ApiError
          ? `获取节点失败: ${err.message}`
          : err instanceof Error
          ? err.message
          : '未知错误';
      setError(errorMessage);
      setNodes([]);
      console.error('Failed to load nodes:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // 当 projectId 改变时，自动加载数据
  useEffect(() => {
    loadNodes();
  }, [loadNodes]);

  return {
    nodes,
    loading,
    error,
    refresh: loadNodes,
  };
}

/**
 * 获取节点的溯源链（从 Root 到当前节点）
 * 
 * @param nodeId - 节点 ID（如果为 null，则不加载数据）
 * @returns UseNodeLineageResult
 */
interface UseNodeLineageResult {
  /** 溯源链列表，顺序为 [Root, Level_1, ..., Parent, Self] */
  lineage: AtomicNode[];
  /** 是否正在加载 */
  loading: boolean;
  /** 错误信息（如果有） */
  error: string | null;
  /** 重新加载 */
  reload: () => Promise<void>;
}

export function useNodeLineage(nodeId: string | null): UseNodeLineageResult {
  const [lineage, setLineage] = useState<AtomicNode[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadLineage = useCallback(async () => {
    if (!nodeId) {
      setLineage([]);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getLineage(nodeId);
      setLineage(data);
    } catch (err) {
      const errorMessage =
        err instanceof ApiError
          ? `获取溯源链失败: ${err.message}`
          : err instanceof Error
          ? err.message
          : '未知错误';
      setError(errorMessage);
      setLineage([]);
      console.error('Failed to load lineage:', err);
    } finally {
      setLoading(false);
    }
  }, [nodeId]);

  useEffect(() => {
    loadLineage();
  }, [loadLineage]);

  return {
    lineage,
    loading,
    error,
    reload: loadLineage,
  };
}

