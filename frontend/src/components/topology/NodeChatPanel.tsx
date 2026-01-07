/**
 * 节点聊天面板组件
 * 
 * 功能：
 * 1. 显示聊天历史记录
 * 2. 发送消息并接收流式响应
 * 3. 显示使用统计（tokens, cost, latency）
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Send, Loader2, AlertCircle, Info } from 'lucide-react';
import { streamNodeChat, savePartialResponse, type ChatStreamDelta } from '../../api/chat';
import { getNode } from '../../api/topology';
import type { AtomicNode, ChatMessage } from '../../types/node';

interface NodeChatPanelProps {
  /** 当前节点 */
  node: AtomicNode;
  /** 节点更新后的回调 */
  onNodeUpdated?: (node: AtomicNode) => void;
}

export function NodeChatPanel({ node, onNodeUpdated }: NodeChatPanelProps) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<ChatStreamDelta['usage'] | null>(null);
  const [currentResponse, setCurrentResponse] = useState('');
  // 本地消息状态（乐观更新）
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const userHasScrolledRef = useRef(false);
  const shouldAutoScrollRef = useRef(true);
  const scrollThrottleRef = useRef<number | null>(null);

  // 从节点获取聊天历史（作为 fallback）
  const chatHistory = node.internal_state?.chat_history || [];
  
  // 初始化时从 node prop 加载历史消息到本地状态
  useEffect(() => {
    if (node.internal_state?.chat_history) {
      setLocalMessages(node.internal_state.chat_history);
    } else {
      setLocalMessages([]);
    }
  }, [node.id]); // 只在节点 ID 变化时重新加载

  // 检查是否接近底部（距离底部 100px 以内认为是"接近底部"）
  const isNearBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return true;
    
    const threshold = 100;
    const distanceFromBottom = 
      container.scrollHeight - container.scrollTop - container.clientHeight;
    return distanceFromBottom <= threshold;
  }, []);

  // 智能滚动到底部（只在用户接近底部时滚动）
  const scrollToBottom = useCallback((force = false) => {
    // 如果用户手动向上滚动过，且不在底部，不自动滚动
    if (!force && userHasScrolledRef.current && !isNearBottom()) {
      return;
    }

    // 节流：限制滚动频率（每 100ms 最多滚动一次）
    if (scrollThrottleRef.current !== null) {
      return;
    }

    scrollThrottleRef.current = window.setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      scrollThrottleRef.current = null;
    }, 100);
  }, [isNearBottom]);

  // 监听滚动事件，检测用户是否手动滚动
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      // 如果用户滚动到接近底部，重置标志，允许自动滚动
      if (isNearBottom()) {
        userHasScrolledRef.current = false;
        shouldAutoScrollRef.current = true;
      } else {
        // 用户向上滚动，标记为手动滚动
        userHasScrolledRef.current = true;
        shouldAutoScrollRef.current = false;
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [isNearBottom]);

  // 当新消息到达时，智能滚动（使用本地消息状态）
  useEffect(() => {
    // 新消息到达时，如果用户接近底部，自动滚动
    if (shouldAutoScrollRef.current || isNearBottom()) {
      scrollToBottom();
    }
  }, [localMessages.length, scrollToBottom, isNearBottom]);

  // 流式响应更新时的滚动（节流处理）
  useEffect(() => {
    if (currentResponse && isStreaming) {
      // 只在用户接近底部时滚动
      if (shouldAutoScrollRef.current || isNearBottom()) {
        scrollToBottom();
      }
    }
  }, [currentResponse, isStreaming, scrollToBottom, isNearBottom]);

  // 发送新消息时，强制滚动到底部（使用本地消息状态）
  useEffect(() => {
    if (!isStreaming && localMessages.length > 0) {
      // 重置滚动标志，允许自动滚动
      userHasScrolledRef.current = false;
      shouldAutoScrollRef.current = true;
      scrollToBottom(true);
    }
  }, [isStreaming, localMessages.length, scrollToBottom]);

  // 清理节流定时器
  useEffect(() => {
    return () => {
      if (scrollThrottleRef.current !== null) {
        clearTimeout(scrollThrottleRef.current);
      }
    };
  }, []);

  // 发送消息
  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);
    setCurrentResponse('');
    setUsage(null);
    setIsStreaming(true);
    
    // 发送新消息时，重置滚动标志，允许自动滚动
    userHasScrolledRef.current = false;
    shouldAutoScrollRef.current = true;
    
    // 乐观更新：立即将用户消息添加到本地状态
    const userMessageObj: ChatMessage = {
      role: 'user',
      content: userMessage,
      timestamp: Date.now() / 1000,
      is_disabled: false,
    };
    setLocalMessages((prev) => [...prev, userMessageObj]);
    
    // 立即滚动到底部，显示用户消息
    setTimeout(() => scrollToBottom(true), 0);

    try {
      // 使用 streamNodeChat 返回的 AbortController（这是实际用于请求的 controller）
      abortControllerRef.current = streamNodeChat(
        node.id,
        userMessage,
        // onDelta: 接收流式文本片段
        (data: ChatStreamDelta) => {
          if (data.delta) {
            setCurrentResponse((prev) => {
              const newResponse = prev + data.delta;
              // 同时更新本地状态中的助手消息
              setLocalMessages((prevMessages) => {
                const newMessages = [...prevMessages];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg && lastMsg.role === 'assistant') {
                  // 更新最后一条助手消息
                  lastMsg.content = newResponse;
                } else {
                  // 添加新的助手消息
                  newMessages.push({
                    role: 'assistant',
                    content: newResponse,
                    timestamp: Date.now() / 1000,
                    is_disabled: false,
                  });
                }
                return newMessages;
              });
              return newResponse;
            });
          }
        },
        // onDone: 完成时接收使用统计
        async (data: ChatStreamDelta) => {
          setIsStreaming(false);
          setUsage(data.usage || null);
          
          // 在清空 currentResponse 之前，先保存最终内容到本地状态
          setCurrentResponse((finalResponse) => {
            // 确保本地状态中的最后一条助手消息包含完整内容
            setLocalMessages((prevMessages) => {
              const newMessages = [...prevMessages];
              const lastMsg = newMessages[newMessages.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                // 更新为最终完整内容
                lastMsg.content = finalResponse;
              } else if (finalResponse) {
                // 如果没有助手消息，添加一条
                newMessages.push({
                  role: 'assistant',
                  content: finalResponse,
                  timestamp: Date.now() / 1000,
                  is_disabled: false,
                });
              }
              return newMessages;
            });
            return ''; // 清空 currentResponse
          });
          
          // 刷新节点数据以获取更新后的历史记录（后台同步）
          try {
            const updatedNode = await getNode(node.id);
            // 同步服务器状态到本地（确保一致性）
            if (updatedNode.internal_state?.chat_history) {
              setLocalMessages(updatedNode.internal_state.chat_history);
            }
            onNodeUpdated?.(updatedNode);
          } catch (err) {
            console.error('Failed to refresh node after chat:', err);
            // 即使刷新失败，本地状态仍然可用
          }
        },
        // onError: 错误处理
        (error: Error) => {
          setIsStreaming(false);
          setError(error.message);
          // 错误时移除最后添加的助手消息（如果有不完整的）
          setCurrentResponse((current) => {
            setLocalMessages((prevMessages) => {
              const lastMsg = prevMessages[prevMessages.length - 1];
              // 如果最后一条是助手消息且内容与当前响应匹配，移除它
              if (lastMsg && lastMsg.role === 'assistant' && lastMsg.content === current) {
                return prevMessages.slice(0, -1);
              }
              return prevMessages;
            });
            return ''; // 清空 currentResponse
          });
        }
      );
    } catch (err) {
      setIsStreaming(false);
      setError(err instanceof Error ? err.message : '发送消息失败');
      // 错误时移除用户消息（回滚乐观更新）
      setLocalMessages((prevMessages) => prevMessages.slice(0, -1));
    }
  };

  // 取消请求
  const handleCancel = async () => {
    if (!abortControllerRef.current || !isStreaming) {
      return;
    }
    
    // 1. 立即中断连接（停止接收新的 delta）
    abortControllerRef.current.abort();
    
    // 2. 立即重置流式状态，让按钮立即响应
    setIsStreaming(false);
    
    // 3. 使用函数式更新获取 currentResponse 的最新值
    setCurrentResponse((current) => {
      const partialContent = current.trim();
      
      // 4. 如果有已显示的内容，保存它并更新本地状态
      if (partialContent) {
        // 异步保存，不阻塞取消流程
        savePartialResponse(node.id, partialContent)
          .then(() => {
            // 更新本地状态：确保最后一条助手消息包含保存的内容
            setLocalMessages((prevMessages) => {
              const newMessages = [...prevMessages];
              const lastMsg = newMessages[newMessages.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                lastMsg.content = partialContent;
              } else {
                // 如果最后一条不是助手消息，添加一条
                newMessages.push({
                  role: 'assistant',
                  content: partialContent,
                  timestamp: Date.now() / 1000,
                  is_disabled: false,
                });
              }
              return newMessages;
            });
            
            // 刷新节点数据，获取更新后的历史记录（后台同步）
            return getNode(node.id);
          })
          .then((updatedNode) => {
            // 同步服务器状态到本地（确保一致性）
            if (updatedNode.internal_state?.chat_history) {
              setLocalMessages(updatedNode.internal_state.chat_history);
            }
            onNodeUpdated?.(updatedNode);
          })
          .catch((err) => {
            console.error('Failed to save partial response or refresh node:', err);
            // 即使保存失败，本地状态仍然保留已显示的内容
          });
      }
      
      return ''; // 清空 currentResponse
    });
    
    // 5. 重置其他状态
    setUsage(null);
  };

  // 处理 Enter 键（Shift+Enter 换行）
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 rounded-lg border border-slate-200 bg-white shadow-sm"
    >
      {/* 头部 */}
      <div className="border-b border-slate-200 bg-slate-50 px-6 py-4">
        <h3 className="text-lg font-semibold text-slate-900">聊天</h3>
        <p className="mt-1 text-xs text-slate-500">
          与节点 "{node.tags[0] || node.id.slice(0, 8)}" 对话
        </p>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="border-b border-red-200 bg-red-50 px-6 py-3">
          <div className="flex items-center gap-2 text-sm text-red-900">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* 使用统计 */}
      {usage && (
        <div className="border-b border-slate-200 bg-blue-50 px-6 py-3">
          <div className="flex items-center gap-2 text-xs text-blue-900">
            <Info className="h-4 w-4" />
            <span>
              输入: {usage.input_tokens} tokens | 
              输出: {usage.output_tokens} tokens | 
              延迟: {usage.latency_ms}ms
              {usage.cost_usd && ` | 成本: $${usage.cost_usd.toFixed(6)}`}
            </span>
          </div>
        </div>
      )}

      {/* 聊天消息区域 */}
      <div 
        ref={messagesContainerRef}
        className="h-96 overflow-y-auto px-6 py-4"
      >
        <div className="space-y-4">
          {/* 历史消息（使用本地状态，fallback 到 chatHistory） */}
          {(localMessages.length > 0 ? localMessages : chatHistory).map((msg, index) => (
            <div
              key={index}
              className={`flex ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.role === 'user'
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-900'
                }`}
              >
                <div className="text-sm whitespace-pre-wrap break-words">
                  {msg.content}
                </div>
                <div
                  className={`mt-1 text-xs ${
                    msg.role === 'user'
                      ? 'text-slate-300'
                      : 'text-slate-500'
                  }`}
                >
                  {new Date(msg.timestamp * 1000).toLocaleTimeString('zh-CN')}
                </div>
              </div>
            </div>
          ))}

          {/* 当前流式响应 */}
          {isStreaming && currentResponse && (
            <div className="flex justify-start">
              <div className="max-w-[80%] rounded-lg bg-slate-100 px-4 py-2">
                <div className="text-sm whitespace-pre-wrap break-words">
                  {currentResponse}
                  <span className="inline-block w-2 h-4 bg-slate-400 animate-pulse ml-1" />
                </div>
              </div>
            </div>
          )}

          {/* 滚动到底部的占位符 */}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 输入区域 */}
      <div className="border-t border-slate-200 px-6 py-4">
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            disabled={isStreaming}
            rows={3}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20 disabled:bg-slate-50 disabled:text-slate-500"
          />
          {isStreaming ? (
            <button
              onClick={handleCancel}
              className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              取消
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="h-4 w-4" />
              发送
            </button>
          )}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          系统提示词: {node.internal_state?.system_instruction?.slice(0, 50) || '（未设置）'}...
        </p>
      </div>
    </motion.div>
  );
}
