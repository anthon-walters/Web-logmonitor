import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("production")

def build_frontend():
    """Build the frontend for production."""
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
    build_dir = os.path.join(frontend_dir, 'build')
    
    # Check if build directory exists and is not empty
    if os.path.exists(build_dir) and os.listdir(build_dir):
        logger.info("Frontend build directory exists and is not empty")
        return True
        
    logger.info("Building frontend...")
    try:
        # Change to frontend directory
        os.chdir(frontend_dir)
        
        # Install dependencies
        subprocess.run(['npm', 'install'], check=True)
        
        # Build the frontend
        subprocess.run(['npm', 'run', 'build'], check=True)
        
        logger.info("Frontend built successfully")
        return True
    except Exception as e:
        logger.error(f"Error building frontend: {str(e)}")
        return False
    finally:
        # Change back to original directory
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

def run_server():
    """Run the production server."""
    try:
        # Build frontend first
        if not build_frontend():
            logger.error("Frontend build failed")
            return
            
        # Import FastAPI app
        from backend.main import app
        import uvicorn
        
        # Get port from config
        from config import API_PORT
        
        # Run the server
        logger.info(f"Starting server on port {API_PORT}")
        uvicorn.run(app, host="0.0.0.0", port=API_PORT)
        
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")

if __name__ == "__main__":
    run_server()
