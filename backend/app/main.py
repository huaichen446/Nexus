import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. 导入数据库引擎和基类（用于自动建表）
from backend.app.database import engine, Base
# 2. 导入你刚刚写好的路由
from backend.app.routers import topology

# --- 数据库初始化 ---
# 在应用启动前，自动在数据库中创建所有定义的模型表
# 如果表已存在，它不会覆盖或报错
Base.metadata.create_all(bind=engine)

# --- 初始化 FastAPI 应用 ---
app = FastAPI(
    title="Nexus Topology API",
    description="Backend service for managing prompt engineering nodes and lineage.",
    version="0.1.0"
)

# --- 配置 CORS (跨域资源共享) ---
# 这一步非常重要，否则以后前端(localhost:3000)无法调用后端(localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有来源，生产环境建议指定具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, etc.)
    allow_headers=["*"],
)

# --- 注册路由模块 ---
# 我们把 topology 相关的接口挂载到 app 上
app.include_router(topology.router)

# --- 基础健康检查接口 ---
@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Nexus-Topology-Engine",
        "version": "0.1.0"
    }

# --- 启动入口 ---
if __name__ == "__main__":
    # 使用 uvicorn 运行应用
    # reload=True 表示当你修改代码保存后，服务器会自动重启，非常适合开发
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)

#uvicorn backend.app.main:app --reload
