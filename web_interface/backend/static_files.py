import os
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.types import Scope, Receive, Send

class SPAStaticFiles(StaticFiles):
    """Custom static files handler that serves index.html for all routes."""
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle incoming request."""
        assert scope["type"] == "http"
        
        # Get the request path
        request_path = scope["path"]
        
        # If path has a file extension, try to serve it as a static file
        if os.path.splitext(request_path)[1]:
            response = await super().__call__(scope, receive, send)
            return response
            
        # For all other routes, serve index.html
        index_path = os.path.join(self.directory, "index.html")
        if os.path.exists(index_path):
            response = FileResponse(index_path)
            await response(scope, receive, send)
            return
            
        # Fallback to regular static file handling
        response = await super().__call__(scope, receive, send)
        return response
