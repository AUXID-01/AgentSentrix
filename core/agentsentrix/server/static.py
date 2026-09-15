import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger("agentsentrix.server.static")

def mount_static_files(app: FastAPI, web_dir: str = "dashboard/out") -> None:
    """Mount static dashboard assets to serve Next.js export on root UI routes."""
    target_dir = web_dir if os.path.exists(web_dir) else "core/agentsentrix/web"
    abs_web_dir = os.path.abspath(target_dir)
    if not os.path.exists(abs_web_dir):
        os.makedirs(abs_web_dir, exist_ok=True)
        # Create dummy index.html if empty
        index_file = os.path.join(abs_web_dir, "index.html")
        if not os.path.exists(index_file):
            with open(index_file, "w", encoding="utf-8") as f:
                f.write("<html><body><h1>AgentSentrix Real-Time Threat Dashboard</h1></body></html>")

    index_path = os.path.join(abs_web_dir, "index.html")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard_root():
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "AgentSentrix Dashboard Placeholder"}

    app.mount("/_next", StaticFiles(directory=os.path.join(abs_web_dir, "_next")), name="static_next") if os.path.exists(os.path.join(abs_web_dir, "_next")) else None
    app.mount("/out", StaticFiles(directory=abs_web_dir, html=True), name="static_out")
    logger.info(f"[Static] Mounted web dashboard static files from {abs_web_dir}")
