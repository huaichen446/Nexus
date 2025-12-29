/**
 * 拓扑相关 API 调用
 *
 * 对应后端路由：backend/app/routers/topology.py
 *
 * API 端点映射：
 * - POST   /nodes/                          → createNode
 * - GET    /nodes/{node_id}                 → getNode
 * - PATCH  /nodes/{node_id}                 → updateNode
 * - DELETE /nodes/{node_id}                 → deleteNode
 * - POST   /nodes/{node_id}/archive-branch  → archiveBranch
 * - GET    /nodes/{node_id}/children        → getChildren
 * - GET    /nodes/{node_id}/lineage         → getLineage
 * - GET    /nodes/project/{project_id}/all  → getProjectAllNodes
 */

import { apiGet, apiPost, apiDelete, apiRequest } from "../api/client";
import type { AtomicNode, AtomicNodeCreate } from "../types/node";

/**
 * 创建新节点
 */
export async function createNode(
  nodeData: AtomicNodeCreate
): Promise<AtomicNode> {
  return apiPost<AtomicNode>("/nodes/", nodeData);
}

/**
 * 获取单个节点的详细信息
 */
export async function getNode(nodeId: string): Promise<AtomicNode> {
  return apiGet<AtomicNode>(`/nodes/${nodeId}`);
}

/**
 * 获取节点的直接子节点列表
 */
export async function getChildren(nodeId: string): Promise<AtomicNode[]> {
  return apiGet<AtomicNode[]>(`/nodes/${nodeId}/children`);
}

/**
 * 获取节点的溯源链（从 Root 到当前节点）
 */
export async function getLineage(nodeId: string): Promise<AtomicNode[]> {
  return apiGet<AtomicNode[]>(`/nodes/${nodeId}/lineage`);
}

/**
 * 获取项目的所有节点（仅 active 节点）
 */
export async function getProjectAllNodes(
  projectId: string
): Promise<AtomicNode[]> {
  return apiGet<AtomicNode[]>(`/nodes/project/${projectId}/all`);
}

/**
 * 更新节点（部分更新）
 *
 * 只应传入可编辑字段：
 * - input_context
 * - output_artifact
 * - internal_state
 * - config
 * - fork_from_node_id
 * - tags
 * - author_id
 * - node_status
 */
export async function updateNode(
  nodeId: string,
  payload: Partial<AtomicNode>
): Promise<AtomicNode> {
  // 构造后端允许的字段
  const body: any = {
    input_context: payload.input_context,
    output_artifact: payload.output_artifact,
    internal_state: payload.internal_state,
    config: payload.config,
    fork_from_node_id: payload.fork_from_node_id,
    tags: payload.tags,
    author_id: payload.author_id,
    node_status: (payload as any).node_status,
  };

  return apiRequest<AtomicNode>(`/nodes/${nodeId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/**
 * 物理删除节点（及其子树）
 */
export async function deleteNode(nodeId: string): Promise<void> {
  await apiDelete<void>(`/nodes/${nodeId}`);
}

/**
 * 宏观剪枝：归档分支
 *
 * 将当前节点及其所有子孙节点的 node_status 设为 'archived'。
 * 默认树/列表视图会过滤掉已归档节点，从而在 UI 上“剪掉”这一整条分支。
 */
export async function archiveBranch(
  nodeId: string
): Promise<{ node_id: string; archived_count: number }> {
  return apiPost<{ node_id: string; archived_count: number }>(
    `/nodes/${nodeId}/archive-branch`,
    {}
  );
}

/**
 * 健康检查（测试后端连接）
 */
export async function healthCheck(): Promise<{
  status: string;
  service: string;
  version: string;
}> {
  return apiGet("/");
}


