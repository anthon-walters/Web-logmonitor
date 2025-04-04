import os
import sys
import asyncio
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn
import json
from datetime import datetime

from .websocket_service import WebSocketService # Relative import
from .data_service import DataService # Relative import
# Import custom exceptions from file_monitor
# Use the correct FileMonitor based on platform later
# from windows_file_monitor import FileMonitorError, ApiConnectionError, ApiTimeoutError, ApiResponseError, ShareConnectionError

# Add parent directory to path to import from the main application
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import from the main application
from config import (
    API_USERNAME,
    API_PASSWORD,
    API_PORT,
    STATS_SERVER_HOST,
    STATS_SERVER_PORT,
    WEB_INTERFACE_TITLE
)

# Import the file monitor and its exceptions
if sys.platform == 'win32':
    from windows_file_monitor import FileMonitor, FileMonitorError, ApiConnectionError, ApiTimeoutError, ApiResponseError, ShareConnectionError
else:
    from file_monitor import FileMonitor, FileMonitorError, ApiConnectionError, ApiTimeoutError, ApiResponseError, ShareConnectionError

# Configure logging
# Set root logger level - basicConfig might be called elsewhere or by libraries
logging.basicConfig(level=logging.INFO) # Keep basicConfig less verbose initially
# Get the specific loggers we want to be verbose
file_monitor_logger = logging.getLogger('FileMonitor')
file_monitor_logger.setLevel(logging.DEBUG)
data_service_logger = logging.getLogger('data_service')
data_service_logger.setLevel(logging.DEBUG) # Optional: Make data_service verbose too
web_interface_logger = logging.getLogger('web_interface')
web_interface_logger.setLevel(logging.DEBUG) # Make main app logger verbose

# Ensure handlers are present (basicConfig usually adds one, but let's be sure)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.DEBUG) # Fallback if no handlers exist

logger = web_interface_logger # Use the specific logger for this file

# Create FastAPI app
app = FastAPI(title="Web Log Monitor API")

# Add CORS middleware to allow cross-origin requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:3000"],  # Allow requests from the frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBasic()

# Initialize file monitor
file_monitor = FileMonitor()

# Initialize services
data_service = DataService(file_monitor) # Pass file_monitor instance
websocket_service = WebSocketService()


# Authentication dependency (can be used for WebSocket too if needed)
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = API_USERNAME
    correct_password = API_PASSWORD

    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_service.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle incoming messages if needed
            data = await websocket.receive_text()
            # Example: Handle client messages if necessary
            # logger.info(f"Received message from client: {data}")
    except WebSocketDisconnect:
        websocket_service.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        websocket_service.disconnect(websocket)


from fastapi import APIRouter
from .static_files import SPAStaticFiles # Relative import

# Create API router
api_router = APIRouter(prefix="/api")

# API routes
@api_router.get("/title")
def get_title(_: str = Depends(get_current_username)):
    """Get the web interface title."""
    return {"title": WEB_INTERFACE_TITLE}

@api_router.get("/debug")
def get_debug_info(): # No auth needed for debug usually
    """Get debug information about the API."""
    # Fetch current monitoring states from DataService (which reads from Redis)
    current_monitoring_states = data_service._get_all_monitoring_states_sync()
    return {
        "file_monitor_connected": file_monitor.is_connected(),
        "base_path": file_monitor.base_path,
        "api_port": API_PORT,
        "stats_server_host": STATS_SERVER_HOST,
        "stats_server_port": STATS_SERVER_PORT,
        "pi_addresses": file_monitor.pi_addresses,
        "monitoring_states": current_monitoring_states, # Use state fetched from Redis
        "timestamp": datetime.now().isoformat()
    }

@api_router.get("/status")
def get_status(_: str = Depends(get_current_username)):
    """Get the current status of the monitoring system."""
    try:
        is_connected = file_monitor.is_connected()
        logger.info(f"Status API called - is_connected: {is_connected}")
        return {
            "status": "running" if is_connected else "disconnected",
            "timestamp": datetime.now().isoformat()
        }
    except ShareConnectionError as e: # Catch potential error during is_connected check
         logger.error(f"Share connection error during status check: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Share connection error: {e}")
    except Exception as e: # Catch unexpected errors
         logger.error(f"Unexpected error during status check: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during status check")

