import os
import sys
import asyncio
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
import json
from datetime import datetime

from websocket_service import WebSocketService
from data_service import DataService

# Add parent directory to path to import from the main application
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import from the main application
from config import (
    API_USERNAME,
    API_PASSWORD,
    API_PORT,
    STATS_SERVER_HOST,
    STATS_SERVER_PORT
)

# Import the file monitor
if sys.platform == 'win32':
    from windows_file_monitor import FileMonitor
else:
    from file_monitor import FileMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_interface")

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
websocket_service = WebSocketService()
data_service = DataService(file_monitor)

# Authentication dependency
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

# Routes
@app.get("/")
def read_root():
    return {"message": "Web Log Monitor API"}

@app.get("/api/status")
def get_status(_: str = Depends(get_current_username)):
    """Get the current status of the monitoring system."""
    return {
        "status": "running" if file_monitor.is_connected() else "disconnected",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/file-counts")
def get_file_counts(_: str = Depends(get_current_username)):
    """Get file counts for each Pi directory."""
    if not file_monitor.is_connected():
        return {"counts": [], "total": 0}
    
    jpg_counts = []
    total_files = 0
    
    # Count JPG files in each Pi directory
    for i in range(1, 11):
        pi_name = f"H{i}"
        count = file_monitor.count_files(pi_name, '.JPG')
        jpg_counts.append({"directory": pi_name, "count": count})
        total_files += count
    
    return {"counts": jpg_counts, "total": total_files}

@app.get("/api/pi-status")
def get_pi_status(_: str = Depends(get_current_username)):
    """Get the status of all Pi devices."""
    if not file_monitor.is_connected():
        return {"statuses": {f"H{i}": False for i in range(1, 11)}}
    
    statuses = file_monitor.check_pi_status()
    return {"statuses": statuses}

@app.get("/api/pi-statistics")
def get_pi_statistics(_: str = Depends(get_current_username)):
    """Get statistics for all Pi devices."""
    if not file_monitor.is_connected():
        return {
            "sent": [],
            "tagged": [],
            "bibs": [],
            "totals": [0, 0, 0]
        }
    
    sent_data = []
    tagged_data = []
    bibs_data = []
    
    for i in range(1, 11):
        pi_name = f"H{i}"
        
        # Get total images
        total_images = file_monitor.get_pi_total_images(pi_name)
        sent_data.append({"device": pi_name, "count": total_images})
        
        # Get tagged files
        tagged_count = file_monitor.get_pi_statistics(pi_name)
        tagged_data.append({"device": pi_name, "count": tagged_count})
        
        # Get bib statistics
        bibs_count = file_monitor.get_pi_bib_statistics(pi_name)
        bibs_data.append({"device": pi_name, "count": bibs_count})
    
    totals = [
        sum(item["count"] for item in sent_data),
        sum(item["count"] for item in tagged_data),
        sum(item["count"] for item in bibs_data)
    ]
    
    return {
        "sent": sent_data,
        "tagged": tagged_data,
        "bibs": bibs_data,
        "totals": totals
    }

@app.get("/api/pi-monitor")
def get_pi_monitor(_: str = Depends(get_current_username)):
    """Get monitoring data for all Pi devices."""
    if not file_monitor.is_connected():
        return {"data": []}
    
    # This is a bit of a hack since we don't have direct access to the monitoring data
    # In a real implementation, we would refactor the file_monitor to provide this data directly
    statuses = file_monitor.check_pi_status()
    
    # The check_pi_status method updates the UI with monitoring data
    # We need to extract this data from somewhere else or modify the file_monitor
    # For now, we'll return a simplified version
    monitor_data = []
    for pi_name, is_online in statuses.items():
        if is_online:
            # Get data from the statistics API
            total_images = file_monitor.get_pi_total_images(pi_name)
            # For uploaded, we'll use a placeholder
            # In a real implementation, we would get this from the file_monitor
            monitor_data.append({
                "device": pi_name,
                "processed": total_images,
                "uploaded": total_images  # Placeholder
            })
        else:
            monitor_data.append({
                "device": pi_name,
                "processed": 0,
                "uploaded": 0
            })
    
    return {"data": monitor_data}

@app.get("/api/success-rates")
def get_success_rates(_: str = Depends(get_current_username)):
    """Get CV and bib detection success rates."""
    if not file_monitor.is_connected():
        return {"cv_rate": 0, "bib_rate": 0}
    
    cv_rate, bib_rate = file_monitor.get_pi_success_rates()
    return {"cv_rate": cv_rate, "bib_rate": bib_rate}

# Add route for setting monitoring state
@app.post("/api/monitoring/{device}")
async def set_monitoring(device: str, state: bool, _: str = Depends(get_current_username)):
    """Set the monitoring state for a device."""
    data_service.set_monitoring_state(device, state)
    return {"device": device, "monitoring": state}

# Background task to periodically check and clean up stale WebSocket connections
@app.on_event("startup")
async def start_connection_cleanup():
    async def cleanup_task():
        while True:
            try:
                # Check connections every 30 seconds
                await asyncio.sleep(30)
                removed = await websocket_service.check_connections()
                if removed > 0:
                    logger.info(f"Connection cleanup removed {removed} stale connections")
            except Exception as e:
                logger.error(f"Error in connection cleanup task: {str(e)}")
                await asyncio.sleep(30)  # Still wait before retrying
    
    # Start the cleanup task
    asyncio.create_task(cleanup_task())
    logger.info("Started WebSocket connection cleanup task")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("WebSocket connection request received")
    
    try:
        # Accept the connection without authentication for now
        # In a production environment, you would want to add authentication
        await websocket_service.connect(websocket)
        logger.info("WebSocket connection accepted")
        
        # Start background task to send updates every 5 seconds if not already running
        # This ensures we only have one background task regardless of how many clients connect
        await websocket_service.start_background_task(data_service.get_all_data, 5.0)
        
        try:
            # Send initial data immediately
            initial_data = await data_service.get_all_data()
            logger.info("Sending initial data to new WebSocket client")
            await websocket.send_json(initial_data)
            
            # Main receive loop
            while True:
                # Wait for any message from the client with a timeout
                try:
                    # Use a timeout to periodically check if the connection is still alive
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    
                    # Handle ping messages specially
                    if data == 'ping':
                        await websocket.send_text('pong')
                        continue
                    
                    # Log the received message
                    logger.info(f"Received WebSocket message: {data}")
                    
                    # Send current data immediately when requested
                    all_data = await data_service.get_all_data()
                    logger.info(f"Sending data to WebSocket client")
                    await websocket.send_json(all_data)
                except asyncio.TimeoutError:
                    # No message received within timeout, check if connection is still alive
                    try:
                        # Send a ping to check if the connection is still alive
                        await websocket.send_text('ping')
                    except Exception:
                        # Connection is dead, break out of the loop
                        logger.info("WebSocket connection timed out and is no longer responsive")
                        break
                
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"Error in WebSocket endpoint receive loop: {str(e)}")
        finally:
            # Always ensure we disconnect the client
            if websocket in websocket_service.active_connections:
                websocket_service.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error establishing WebSocket connection: {str(e)}")
    
    # Only stop the background task if there are no more connections
    if not websocket_service.active_connections:
        await websocket_service.stop_background_task()

# Error handler for exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)},
    )

# Mount the static files (frontend) if the directory exists
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "build")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Web Log Monitor API")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Web Log Monitor API")
    # Stop any running background tasks
    await websocket_service.stop_background_task()

# Run the server
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7171, reload=True, log_level="info")
