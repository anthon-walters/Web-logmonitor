import os
import sys
import subprocess

# Add parent directory to path to import from the main application
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Run the FastAPI backend server."""
    try:
        # Get the absolute path to the backend directory
        backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
        backend_main = os.path.join(backend_dir, 'main.py')
        
        # Check if the main.py file exists
        if not os.path.exists(backend_main):
            print(f"ERROR: main.py not found at {backend_main}")
            return
        
        # Check if requirements are installed
        try:
            import fastapi
        except ImportError:
            print("Installing backend dependencies...")
            requirements_path = os.path.join(backend_dir, 'requirements.txt')
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', requirements_path], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error installing dependencies: {str(e)}")
                return
        
        print("Starting backend server...")
        print("The server will be available at http://localhost:7171")
        print("Press Ctrl+C to stop the server")

        # Calculate project root directory (one level up from web_interface)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Define the port (using the hardcoded value from the print statement)
        port = 7171
        
        # Construct the uvicorn command
        # Use the module path 'web_interface.backend.main' and the app instance 'app'
        command = [
            sys.executable, '-m', 'uvicorn',
            'web_interface.backend.main:app',
            '--host', '0.0.0.0',
            '--port', str(port)
            # '--reload' # Typically not used in run_backend.py, more for run_dev.py
        ]
        
        print(f"Running command: {' '.join(command)} from {project_root}")
        
        # Run the uvicorn command from the project root directory
        subprocess.run(command, cwd=project_root)
        
    except Exception as e:
        print(f"Error running backend: {str(e)}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging

if __name__ == "__main__":
    main()
