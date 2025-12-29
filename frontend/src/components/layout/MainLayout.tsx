import { useState } from "react";
import { motion } from "framer-motion";
import { Plus, Mic, Sparkles } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { chatsMock } from "../../data/chats";
import { projectsMock } from "../../data/projects";
import { ApiConnectionTest } from "../topology/ApiConnectionTest";
import { NodeTree } from "../topology/NodeTree";
import { NodeList } from "../topology/NodeList";
import { NodeCreateForm } from "../topology/NodeCreateForm";
import { NodeDetailPanel } from "../topology/NodeDetailPanel";
import type { AtomicNode } from "../../types/node";

export function MainLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(
    projectsMock[0]?.id || null
  );
  const [selectedNode, setSelectedNode] = useState<AtomicNode | null>(null);
  const [viewMode, setViewMode] = useState<'tree' | 'list'>('tree');
  const [refreshKey, setRefreshKey] = useState(0); // 用于触发刷新

  // 刷新节点列表
  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  // 节点创建成功回调
  const handleNodeCreated = (node: AtomicNode) => {
    console.log('Node created:', node);
    handleRefresh();
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-900">
      <Sidebar
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        chats={chatsMock}
        projects={projectsMock}
        activeChatId={chatsMock[0]?.id}
        activeProjectId={activeProjectId || undefined}
      />

      <div className="flex flex-1 flex-col bg-white">
        <header className="flex h-14 items-center border-b border-slate-200 px-6">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-full bg-gradient-to-tr from-sky-500 via-violet-500 to-amber-400 shadow-sm" />
            <span className="text-lg font-semibold tracking-tight">Nexus</span>
          </div>
        </header>

        <main className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-6">
            <div className="mx-auto max-w-6xl">
              {/* 项目选择和视图切换 */}
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <select
                    value={activeProjectId || ''}
                    onChange={(e) => setActiveProjectId(e.target.value || null)}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                  >
                    <option value="">选择项目</option>
                    {projectsMock.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                  
                  {/* 创建节点按钮 */}
                  {activeProjectId && (
                    <NodeCreateForm
                      projectId={activeProjectId}
                      parentId={selectedNode?.id || null}
                      onSuccess={handleNodeCreated}
                      onRefresh={handleRefresh}
                    />
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setViewMode('tree')}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      viewMode === 'tree'
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    树形视图
                  </button>
                  <button
                    onClick={() => setViewMode('list')}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      viewMode === 'list'
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    列表视图
                  </button>
                </div>
              </div>

              {/* 节点显示区域 */}
              <div className="mb-6" key={refreshKey}>
                {viewMode === 'tree' ? (
                  <NodeTree
                    projectId={activeProjectId}
                    onSelectNode={setSelectedNode}
                    onRefresh={handleRefresh}
                  />
                ) : (
                  <NodeList
                    projectId={activeProjectId}
                    onSelectNode={setSelectedNode}
                    onRefresh={handleRefresh}
                  />
                )}
              </div>

              {/* 选中的节点详情 */}
              {selectedNode && (
                <>
                  <NodeDetailPanel
                    node={selectedNode}
                    projectId={activeProjectId}
                    onNodeUpdated={(updatedNode) => {
                      setSelectedNode(updatedNode);
                      handleRefresh();
                    }}
                    onNodeDeleted={() => {
                      setSelectedNode(null);
                      handleRefresh();
                    }}
                    onNodeArchived={() => {
                      setSelectedNode(null);
                      handleRefresh();
                    }}
                    onRefresh={handleRefresh}
                    onSelectNode={setSelectedNode}
                  />

                  {/* 在节点详情下提供"创建子节点"入口 */}
                  {activeProjectId && (
                    <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
                      <h4 className="mb-3 text-sm font-semibold text-slate-900">
                        创建子节点
                      </h4>
                      <NodeCreateForm
                        projectId={activeProjectId}
                        parentId={selectedNode.id}
                        onSuccess={handleNodeCreated}
                        onRefresh={handleRefresh}
                      />
                    </div>
                  )}
                </>
              )}

              {/* API 连接测试组件（保留用于调试） */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: 0.1 }}
                className="mt-8"
              >
                <ApiConnectionTest />
              </motion.div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}









