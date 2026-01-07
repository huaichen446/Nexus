"""
Chatbot 功能验证脚本

使用方法：
1. 确保已安装依赖：pip install -r requirements.txt
2. 设置环境变量（.env 文件或系统环境变量）：
   - OPENAI_API_KEY=your_api_key (如果使用 OpenAI)
   - 或其他 LLM 提供商的 API key
3. 运行：python -m backend.tests.test_chatbot
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from backend.app.database import get_db, engine, Base
from backend.app.models import AtomicNodeModel
from backend.app.services.chat_executor import chat_executor
from backend.app.services.topology_service import topology_service
from backend.app.schemas import (
    AtomicNodeCreate, 
    NodeInternalState, 
    NodeInputContext, 
    NodeOutputArtifact, 
    NodeExecutionConfig, 
    LlmSettings
)

# __file__ 是当前脚本: .../Nexus/backend/tests/test_chatbot.py
# parents[0] 是 tests
# parents[1] 是 backend
# parents[2] 是 Nexus (根目录)
current_file = Path(__file__).resolve()
project_root = current_file.parents[2]
#将根目录加入 Python 路径 (解决 ModuleNotFoundError)
sys.path.insert(0, str(project_root))

#显式加载根目录下的 .env 文件
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✅ 已加载 .env 文件: {env_path}")
else:
    print(f"⚠️ 未找到 .env 文件，路径: {env_path}")

load_dotenv()

# 确保数据库表已创建
Base.metadata.create_all(bind=engine)


def create_test_node(db: Session) -> AtomicNodeModel:
    """创建一个测试节点"""
    import uuid
    from datetime import datetime
    
    node_data = AtomicNodeCreate(
        id=str(uuid.uuid4()),
        project_id="test_project",
        parent_id=None,
        input_context=NodeInputContext(
            content="Test input context"
        ),
        output_artifact=NodeOutputArtifact(
            content="",
            mime_type="text/plain",
            status="empty"
        ),
        internal_state=NodeInternalState(
            system_instruction="你是一个友好的助手。请用中文回答问题。",
            chat_history=[],
            variables={}
        ),
        config=NodeExecutionConfig(
            execution_mode="manual",
            llm_settings=LlmSettings(
                provider="zhipuai",  
                model="glm-4-flash",  
                temperature=0.7,
                max_tokens=1024,
                top_p=None,
                tools=[]
            ),
            automation_rules=None
        ),
        fork_from_node_id=None,
        tags=[],
        author_id="test_user"
    )
    
    node = topology_service.create_node(db, node_data)
    print(f"✅ 测试节点创建成功: {node.id}")
    return node


def test_chatbot(db: Session, node: AtomicNodeModel):
    """测试 chatbot 功能"""
    print("\n" + "="*60)
    print("开始测试 Chatbot 功能")
    print("="*60)
    
    # 测试消息列表
    test_messages = [
        "你好",
        "请介绍一下你自己",
        "1+1等于多少？"
    ]
    
    for i, user_message in enumerate(test_messages, 1):
        print(f"\n--- 测试消息 {i}/{len(test_messages)} ---")
        print(f"👤 用户: {user_message}")
        print("🤖 助手: ", end="", flush=True)
        
        try:
            # 调用 stream_chat_completion
            generator = chat_executor.stream_chat_completion(
                db=db,
                node=node,
                user_content=user_message
            )
            
            # 处理 SSE 流
            assistant_response = ""
            for event in generator:
                # 解析 SSE 格式: "data: {...}\n\n"
                if event.startswith("data: "):
                    data_str = event[6:].strip()  # 移除 "data: " 前缀
                    try:
                        data = json.loads(data_str)
                        
                        if "delta" in data:
                            # 流式输出片段
                            delta = data["delta"]
                            print(delta, end="", flush=True)
                            assistant_response += delta
                        elif "event" in data:
                            # 完成事件
                            if data["event"] == "done":
                                usage = data.get("usage", {})
                                print(f"\n\n📊 使用统计:")
                                print(f"   - 输入 tokens: {usage.get('input_tokens', 'N/A')}")
                                print(f"   - 输出 tokens: {usage.get('output_tokens', 'N/A')}")
                                print(f"   - 延迟: {usage.get('latency_ms', 'N/A')}ms")
                                if usage.get('cost_usd'):
                                    print(f"   - 成本: ${usage.get('cost_usd'):.6f}")
                            elif data["event"] == "error":
                                print(f"\n❌ 错误: {data.get('message', 'Unknown error')}")
                                return False
                    except json.JSONDecodeError:
                        continue
            
            print("\n✅ 消息处理完成")
            
        except Exception as e:
            print(f"\n❌ 错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    # 验证历史记录
    print("\n" + "="*60)
    print("验证聊天历史记录")
    print("="*60)
    
    # 重新从数据库加载节点
    db.refresh(node)
    internal_state = node.internal_state or {}
    history = internal_state.get("chat_history", [])
    
    print(f"📝 历史记录数量: {len(history)}")
    
    user_count = sum(1 for msg in history if msg.get("role") == "user")
    assistant_count = sum(1 for msg in history if msg.get("role") == "assistant")
    
    print(f"   - 用户消息: {user_count}")
    print(f"   - 助手消息: {assistant_count}")
    
    if user_count != assistant_count:
        print(f"⚠️  警告: 用户消息和助手消息数量不匹配！")
        return False
    
    # 显示历史记录
    print("\n📜 完整历史记录:")
    for i, msg in enumerate(history, 1):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:100]  # 只显示前100个字符
        print(f"   {i}. [{role}]: {content}...")
    
    return True


def check_environment():
    """检查环境配置"""
    print("检查环境配置...")
    
    # 检查必要的环境变量
    api_keys = {
        "ZHIPUAI_API_KEY": os.getenv("ZHIPUAI_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    }
    
    has_key = any(api_keys.values())
    
    if not has_key:
        print("⚠️  警告: 未找到 LLM API Key")
        print("   请设置以下环境变量之一:")
        print("   - ZHIPUAI_API_KEY (用于智谱AI)")
        print("   - OPENAI_API_KEY (用于 OpenAI)")
        print("   - ANTHROPIC_API_KEY (用于 Anthropic)")
        print("   - GOOGLE_API_KEY (用于 Google)")
        print("\n   或者在项目根目录创建 .env 文件:")
        print("   ZHIPUAI_API_KEY=your_api_key_here")
        return False
    else:
        print("✅ 找到 API Key")
        for key, value in api_keys.items():
            if value:
                print(f"   - {key}: {'*' * 20} (已设置)")
        return True


def main():
    """主函数"""
    print("="*60)
    print("Chatbot 功能验证脚本")
    print("="*60)
    
    # 检查环境
    if not check_environment():
        print("\n❌ 环境检查失败，请先配置 API Key")
        return
    
    # 获取数据库会话
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # 创建测试节点
        print("\n创建测试节点...")
        node = create_test_node(db)
        
        # 测试 chatbot
        success = test_chatbot(db, node)
        
        if success:
            print("\n" + "="*60)
            print("✅ 所有测试通过！")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("❌ 测试失败，请检查错误信息")
            print("="*60)
    
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
