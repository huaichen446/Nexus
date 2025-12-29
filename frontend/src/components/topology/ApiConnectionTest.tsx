/**
 * API 连接测试组件
 * 
 * 用于验证前端是否能成功调用后端 API
 * 这是一个临时组件，用于第一步测试
 */

import { useState } from 'react';
import { healthCheck, getNode } from '../../api/topology';
import type { ApiError } from '../../api/client';

export function ApiConnectionTest() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string>('');
  const [testNodeId, setTestNodeId] = useState<string>('');

  // 测试健康检查
  const testHealthCheck = async () => {
    setStatus('loading');
    setMessage('正在测试后端连接...');

    try {
      const result = await healthCheck();
      setStatus('success');
      setMessage(`✅ 连接成功！\n服务: ${result.service}\n版本: ${result.version}\n状态: ${result.status}`);
    } catch (error) {
      setStatus('error');
      if (error instanceof ApiError) {
        setMessage(`❌ 连接失败！\n错误: ${error.message}\n状态码: ${error.status}`);
      } else {
        setMessage(`❌ 未知错误: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
  };

  // 测试获取节点
  const testGetNode = async () => {
    if (!testNodeId.trim()) {
      setMessage('⚠️ 请输入节点 ID');
      return;
    }

    setStatus('loading');
    setMessage(`正在获取节点 ${testNodeId}...`);

    try {
      const node = await getNode(testNodeId);
      setStatus('success');
      setMessage(
        `✅ 获取节点成功！\n` +
        `ID: ${node.id}\n` +
        `项目: ${node.project_id}\n` +
        `深度: ${node.depth}\n` +
        `子节点数: ${node.children_ids.length}`
      );
    } catch (error) {
      setStatus('error');
      if (error instanceof ApiError) {
        if (error.status === 404) {
          setMessage(`❌ 节点不存在（404）\n节点 ID: ${testNodeId}`);
        } else {
          setMessage(`❌ 获取节点失败！\n错误: ${error.message}\n状态码: ${error.status}`);
        }
      } else {
        setMessage(`❌ 未知错误: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
  };

  return (
    <div className="w-full max-w-2xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">
        API 连接测试
      </h2>

      {/* 健康检查测试 */}
      <div className="mb-6">
        <button
          onClick={testHealthCheck}
          disabled={status === 'loading'}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {status === 'loading' ? '测试中...' : '测试后端连接'}
        </button>
      </div>

      {/* 获取节点测试 */}
      <div className="mb-6">
        <div className="mb-2 flex gap-2">
          <input
            type="text"
            value={testNodeId}
            onChange={(e) => setTestNodeId(e.target.value)}
            placeholder="输入节点 ID 进行测试"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
          />
          <button
            onClick={testGetNode}
            disabled={status === 'loading'}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            获取节点
          </button>
        </div>
        <p className="text-xs text-slate-500">
          提示：如果数据库中没有节点，可以先创建节点，然后使用返回的 ID 进行测试
        </p>
      </div>

      {/* 结果显示 */}
      {message && (
        <div
          className={`rounded-lg border p-4 ${
            status === 'success'
              ? 'border-green-200 bg-green-50 text-green-900'
              : status === 'error'
              ? 'border-red-200 bg-red-50 text-red-900'
              : 'border-slate-200 bg-slate-50 text-slate-900'
          }`}
        >
          <pre className="whitespace-pre-wrap text-sm font-mono">{message}</pre>
        </div>
      )}

      {/* 说明 */}
      <div className="mt-4 rounded-lg bg-slate-50 p-4 text-xs text-slate-600">
        <p className="font-medium mb-2">测试说明：</p>
        <ul className="list-disc list-inside space-y-1">
          <li>点击"测试后端连接"按钮，验证前端是否能访问后端 API</li>
          <li>如果成功，说明前后端连接已建立</li>
          <li>如果失败，请检查：后端是否运行在 http://127.0.0.1:8000</li>
        </ul>
      </div>
    </div>
  );
}

