from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path

from app.config import get_settings
from app.errors import ApiError
from app.exception_handlers import (
    api_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.routers.categories import router as categories_router
from app.routers.standards import router as standards_router
from app.routers.search import router as search_router
from app.routers.relations import router as relations_router
from app.routers.embeddings import router as embeddings_router
from app.routers.code_lists import router as code_lists_router


# 应用实例
settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

# 注册统一异常处理器（返回标准化 errors/warnings 结构）
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# 路由注册
app.include_router(categories_router)
app.include_router(standards_router)
app.include_router(search_router)
app.include_router(relations_router)
app.include_router(embeddings_router)
app.include_router(code_lists_router)

UI_READONLY_DIR = Path(__file__).resolve().parents[1] / "ui-readonly"
if UI_READONLY_DIR.exists():
    app.mount("/ui-readonly", StaticFiles(directory=str(UI_READONLY_DIR), html=True), name="ui_readonly")

    @app.get("/", include_in_schema=False)
    async def ui_home():
        return RedirectResponse(url="/ui-readonly/")


# 健康检查
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
