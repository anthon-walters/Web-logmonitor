import os
import logging
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, Response
from starlette.types import Scope, Receive, Send

logger = logging.getLogger(__name__)

class SPAStaticFiles(StaticFiles):
    """Custom static files handler that serves index.html for all routes."""
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle incoming request."""
        assert scope["type"] == "http"
        
        # Get the request path
        request_path = scope["path"]
        logger.debug(f"Handling request for path: {request_path}")
        
        try:
            # Check if this is a static file request
            if request_path.startswith("/static/"):
                logger.debug(f"Serving static file: {request_path}")
                await super().__call__(scope, receive, send)
                return
                
            # Check for other known static files
            if request_path in ["/favicon.ico", "/manifest.json", "/logo192.png", "/logo512.png", "/robots.txt"]:
                file_path = os.path.join(self.directory, request_path.lstrip("/"))
                if os.path.exists(file_path):
                    logger.debug(f"Serving known static file: {file_path}")
                    response = FileResponse(file_path)
                    await response(scope, receive, send)
                    return
            
            # For all other routes, serve index.html
            index_path = os.path.join(self.directory, "index.html")
            if os.path.exists(index_path):
                logger.debug(f"Serving index.html for path: {request_path}")
                response = FileResponse(index_path)
                await response(scope, receive, send)
                return
                
            # If we get here, the file wasn't found
            logger.warning(f"File not found: {request_path}")
            response = Response(status_code=404)
            await response(scope, receive, send)
            
        except Exception as e:
            logger.error(f"Error serving static files: {str(e)}")
            response = Response(status_code=500)
            await response(scope, receive, send)