@api_router.get("/file-counts")
def get_file_counts(_: str = Depends(get_current_username)):
    """Get file counts for each Pi directory."""
    try:
        if not file_monitor.is_connected():
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Network share not accessible")
    except ShareConnectionError as e:
         logger.error(f"Share connection error checking connection for file counts: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Share connection error: {e}")
    except Exception as e: # Catch unexpected errors during connection check
         logger.error(f"Unexpected error checking connection for file counts: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error checking connection")

    try:
        # Fetch current monitoring states from DataService (which reads from Redis)
        current_monitoring_states = data_service._get_all_monitoring_states_sync()
        jpg_counts = []
        total_files = 0
        for i in range(1, 11):
            pi_name = f"H{i}"
            # Skip if not monitored based on Redis state
            if not current_monitoring_states.get(pi_name, True):
                continue
            count = file_monitor.count_files(pi_name, '.JPG')
            jpg_counts.append({"directory": pi_name, "count": count})
            total_files += count
        return {"counts": jpg_counts, "total": total_files}
    except ShareConnectionError as e:
         logger.error(f"Share connection error during file count: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Share connection error during file count: {e}")
    except FileMonitorError as fm_error:
         logger.error(f"FileMonitor error during file count: {fm_error}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(fm_error))
    except Exception as e:
         logger.error(f"Unexpected error during file count: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during file count")


@api_router.get("/pi-status")
def get_pi_status(_: str = Depends(get_current_username)):
    """Get the status of all Pi devices."""
    try:
        if not file_monitor.is_connected():
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Network share not accessible")
    except ShareConnectionError as e:
         logger.error(f"Share connection error checking connection for pi status: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Share connection error: {e}")

    try:
        # Fetch current monitoring states from DataService (which reads from Redis)
        current_monitoring_states = data_service._get_all_monitoring_states_sync()
        # Pass the fetched monitoring states
        statuses, _ = file_monitor.check_pi_status_and_get_data(current_monitoring_states)
        logger.info(f"Pi status API called - returning statuses: {statuses}")
        return {"statuses": statuses}
    except Exception as e:
         logger.error(f"Unexpected error during pi status check: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during pi status check")

@api_router.get("/pi-statistics")
def get_pi_statistics(_: str = Depends(get_current_username)):
    """Get statistics for all Pi devices."""
    try:
        if not file_monitor.is_connected():
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Network share not accessible")
    except ShareConnectionError as e:
         logger.error(f"Share connection error checking connection for pi statistics: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Share connection error: {e}")
    except Exception as e: # Catch unexpected errors during connection check
         logger.error(f"Unexpected error checking connection for pi statistics: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error checking connection")

    sent_data = []
    tagged_data = []
    bibs_data = []
    try:
        # Fetch current monitoring states from DataService (which reads from Redis)
        current_monitoring_states = data_service._get_all_monitoring_states_sync()
        for i in range(1, 11):
            pi_name = f"H{i}"
            # Skip if not monitored based on Redis state
            if not current_monitoring_states.get(pi_name, True):
                sent_data.append({"device": pi_name, "count": 0})
                tagged_data.append({"device": pi_name, "count": 0})
                bibs_data.append({"device": pi_name, "count": 0})
                continue

            total_images = file_monitor.get_pi_total_images(pi_name)
            sent_data.append({"device": pi_name, "count": total_images})
            tagged_count = file_monitor.get_pi_statistics(pi_name)
            tagged_data.append({"device": pi_name, "count": tagged_count})
            bibs_count = file_monitor.get_pi_bib_statistics(pi_name)
            bibs_data.append({"device": pi_name, "count": bibs_count})

        totals = [ sum(item["count"] for item in sent_data), sum(item["count"] for item in tagged_data), sum(item["count"] for item in bibs_data) ]
        return { "sent": sent_data, "tagged": tagged_data, "bibs": bibs_data, "totals": totals }
    except (ApiConnectionError, ApiTimeoutError, ApiResponseError) as api_error:
         logger.error(f"API error getting pi statistics: {api_error}")
         raise api_error
    except FileMonitorError as fm_error:
         logger.error(f"FileMonitor error getting pi statistics: {fm_error}")
         raise fm_error
    except Exception as e:
         logger.error(f"Unexpected error getting pi statistics: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error getting pi statistics")


@api_router.get("/pi-monitor")
def get_pi_monitor(_: str = Depends(get_current_username)):
    """Get monitoring data for all Pi devices."""
    try:
        if not file_monitor.is_connected():
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Network share not accessible")
    except ShareConnectionError as e:
         logger.error(f"Share connection error checking connection for pi monitor data: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Share connection error: {e}")

    try:
        # Fetch current monitoring states from DataService (which reads from Redis)
        current_monitoring_states = data_service._get_all_monitoring_states_sync()
        # Pass the fetched monitoring states
        monitor_data = file_monitor.get_pi_monitor_data(current_monitoring_states)
        return {"data": monitor_data}
    except Exception as e:
         logger.error(f"Unexpected error getting pi monitor data: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error getting pi monitor data")

@api_router.get("/success-rates")
def get_success_rates(_: str = Depends(get_current_username)):
    """Get CV and bib detection success rates."""
    try:
        if not file_monitor.is_connected():
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Network share not accessible")
    except ShareConnectionError as e:
         logger.error(f"Share connection error checking connection for success rates: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Share connection error: {e}")
    except Exception as e: # Catch unexpected errors during connection check
         logger.error(f"Unexpected error checking connection for success rates: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error checking connection")

    try:
        # Fetch current monitoring states from DataService (which reads from Redis)
        current_monitoring_states = data_service._get_all_monitoring_states_sync()
        monitored_devices = [device for device, state in current_monitoring_states.items() if state]

        if not monitored_devices:
            return {"cv_rate": 0, "bib_rate": 0}

        cv_rate, bib_rate = file_monitor.get_pi_success_rates(monitored_devices)
        return {"cv_rate": cv_rate, "bib_rate": bib_rate}
    except FileMonitorError as fm_error:
         logger.error(f"FileMonitor error getting success rates: {fm_error}")
         raise fm_error
    except Exception as e:
         logger.error(f"Unexpected error getting success rates: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error getting success rates")


@api_router.post("/monitoring/{device}")
async def set_monitoring(device: str, state: bool, _: str = Depends(get_current_username)):
    """Set the monitoring state for a device."""
    try:
        await data_service.set_monitoring_state(device, state) # Now async
        return {"device": device, "monitoring": state}
    except ConnectionError as e: # Catch Redis connection error
         logger.error(f"Redis connection error setting monitoring state: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cannot update monitoring state: Redis unavailable")
    except Exception as e: # Catch other potential errors from Redis or logic
         logger.error(f"Error setting monitoring state for {device}: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update monitoring state")


# Custom Exception Handlers for API routes
@app.exception_handler(ApiConnectionError)
async def api_connection_error_handler(request: Request, exc: ApiConnectionError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": "API Connection Error", "message": str(exc)},
    )

@app.exception_handler(ApiTimeoutError)
async def api_timeout_error_handler(request: Request, exc: ApiTimeoutError):
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={"detail": "API Timeout Error", "message": str(exc)},
    )

