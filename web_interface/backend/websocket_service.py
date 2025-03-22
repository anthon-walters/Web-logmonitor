import asyncio
import logging
from typing import Dict, List, Any, Callable, Awaitable
from fastapi import WebSocket

logger = logging.getLogger("websocket_service")

class WebSocketService:
    """Service for managing WebSocket connections and broadcasting updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.background_task = None
        self.stop_event = asyncio.Event()
        self.is_background_task_running = False
        self.connection_count = 0  # Track total connections for debugging
    
    async def connect(self, websocket: WebSocket):
        """Connect a new WebSocket client."""
        # Accept the connection
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_count += 1
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}, Connection count: {self.connection_count}")
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        disconnected_clients = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {str(e)}")
                disconnected_clients.append(connection)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in self.active_connections:
                self.active_connections.remove(client)
                logger.info(f"Removed disconnected client. Remaining connections: {len(self.active_connections)}")
    
    async def start_background_task(self, update_function: Callable[[], Awaitable[Dict[str, Any]]], interval: float = 1.0):
        """Start a background task that periodically broadcasts updates."""
        # Only start if not already running
        if self.is_background_task_running:
            logger.info("Background task already running, not starting a new one")
            return
            
        self.stop_event.clear()
        self.is_background_task_running = True
        
        async def task():
            logger.info(f"Starting background WebSocket update task with interval {interval}s")
            try:
                while not self.stop_event.is_set():
                    try:
                        # Get update data
                        data = await update_function()
                        
                        # Broadcast to all clients
                        if self.active_connections:
                            await self.broadcast(data)
                        
                        # Wait for the next update
                        await asyncio.sleep(interval)
                    except Exception as e:
                        logger.error(f"Error in background task: {str(e)}")
                        await asyncio.sleep(interval)  # Still wait before retrying
            finally:
                logger.info("Background WebSocket update task stopped")
                self.is_background_task_running = False
        
        self.background_task = asyncio.create_task(task())
    
    async def stop_background_task(self):
        """Stop the background update task."""
        if self.background_task and self.is_background_task_running:
            logger.info("Stopping background WebSocket update task...")
            self.stop_event.set()
            try:
                # Wait for the task to complete with a timeout
                done, pending = await asyncio.wait([self.background_task], timeout=5.0)
                
                if self.background_task in pending:
                    # Task didn't complete within timeout, cancel it
                    self.background_task.cancel()
                    logger.info("Background WebSocket update task was cancelled due to timeout")
                
                self.background_task = None
            except asyncio.CancelledError:
                logger.info("Background WebSocket update task was cancelled")
            except Exception as e:
                logger.error(f"Error stopping background WebSocket update task: {str(e)}")
            finally:
                self.is_background_task_running = False
                
    async def check_connections(self):
        """Check if connections are still alive and remove stale ones."""
        stale_connections = []
        
        for connection in self.active_connections:
            try:
                # Try to ping the connection
                await connection.send_text('ping')
            except Exception as e:
                logger.warning(f"Found stale connection: {str(e)}")
                stale_connections.append(connection)
        
        # Remove stale connections
        for connection in stale_connections:
            if connection in self.active_connections:
                self.active_connections.remove(connection)
                
        if stale_connections:
            logger.info(f"Removed {len(stale_connections)} stale connections. Remaining: {len(self.active_connections)}")
            
        return len(stale_connections)
