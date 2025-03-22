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
        
        # Run the backend server without changing directory
        subprocess.run([sys.executable, backend_main])
    except Exception as e:
        print(f"Error running backend: {str(e)}")

if __name__ == "__main__":
    main()