@app.exception_handler(ApiResponseError)
async def api_response_error_handler(request: Request, exc: ApiResponseError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY, # Or 500 depending on context
        content={"detail": "API Response Error", "message": str(exc)},
    )

@app.exception_handler(ShareConnectionError)
async def share_connection_error_handler(request: Request, exc: ShareConnectionError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Share Connection Error", "message": str(exc)},
    )

@app.exception_handler(FileMonitorError) # Catch-all for other FileMonitor errors
async def file_monitor_error_handler(request: Request, exc: FileMonitorError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "File Monitor Error", "message": str(exc)},
    )

# Global handler for unexpected errors (should be last)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global unexpected exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error", "message": "An unexpected error occurred."},
    )


# Include API router first
app.include_router(api_router)

# Then mount static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "build")
logger.info(f"Looking for frontend files in: {frontend_dir}")
if os.path.exists(frontend_dir):
    logger.info("Frontend directory found, mounting static files")
    try:
        # Mount static files directory explicitly
        static_dir = os.path.join(frontend_dir, "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
            logger.info("Static files mounted at /static")

        # Mount other static files
        app.mount("/favicon.ico", StaticFiles(directory=frontend_dir), name="favicon")
        app.mount("/manifest.json", StaticFiles(directory=frontend_dir), name="manifest")
        app.mount("/logo192.png", StaticFiles(directory=frontend_dir), name="logo192")
        app.mount("/logo512.png", StaticFiles(directory=frontend_dir), name="logo512")
        app.mount("/robots.txt", StaticFiles(directory=frontend_dir), name="robots")

        # Mount root last
        app.mount("/", SPAStaticFiles(directory=frontend_dir, html=True), name="root")
        logger.info("All static files mounted successfully")
    except Exception as e:
        logger.error(f"Error mounting static files: {str(e)}")
else:
    logger.error(f"Frontend directory not found at: {frontend_dir}")

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Web Log Monitor API")
    try:
        is_connected = await asyncio.get_event_loop().run_in_executor(None, file_monitor.is_connected)
        logger.info(f"File monitor connection status: {is_connected}")
        logger.info(f"Base path: {file_monitor.base_path}")
    except Exception as e:
        logger.error(f"Error checking file monitor connection on startup: {e}", exc_info=True)

    # Start the WebSocket background task to broadcast updates
    # Use the get_all_data method from the data_service instance
    # Set an appropriate interval (e.g., 1 second)
    update_interval = 1.0
    await websocket_service.start_background_task(data_service.get_all_data, interval=update_interval)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Web Log Monitor API")
    # Stop any running background tasks
    await websocket_service.stop_background_task()
    # Close Redis connection pool if it exists
    if data_service.redis_pool:
        logger.info("Closing Redis connection pool.")
        # The pool doesn't have an explicit close, rely on garbage collection
        # or ensure connections are closed if using individual connections.
        # For simplicity here, we assume pool management handles connection closing.
        pass


# Run the server
if __name__ == "__main__":
    # Note: log_level here might be overridden by basicConfig if run directly
    uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=True, log_level="info")
