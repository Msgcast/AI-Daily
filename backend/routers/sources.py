"""
数据源配置路由
GET    /api/sources               - 获取所有数据源
POST   /api/sources               - 新增
PUT    /api/sources/{id}          - 修改
DELETE /api/sources/{id}          - 删除
POST   /api/sources/{id}/validate - 验证 RSS URL 可达性
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import RssSource

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    category: str = "综合资讯"
    url: str
    description: str = ""
    enabled: bool = True


class SourceUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    url: str | None = None
    description: str | None = None
    enabled: bool | None = None


@router.get("")
def list_sources(session: Session = Depends(get_session)):
    sources = session.exec(select(RssSource).order_by(RssSource.id)).all()
    return [s.model_dump() for s in sources]


@router.post("")
def create_source(data: SourceCreate, session: Session = Depends(get_session)):
    source = RssSource(**data.model_dump())
    session.add(source)
    session.commit()
    session.refresh(source)
    return source.model_dump()


@router.put("/{source_id}")
def update_source(source_id: int, data: SourceUpdate, session: Session = Depends(get_session)):
    source = session.get(RssSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(source, k, v)
    session.add(source)
    session.commit()
    session.refresh(source)
    return source.model_dump()


@router.delete("/{source_id}")
def delete_source(source_id: int, session: Session = Depends(get_session)):
    source = session.get(RssSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    session.delete(source)
    session.commit()
    return {"status": "deleted", "id": source_id}


@router.post("/{source_id}/validate")
async def validate_source(source_id: int, session: Session = Depends(get_session)):
    source = session.get(RssSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(source.url)
            content = resp.content[:500].lower()
            is_feed = b"<rss" in content or b"<feed" in content or b"<rdf" in content
            return {
                "valid": resp.status_code == 200 and is_feed,
                "status_code": resp.status_code,
                "is_feed": is_feed,
                "message": "验证通过" if is_feed else "URL 可达但内容不是有效 RSS/Atom",
            }
    except Exception as e:
        return {"valid": False, "message": str(e)}
