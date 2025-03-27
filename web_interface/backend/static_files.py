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
        logger.debug(f"SPA Handling request for path: {request_path}")

        try:
            # Try to serve the static file using the parent class
            response = await self.get_response(request_path, scope)
            if response.status_code != 404:
                # If found and not a 404, serve it
                logger.debug(f"Serving static file: {request_path}")
                await response(scope, receive, send)
                return
            # If parent class returned 404, fall through to serve index.html
            logger.debug(f"Static file not found for {request_path}, falling back to index.html")

        except Exception as e:
            # Handle potential errors during static file lookup
            logger.warning(f"Error looking up static file {request_path}, falling back to index.html: {e}")
            # Fall through to serve index.html

        # Serve index.html if static file not found or error occurred
        index_path = os.path.join(self.directory, "index.html")
        if os.path.exists(index_path):
            logger.debug(f"Serving index.html for path: {request_path}")
            response = FileResponse(index_path, stat_result=os.stat(index_path))
            await response(scope, receive, send)
        else:
            # If index.html doesn't exist either, return 404
            logger.error(f"index.html not found in directory: {self.directory}")
            response = Response("Not Found", status_code=404)
            await response(scope, receive, send)
