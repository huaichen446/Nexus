from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 使用 SQLite 文件
#相对路径在不同运行目录下会有差异；
# 部署时常改成绝对路径或用环境变量控制连接字符串。SQLALCHEMY_DATABASE_URL = "sqlite:///./nexus.db"
SQLALCHEMY_DATABASE_URL = "sqlite:///./nexus.db"

# check_same_thread=False 是 SQLite 在 FastAPI (多线程环境) 中必须的配置
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency Injection for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    except:
        db.rollback()
        raise
    finally:
        db.close()