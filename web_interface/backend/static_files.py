import os
import logging
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, Response, JSONResponse
from starlette.types import Scope, Receive, Send

logger = logging.getLogger(__name__)

class SPAStaticFiles(StaticFiles):
    """Custom static files handler that serves index.html for all non-API routes."""
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle incoming request."""
        assert scope["type"] == "http"
        
        # Get the request path
        request_path = scope["path"]
        logger.debug(f"Handling request for path: {request_path}")
        
        try:
            # Skip API routes
            if request_path.startswith("/api/"):
                logger.debug(f"Skipping API route: {request_path}")
                response = Response(status_code=404)
                await response(scope, receive, send)
                return
            
            # Try to serve as a static file first
            try:
                await super().__call__(scope, receive, send)
                return
            except Exception as e:
                logger.debug(f"Static file not found, falling back to index.html: {str(e)}")
            
            # For all other routes, serve index.html
            index_path = os.path.join(self.directory, "index.html")
            if os.path.exists(index_path):
                logger.debug(f"Serving index.html for path: {request_path}")
                response = FileResponse(index_path)
                await response(scope, receive, send)
                return
            
            # If we get here, something went wrong
            logger.error(f"Could not serve path: {request_path}")
            response = Response(status_code=404)
            await response(scope, receive, send)
            
        except Exception as e:
            logger.error(f"Error serving static files: {str(e)}")
            response = Response(status_code=500)
            await response(scope, receive, send)
