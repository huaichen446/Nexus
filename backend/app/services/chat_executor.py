import os
import time
import json
import logging
import functools
import uuid
from typing import List, Dict, Any, Optional, Generator, TypedDict
from datetime import datetime

import tiktoken
import litellm
from sqlalchemy.orm import Session

from backend.app.models import AtomicNodeModel

logger = logging.getLogger(__name__)

litellm.suppress_instrumentation = True  

class BuildMessagesResult(TypedDict):
    messages: List[Dict[str, str]]
    total_tokens: int
    max_tokens: int
    overflow: bool

class ChatExecutor:
    """
    Backend core for executing chat completions on an AtomicNode.
    
    Responsibilities:
    - Build chat context (system + history + new user message).
    - Call litellm.completion(stream=True) to support multiple providers.
    - Stream SSE events chunk-by-chunk to the frontend.
    - Persist user / assistant messages back into node.internal_state.chat_history.
    """

    # Default context size 
    _MAX_CONTEXT_TOKENS = 128000

    # ============================
    # Phase A: Helpers & Calculation
    # ============================

    def _get_llm_settings(self, node: AtomicNodeModel) -> Dict[str, Any]:
        config: Dict[str, Any] = node.config or {}
        llm_settings: Dict[str, Any] = config.get("llm_settings", {}) or {}
        return llm_settings

    @functools.lru_cache(maxsize=16)
    def _get_tiktoken_encoding(self, model_name: str):
        """
        [Performance Optimization]
        Cached version of encoding loader.
        Loading encoding files (cl100k_base etc) is I/O heavy.
        Caching this provides significant speedup for frequent calls.
        """
        try:
            return tiktoken.encoding_for_model(model_name)
        except Exception:
            # Fallback to standard OpenAI encoding if specific model not found
            return tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, messages: List[Dict[str, str]], model_name: str) -> int:
        """
        Approximate token count using cached encoding.
        """
        encoding = self._get_tiktoken_encoding(model_name)
        total = 0
        for msg in messages:
            content = msg.get("content") or ""
            total += len(encoding.encode(content))
        return total

    def _get_cached_history_tokens(
        self,
        internal_state: Dict[str, Any],
        history: List[Dict[str, Any]],
        model_name: str,
    ) -> Optional[int]:
        """
        Retrieve cached history tokens if valid.
        """
        cache = internal_state.get("_history_token_cache")
        if cache is None:
            return None

        cached_count = cache.get("message_count")
        cached_tokens = cache.get("tokens")
        cached_model = cache.get("model")

        if (
            cached_count is not None
            and cached_tokens is not None
            and cached_model == model_name
            and cached_count == len(history)
        ):
            return cached_tokens

        return None

    def _calculate_history_tokens(
        self,
        history_messages: List[Dict[str, str]],
        model_name: str,
    ) -> int:
        if not history_messages:
            return 0
        return self._count_tokens(history_messages, model_name)

    def _build_messages(
        self,
        node: AtomicNodeModel,
        user_content: str,
    ) -> BuildMessagesResult:
        """
        Constructs the message list and checks for token overflow.
        """
        # Fail fast for invalid inputs
        if user_content is None or not isinstance(user_content, str):
            raise TypeError("user_content must be a valid string.")

        llm_settings = self._get_llm_settings(node)
        model_name: str = llm_settings.get("model", "gpt-4o")
        max_output_tokens: int = llm_settings.get("max_tokens") or 1024
        
        # Calculate max input
        max_input_tokens = max(self._MAX_CONTEXT_TOKENS - max_output_tokens, 1024)

        internal_state: Dict[str, Any] = node.internal_state or {}
        history: List[Dict[str, Any]] = internal_state.get("chat_history", []) or []
        system_instruction: str = internal_state.get("system_instruction", "") or ""

        system_message = {"role": "system", "content": system_instruction}
        latest_user_message = {"role": "user", "content": user_content}

        # Validate and prepare history
        history_messages: List[Dict[str, str]] = []
        for msg in history:
            role = msg.get("role")
            # Validate role: must be "user" or "assistant" (v1: fail fast if invalid)
            if role not in ("user", "assistant"):
                logger.warning(
                    f"Invalid role '{role}' in chat_history, defaulting to 'user'. "
                    f"Message content: {msg.get('content', '')[:50]}..."
                )
                role = "user"  # Fallback for data integrity
            history_messages.append({
                "role": role,
                "content": msg.get("content", ""),
            })

        messages = [system_message] + history_messages + [latest_user_message]

        # Smart Token Counting with Cache
        cached_history_tokens = self._get_cached_history_tokens(internal_state, history, model_name)

        if cached_history_tokens is not None:
            new_messages = [system_message, latest_user_message]
            new_tokens = self._count_tokens(new_messages, model_name)
            total_tokens = cached_history_tokens + new_tokens
        else:
            total_tokens = self._count_tokens(messages, model_name)

        overflow = total_tokens > max_input_tokens

        return BuildMessagesResult(
            messages=messages,
            total_tokens=total_tokens,
            max_tokens=max_input_tokens,
            overflow=overflow,
        )

    # ============================
    # Phase B: Database Persistence
    # ============================

    def _append_chat_message(
        self,
        db: Session,
        node: AtomicNodeModel,
        role: str,
        content: str,
        timestamp: Optional[float] = None,
        message_id: Optional[str] = None,
    ) -> None:
        """
        Append a chat message into node.internal_state.chat_history and commit.
        Also updates the history token cache for performance optimization.

        IMPORTANT: internal_state is a JSON column.
        To trigger SQLAlchemy's change tracking, we must reassign the dict.
        
        Args:
            message_id: 可选的消息 ID。如果提供，将使用该 ID；否则生成新的 UUID。
                       用于编辑消息时保留原 message_id。
        """
        if timestamp is None:
            timestamp = time.time()

        # Create a fresh copy of internal_state to trigger SQLAlchemy change detection
        state: Dict[str, Any] = dict(node.internal_state or {})
        history: List[Dict[str, Any]] = state.get("chat_history") or []

        history.append({
            "id": message_id or str(uuid.uuid4()),  # 使用提供的 ID 或生成新的 UUID
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "is_disabled": False,
        })
        state["chat_history"] = history

        # Update Cache
        llm_settings = self._get_llm_settings(node)
        model_name = llm_settings.get("model", "gpt-4o")
        
        # Recalculate only history tokens
        history_msgs = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]
        history_tokens = self._calculate_history_tokens(history_msgs, model_name)

        state["_history_token_cache"] = {
            "tokens": history_tokens,
            "message_count": len(history),
            "model": model_name,
        }

        node.internal_state = state
        node.updated_at = datetime.utcnow()
        
        db.add(node)
        db.commit()
        db.refresh(node)

    def save_partial_assistant_message(
        self,
        db: Session,
        node: AtomicNodeModel,
        content: str,
    ) -> None:
        """
        保存部分完成的助手消息（当用户取消流式响应时调用）。
        
        检查最后一条消息是否是用户消息且没有对应的助手回复，
        如果是，则将部分内容追加为助手消息。
        """
        if not content or not content.strip():
            # 空内容不保存
            return
        
        # Create a fresh copy of internal_state
        state: Dict[str, Any] = dict(node.internal_state or {})
        history: List[Dict[str, Any]] = state.get("chat_history") or []
        
        # 检查最后一条消息
        if history:
            last_msg = history[-1]
            # 如果最后一条是用户消息，追加助手回复
            if last_msg.get("role") == "user":
                # 追加部分完成的助手消息
                self._append_chat_message(db, node, role="assistant", content=content.strip())
            else:
                # 如果最后一条已经是助手消息，可能是重复调用，不处理
                logger.warning(f"Last message is already assistant message, skipping partial save for node {node.id}")
        else:
            # 历史记录为空，直接追加助手消息（理论上不应该发生）
            logger.warning(f"Chat history is empty, appending assistant message for node {node.id}")
            self._append_chat_message(db, node, role="assistant", content=content.strip())

    # ============================
    # Phase C: Unified Execution
    # ============================

    def _get_provider_config(self, provider: str, model: str) -> Dict[str, Any]:
        """
        [修改] 以前只返回模型名字符串，现在返回一个包含所有连接参数的字典。
        """
        config = {}
        
        if provider == "zhipuai":
            # 这里的配置和你测试成功的脚本完全一致
            config["model"] = model
            config["custom_llm_provider"] = "openai"
            config["api_base"] = "https://open.bigmodel.cn/api/paas/v4/"
            config["api_key"] = os.getenv("ZHIPUAI_API_KEY")
        elif provider == "openai":
            config["model"] = model
        elif provider == "anthropic":
            config["model"] = model
        else:
            # 其他情况的处理
            if "/" not in model:
                config["model"] = f"{provider}/{model}"
            else:
                config["model"] = model
                
        return config

    def stream_chat_completion(
        self,
        db: Session,
        node: AtomicNodeModel,
        user_content: str,
    ) -> Generator[str, None, None]:
        """
        Unified Entrypoint.
        Supports OpenAI, ZhipuAI, Anthropic via LiteLLM.
        """
        start_ts = time.time()

        # 1. Build Context
        try:
            build_result = self._build_messages(node, user_content)
        except Exception as e:
            logger.exception("Error building messages")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            return

        if build_result["overflow"]:
            error_payload = {
                "event": "error",
                "message": f"Token limit exceeded ({build_result['total_tokens']}/{build_result['max_tokens']})",
                "type": "token_overflow"
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            return
        
        messages = build_result["messages"]

        # 2. Prepare LiteLLM Config
        llm_settings = self._get_llm_settings(node)
        provider = llm_settings.get("provider", "openai")
        raw_model = llm_settings.get("model", "gpt-4o")
        
        provider_config = self._get_provider_config(provider, raw_model)
        
        # 3. Persist User Message
        self._append_chat_message(db, node, role="user", content=user_content)

        # 4. Stream Execution
        logger.info(f"Starting LLM stream: {provider_config['model']} for node {node.id}")
        
        assistant_completion = ""
        completion_tokens = 0
        input_tokens = build_result['total_tokens'] # Approximate start tokens

        try:
            # Unified call for ALL providers (ZhipuAI included)
            response = litellm.completion(
                messages=messages,
                stream=True,
                temperature=llm_settings.get("temperature"),
                max_tokens=llm_settings.get("max_tokens"),
                top_p=llm_settings.get("top_p"),
                **provider_config
            )

            for chunk in response:
                delta_content = None
                
                # Robust chunk parsing
                if hasattr(chunk, "choices") and chunk.choices:
                    delta = chunk.choices[0].delta
                    delta_content = delta.content
                
                if delta_content:
                    assistant_completion += delta_content
                    # Simple heuristic: 1 token ~= 1 char for Chinese, 4 chars for English
                    # Precise counting happens at the end
                    yield f"data: {json.dumps({'delta': delta_content}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"LLM Stream Error ({provider_config['model']})")
            error_payload = {
                "event": "error", 
                "message": f"LLM Provider Error: {str(e)}",
                "type": "provider_error"
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            return

        # 5. Finalize & Stats
        end_ts = time.time()
        latency_ms = int((end_ts - start_ts) * 1000)
        
        # Calculate precise output tokens using cached encoder
        encoding = self._get_tiktoken_encoding(raw_model)
        output_tokens = len(encoding.encode(assistant_completion))
        
        # Persist Assistant Message
        self._append_chat_message(db, node, role="assistant", content=assistant_completion)

        # Emit Done Event
        final_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "model": raw_model
        }
        
        yield f"data: {json.dumps({'event': 'done', 'usage': final_usage}, ensure_ascii=False)}\n\n"


chat_executor = ChatExecutor()