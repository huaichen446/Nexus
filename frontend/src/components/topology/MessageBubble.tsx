/**
 * 消息气泡组件
 * 
 * 功能：
 * 1. 显示消息内容（用户/助手）
 * 2. 悬停时显示操作工具栏（仅用户消息）
 * 3. 支持编辑模式（仅用户消息）
 */

import { useState, useRef, useEffect } from 'react';
import { Copy, Edit2, Trash2, Check, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ChatMessage } from '../../types/node';

interface MessageBubbleProps {
  /** 消息对象 */
  message: ChatMessage;
  /** 是否为流式响应（显示加载动画） */
  isStreaming?: boolean;
  /** 复制消息回调 */
  onCopy?: (content: string) => void;
  /** 编辑消息回调 */
  onEdit?: (messageId: string, newContent: string) => void;
  /** 删除消息回调 */
  onDelete?: (messageId: string) => void;
}

export function MessageBubble({
  message,
  isStreaming = false,
  onCopy,
  onEdit,
  onDelete,
}: MessageBubbleProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isUserMessage = message.role === 'user';

  // 编辑模式时自动聚焦 textarea
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      // 将光标移到末尾
      const length = textareaRef.current.value.length;
      textareaRef.current.setSelectionRange(length, length);
    }
  }, [isEditing]);

  // 处理复制
  const handleCopy = () => {
    if (onCopy) {
      onCopy(message.content);
    } else {
      // 默认行为：复制到剪贴板
      navigator.clipboard.writeText(message.content).catch((err) => {
        console.error('Failed to copy:', err);
      });
    }
  };

  // 处理编辑
  const handleEdit = () => {
    if (!message.id) {
      console.warn('Message ID is required for editing');
      return;
    }
    setIsEditing(true);
    setEditContent(message.content);
  };

  // 保存编辑
  const handleSave = () => {
    if (!message.id || !onEdit) {
      return;
    }
    const trimmedContent = editContent.trim();
    if (trimmedContent && trimmedContent !== message.content) {
      onEdit(message.id, trimmedContent);
    }
    setIsEditing(false);
  };

  // 取消编辑
  const handleCancel = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  // 处理删除
  const handleDelete = () => {
    if (!message.id) {
      console.warn('Message ID is required for deletion');
      return;
    }
    if (onDelete && window.confirm('确定要删除这条消息及其后续所有消息吗？')) {
      onDelete(message.id);
    }
  };

  // 处理键盘事件（编辑模式）
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      // Ctrl+Enter 保存
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      // Escape 取消
      e.preventDefault();
      handleCancel();
    }
  };

  return (
    <div
      className={`flex ${isUserMessage ? 'justify-end' : 'justify-start'}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative max-w-[80%] group">
        {/* 消息气泡 */}
        <div
          className={`min-w-[150px] rounded-lg px-4 py-2 ${
            isUserMessage
              ? 'bg-slate-900 text-white'
              : 'bg-slate-100 text-slate-900'
          }`}
        >
          {isEditing ? (
            // 编辑模式
            <div className="space-y-2">
              <textarea
                ref={textareaRef}
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={Math.min(editContent.split('\n').length + 1, 10)}
                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-500/20"
                style={{ minHeight: '60px', maxHeight: '200px' }}
              />
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={handleCancel}
                  className="flex items-center gap-1 rounded px-3 py-1 text-xs text-slate-400 hover:bg-slate-800"
                >
                  <X className="h-3 w-3" />
                  取消
                </button>
                <button
                  onClick={handleSave}
                  disabled={!editContent.trim() || editContent.trim() === message.content}
                  className="flex items-center gap-1 rounded bg-slate-700 px-3 py-1 text-xs text-white hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Check className="h-3 w-3" />
                  保存并重新生成
                </button>
              </div>
            </div>
          ) : (
            // 显示模式
            <>
              <div className="text-sm whitespace-pre-wrap break-words">
                {message.content}
                {isStreaming && (
                  <span className="inline-block w-2 h-4 bg-slate-400 animate-pulse ml-1" />
                )}
              </div>
              <div
                className={`mt-1 text-xs ${
                  isUserMessage ? 'text-slate-300' : 'text-slate-500'
                }`}
              >
                {new Date(message.timestamp * 1000).toLocaleTimeString('zh-CN')}
              </div>
            </>
          )}
        </div>

        {/* 操作工具栏（仅用户消息，悬停时显示） */}
        {isUserMessage && !isEditing && (
          <AnimatePresence>
            {isHovered && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.15 }}
                className="absolute -bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-1 rounded-lg bg-slate-800 px-2 py-1 shadow-lg"
              >
                <button
                  onClick={handleCopy}
                  className="p-1.5 rounded hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                  title="复制"
                >
                  <Copy className="h-3.5 w-3.5" />
                </button>
                {onEdit && (
                  <button
                    onClick={handleEdit}
                    className="p-1.5 rounded hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                    title="编辑"
                  >
                    <Edit2 className="h-3.5 w-3.5" />
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={handleDelete}
                    className="p-1.5 rounded hover:bg-slate-700 text-red-400 hover:text-red-300 transition-colors"
                    title="删除"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
