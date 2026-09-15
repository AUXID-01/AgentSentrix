import os
import logging
from typing import Optional
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger("agentsentrix.server.static")

def mount_static_dashboard(app: FastAPI, web_dir: Optional[str] = None) -> None:
    """Mount Next.js static export build as single-process SPA dashboard."""
    if web_dir is None:
        web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")

    abs_web_dir = os.path.abspath(web_dir)
    if not os.path.exists(abs_web_dir):
        os.makedirs(abs_web_dir, exist_ok=True)

    index_html = os.path.join(abs_web_dir, "index.html")
    next_dir = os.path.join(abs_web_dir, "_next")

    # Mount Next.js _next static asset directory
    if os.path.exists(next_dir):
        app.mount("/_next", StaticFiles(directory=next_dir), name="web_next")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Bypass SPA fallback for REST API endpoints, WebSockets, OpenAPI docs & health check
        if full_path.startswith(("api", "ws", "events", "graph", "health", "decide", "docs", "openapi.json")):
            return None
        
        file_path = os.path.join(abs_web_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # SPA Fallback to index.html
        if os.path.exists(index_html):
            return FileResponse(index_html)

        return {"error": "Dashboard static build not found. Run 'npm run build' inside dashboard/ first."}

    logger.info(f"[Static Dashboard] Mounted web dashboard from {abs_web_dir}")

# Alias for backward compatibility
mount_static_files = mount_static_dashboard
