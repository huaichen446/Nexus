from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db

# AtomicNode: 用于响应 (Response)，包含完整字段 (depth, created_at, children_ids)
# AtomicNodeCreate: 用于请求 (Request)，只包含前端填写的字段
from backend.app.schemas import AtomicNode, AtomicNodeCreate, AtomicNodeUpdate
from backend.app.services.topology_service import topology_service

router = APIRouter(
    prefix="/nodes",
    tags=["Topology"],
    responses={404: {"description": "Not found"}},
)


# ==========================================
# 1. 创建节点 (Create)
# ==========================================
@router.post("/", response_model=AtomicNode, status_code=status.HTTP_201_CREATED)
def create_node(node_in: AtomicNodeCreate, db: Session = Depends(get_db)):
    """
    创建一个新节点。

    - **Input**: AtomicNodeCreate (前端只需要传内容、父节点ID等，无需传 depth)
    - **Output**: AtomicNode (后端返回完整的对象，包含计算好的 depth 和时间戳)
    """
    try:
        # 调用 Service 层，Service 会负责将 AtomicNodeCreate 补全为数据库模型
        new_node = topology_service.create_node(db, node_in)
        return new_node

    except ValueError as e:
        # 捕获业务逻辑错误（例如：指定的 parent_id 不存在）
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # 捕获数据库或其他未知错误
        # 在生产环境建议使用 logger.error(f"Error creating node: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ==========================================
# 2. 读取单个节点 (Read One)
# ==========================================
@router.get("/{node_id}", response_model=AtomicNode)
def get_node(node_id: str, db: Session = Depends(get_db)):
    """
    获取单个节点的详细信息。
    """
    node = topology_service.get_node(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


# ==========================================
# 3. 获取溯源链 (Read Lineage) - 核心功能
# ==========================================
@router.get("/{node_id}/lineage", response_model=List[AtomicNode])
def get_node_lineage(node_id: str, db: Session = Depends(get_db)):
    """
    获取从 Root 到当前节点的所有祖先列表。
    返回顺序: [Root, Level_1, ..., Parent, Self]
    用于构建 LLM 上下文或面包屑导航。
    """
    try:
        lineage = topology_service.get_ancestor_chain(db, node_id)
        return lineage
    except ValueError as e:
        # 如果当前节点都不存在，无法溯源
        raise HTTPException(status_code=404, detail=str(e))


# ==========================================
# 4. 获取子节点 (Read Children)
# ==========================================
@router.get("/{node_id}/children", response_model=List[AtomicNode])
def get_node_children(node_id: str, db: Session = Depends(get_db)):
    """
    获取某节点的直接子节点列表。用于树状图展开。
    """
    # 即使没有子节点，也返回空列表 []，而不是 404
    children = topology_service.get_children(db, node_id)
    return children


# ==========================================
# 5. 获取项目的根节点 (Get Root Nodes by Project)
# ==========================================
@router.get("/project/{project_id}/roots", response_model=List[AtomicNode])
def get_project_root_nodes(project_id: str, db: Session = Depends(get_db)):
    """
    获取项目的所有根节点（parent_id 为 None 的节点）。
    用于前端显示项目的节点树入口。
    """
    root_nodes = topology_service.get_root_nodes(db, project_id)
    return root_nodes


# ==========================================
# 6. 获取项目的所有节点 (Get All Nodes by Project)
# ==========================================
@router.get("/project/{project_id}/all", response_model=List[AtomicNode])
def get_project_all_nodes(project_id: str, db: Session = Depends(get_db)):
    """
    获取项目的所有节点。
    用于前端一次性获取所有节点，然后在客户端构建树形结构。
    """
    all_nodes = topology_service.get_all_nodes_by_project(db, project_id)
    return all_nodes


# ==========================================
# 7. 更新节点 (Partial Update)
# ==========================================
@router.patch("/{node_id}", response_model=AtomicNode)
def update_node(node_id: str, node_in: AtomicNodeUpdate, db: Session = Depends(get_db)):
    """
    部分更新节点内容（不修改拓扑结构）。
    """
    try:
        updated = topology_service.update_node(db, node_id, node_in)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ==========================================
# 8. 删除节点 (Delete)
# ==========================================
@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: str, db: Session = Depends(get_db)):
    """
    删除节点及其子树（物理删除）。
    """
    try:
        topology_service.delete_node(db, node_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ==========================================
# 9. 宏观剪枝：归档分支 (Archive Branch)
# ==========================================
@router.post("/{node_id}/archive-branch")
def archive_branch(node_id: str, db: Session = Depends(get_db)):
    """
    宏观剪枝 (Macro-Pruning):
    - 将当前节点及其所有子孙节点的 node_status 设为 'archived'。
    - 默认树视图会过滤掉已归档节点，从而在 UI 上“剪掉”这一整条分支。
    """
    try:
        affected = topology_service.archive_branch(db, node_id)
        return {"node_id": node_id, "archived_count": affected}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")