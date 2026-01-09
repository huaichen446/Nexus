/**
 * 聊天相关 API 调用
 *
 * 对应后端路由：backend/app/routers/chat.py
 *
 * API 端点映射：
 * - POST /nodes/{node_id}/chat/stream → streamNodeChat (SSE)
 * - POST /nodes/{node_id}/chat/partial → savePartialResponse
 */

import type { AtomicNode } from '../types/node';

// API 基础 URL（开发环境）
const API_BASE_URL = 'http://127.0.0.1:8000';

/**
 * SSE 事件类型
 */
export interface ChatStreamDelta {
  delta?: string;
  event?: 'done' | 'error';
  message?: string;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    cost_usd?: number | null;
    latency_ms?: number;
  };
}

/**
 * 流式聊天完成回调函数类型
 */
export type ChatStreamCallback = (data: ChatStreamDelta) => void;
export type ChatStreamErrorCallback = (error: Error) => void;

/**
 * 流式聊天完成
 *
 * @param nodeId - 节点 ID
 * @param content - 用户消息内容
 * @param onDelta - 接收到增量文本时的回调
 * @param onDone - 完成时的回调（包含 usage 信息）
 * @param onError - 错误时的回调
 * @returns AbortController（可用于取消请求）
 */
export function streamNodeChat(
  nodeId: string,
  content: string,
  onDelta: ChatStreamCallback,
  onDone?: ChatStreamCallback,
  onError?: ChatStreamErrorCallback
): AbortController {
  const abortController = new AbortController();

  const url = `${API_BASE_URL}/nodes/${nodeId}/chat/stream`;

  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          // 解码 chunk 并添加到 buffer
          buffer += decoder.decode(value, { stream: true });

          // 按行分割，处理完整的 SSE 消息
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // 保留最后一个不完整的行

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6); // 移除 'data: ' 前缀
                const data: ChatStreamDelta = JSON.parse(jsonStr);

                // 处理增量文本
                if (data.delta) {
                  onDelta(data);
                }

                // 处理完成事件
                if (data.event === 'done' && onDone) {
                  onDone(data);
                }

                // 处理错误事件
                if (data.event === 'error') {
                  const error = new Error(data.message || 'Chat stream error');
                  if (onError) {
                    onError(error);
                  } else {
                    throw error;
                  }
                }
              } catch (parseError) {
                console.warn('Failed to parse SSE data:', line, parseError);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    })
    .catch((error) => {
      if (error.name === 'AbortError') {
        // 用户主动取消，不触发错误回调
        return;
      }
      if (onError) {
        onError(error);
      } else {
        console.error('Chat stream error:', error);
      }
    });

  return abortController;
}

/**
 * 保存部分完成的助手消息（当用户取消流式响应时调用）
 *
 * @param nodeId - 节点 ID
 * @param content - 已显示的部分助手消息内容
 * @returns 更新后的节点数据
 */
export async function savePartialResponse(
  nodeId: string,
  content: string
): Promise<AtomicNode> {
  const url = `${API_BASE_URL}/nodes/${nodeId}/chat/partial`;
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * 删除消息（修剪）
 * 
 * 删除指定的用户消息及其所有后续消息（包括对应的 assistant 回复）。
 * 
 * @param nodeId - 节点 ID
 * @param messageId - 要删除的消息 ID
 * @returns 删除结果（包含删除的消息数量）
 */
export async function deleteMessage(
  nodeId: string,
  messageId: string
): Promise<{
  node_id: string;
  message_id: string;
  deleted_count: number;
  remaining_messages: number;
}> {
  const url = `${API_BASE_URL}/nodes/${nodeId}/messages/${messageId}`;
  
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * 编辑用户消息并重新生成（流式）
 * 
 * 编辑指定的用户消息，删除其后续所有消息，然后重新生成 assistant 回复。
 * 
 * @param nodeId - 节点 ID
 * @param messageId - 要编辑的消息 ID
 * @param content - 新的消息内容
 * @param onDelta - 接收到增量文本时的回调
 * @param onDone - 完成时的回调（包含 usage 信息）
 * @param onError - 错误时的回调
 * @returns AbortController（可用于取消请求）
 */
export function editMessageAndRegenerate(
  nodeId: string,
  messageId: string,
  content: string,
  onDelta: ChatStreamCallback,
  onDone?: ChatStreamCallback,
  onError?: ChatStreamErrorCallback
): AbortController {
  const abortController = new AbortController();

  const url = `${API_BASE_URL}/nodes/${nodeId}/messages/${messageId}`;

  fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      content,
      regenerate: true,
    }),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          // 解码 chunk 并添加到 buffer
          buffer += decoder.decode(value, { stream: true });

          // 按行分割，处理完整的 SSE 消息
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // 保留最后一个不完整的行

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6); // 移除 'data: ' 前缀
                const data: ChatStreamDelta = JSON.parse(jsonStr);

                // 处理增量文本
                if (data.delta) {
                  onDelta(data);
                }

                // 处理完成事件
                if (data.event === 'done' && onDone) {
                  onDone(data);
                }

                // 处理错误事件
                if (data.event === 'error') {
                  const error = new Error(data.message || 'Edit message stream error');
                  if (onError) {
                    onError(error);
                  } else {
                    throw error;
                  }
                }
              } catch (parseError) {
                console.warn('Failed to parse SSE data:', line, parseError);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    })
    .catch((error) => {
      if (error.name === 'AbortError') {
        // 用户主动取消，不触发错误回调
        return;
      }
      if (onError) {
        onError(error);
      } else {
        console.error('Edit message stream error:', error);
      }
    });

  return abortController;
}