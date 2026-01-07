from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.schemas import NodeChatRequest, PartialChatRequest, AtomicNode
from backend.app.services.topology_service import topology_service
from backend.app.services.chat_executor import chat_executor

router = APIRouter(
    prefix="/nodes",
    tags=["Chat"],
)


@router.post("/{node_id}/chat/stream")
def stream_node_chat(
    node_id: str,
    body: NodeChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Stream a chat completion for the given node.

    Request body:
    - { "content": "user message" }

    Response:
    - text/event-stream (SSE), with "data: {...}\\n\\n" chunks.
    """
    node = topology_service.get_node(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    generator = chat_executor.stream_chat_completion(
        db=db,
        node=node,
        user_content=body.content,
    )

    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/{node_id}/chat/partial", response_model=AtomicNode)
def save_partial_chat_response(
    node_id: str,
    body: PartialChatRequest,
    db: Session = Depends(get_db),
) -> AtomicNode:
    """
    保存部分完成的助手消息（当用户取消流式响应时调用）。
    
    这个端点用于保存用户已经看到但未完整生成的消息内容。
    确保对话历史的完整性，避免出现孤立的用户消息。
    """
    node = topology_service.get_node(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    # 保存部分完成的助手消息
    chat_executor.save_partial_assistant_message(
        db=db,
        node=node,
        content=body.content,
    )
    
    # 刷新节点以获取最新状态
    db.refresh(node)
    
    # 转换为响应模型
    return AtomicNode.model_validate(node)

