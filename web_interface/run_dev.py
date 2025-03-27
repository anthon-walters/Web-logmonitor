import os
import sys
import subprocess
import time
import signal
import threading
import webbrowser
import shutil

# Add parent directory to path to import from the main application
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_npm():
    """Check if npm is installed and in the PATH."""
    npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'
    try:
        # Use shutil.which to check if npm is in the PATH
        npm_path = shutil.which(npm_cmd)
        if npm_path:
            return npm_path
        else:
            print("ERROR: npm not found in PATH. Please install Node.js and npm.")
            print("You can download Node.js from https://nodejs.org/")
            return None
    except Exception as e:
        print(f"Error checking for npm: {str(e)}")
        return None

def run_backend():
    """Run the FastAPI backend server."""
    try:
        # Get the absolute path to the backend directory
        backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
        backend_main = os.path.join(backend_dir, 'main.py')
        
        # Check if the main.py file exists
        if not os.path.exists(backend_main):
            print(f"ERROR: main.py not found at {backend_main}")
            return
        
        print("Starting backend server...")
        print("Waiting for server to start on localhost:7171...")

        # Calculate project root directory (one level up from web_interface)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Define the port
        port = 7171
        
        # Construct the uvicorn command with --reload for development
        command = [
            sys.executable, '-m', 'uvicorn',
            'web_interface.backend.main:app',
            '--host', '0.0.0.0',
            '--port', str(port),
            '--reload' # Enable auto-reload for development
        ]
        
        print(f"Running backend command: {' '.join(command)} from {project_root}")
        
        # Run the uvicorn command from the project root directory using Popen
        # Store the process handle to potentially terminate it later if needed
        backend_process = subprocess.Popen(command, cwd=project_root)
        
        # Wait for the server to start
        if wait_for_server('localhost', port, timeout=30):
            print("\nBackend server started at http://localhost:7171")
        else:
            print("\nWARNING: Backend server may not have started properly")
    except Exception as e:
        print(f"Error running backend: {str(e)}")

def run_frontend():
    """Run the React frontend development server."""
    try:
        # Get the absolute path to the frontend directory
        frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
        public_dir = os.path.join(frontend_dir, 'public')
        
        # Check if npm is installed
        npm_path = check_npm()
        if not npm_path:
            return
        
        npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'
        
        # Check if package.json exists
        package_json_path = os.path.join(frontend_dir, 'package.json')
        if not os.path.exists(package_json_path):
            print(f"ERROR: package.json not found at {package_json_path}")
            return
        
        # Change to the frontend directory
        original_dir = os.getcwd()
        os.chdir(frontend_dir)
        
        try:
            # Create placeholder image files if they don't exist
            favicon_path = os.path.join(public_dir, 'favicon.ico')
            logo192_path = os.path.join(public_dir, 'logo192.png')
            logo512_path = os.path.join(public_dir, 'logo512.png')
            
            if not os.path.exists(favicon_path) or not os.path.exists(logo192_path) or not os.path.exists(logo512_path):
                print("Creating placeholder image files...")
                placeholder_script = os.path.join(public_dir, 'create_placeholder_images.ps1')
                if os.path.exists(placeholder_script):
                    try:
                        # Change to the public directory to run the script
                        os.chdir(public_dir)
                        if sys.platform == 'win32':
                            subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', 'create_placeholder_images.ps1'], check=True)
                        else:
                            print("Placeholder script is for Windows only. Creating placeholder files manually.")
                            # Create placeholder files manually
                            for file_path in [favicon_path, logo192_path, logo512_path]:
                                if not os.path.exists(file_path):
                                    with open(file_path, 'w') as f:
                                        f.write("This is a placeholder image file.\n")
                                    print(f"Created placeholder file: {file_path}")
                        # Change back to the frontend directory
                        os.chdir(frontend_dir)
                    except Exception as e:
                        print(f"Error creating placeholder files: {str(e)}")
                        # Change back to the frontend directory
                        os.chdir(frontend_dir)
                else:
                    print("Placeholder script not found. Creating placeholder files manually.")
                    # Create placeholder files manually
                    for file_path in [favicon_path, logo192_path, logo512_path]:
                        if not os.path.exists(file_path):
                            with open(file_path, 'w') as f:
                                f.write("This is a placeholder image file.\n")
                            print(f"Created placeholder file: {file_path}")
            
            # Check if node_modules exists, if not, install dependencies
            if not os.path.exists('node_modules'):
                print("Installing frontend dependencies...")
                try:
                    subprocess.run([npm_cmd, 'install'], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error installing dependencies: {str(e)}")
                    os.chdir(original_dir)  # Change back to original directory
                    return
                except FileNotFoundError:
                    print("ERROR: npm command not found. Please make sure Node.js and npm are installed and in your PATH.")
                    os.chdir(original_dir)  # Change back to original directory
                    return
            
            # Start the React development server
            print("Starting frontend development server...")
            print("The frontend will be available at http://localhost:3000")
            try:
                subprocess.run([npm_cmd, 'start'], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error starting frontend server: {str(e)}")
            except FileNotFoundError:
                print("ERROR: npm command not found. Please make sure Node.js and npm are installed and in your PATH.")
        finally:
            # Always change back to the original directory
            os.chdir(original_dir)
    except Exception as e:
        print(f"Error running frontend: {str(e)}")

def wait_for_server(host, port, timeout=30):
    """Wait for a server to start listening on the specified port."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Try to connect to the server
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex((host, port))
            s.close()
            
            if result == 0:  # Port is open, server is running
                # Additional check to see if the WebSocket endpoint is ready
                # by making a simple HTTP request to the root endpoint
                import requests
                try:
                    response = requests.get(f"http://{host}:{port}/", timeout=2)
                    if response.status_code == 200:
                        print(f"Server is running on {host}:{port}")
                        # Give the server a moment to fully initialize WebSocket
                        time.sleep(2)
                        return True
                except Exception:
                    # If the HTTP request fails, the server might still be initializing
                    pass
            
            # Print a dot to show progress
            print(".", end="", flush=True)
            # Wait a bit before trying again
            time.sleep(1)
        except Exception as e:
            # Don't print the error, just wait and try again
            time.sleep(1)
    
    print(f"\nTimed out waiting for server to start on {host}:{port}")
    return False

def open_browser():
    """Open the browser to the frontend URL."""
    try:
        # Wait for the frontend server to start
        # The backend should already be running at this point
        print("Waiting for frontend server to start...")
        frontend_running = wait_for_server('localhost', 3000, timeout=30)
        if frontend_running:
            print("Opening browser to http://localhost:3000...")
            webbrowser.open('http://localhost:3000')
        else:
            print("Frontend server not detected. Not opening browser.")
    except Exception as e:
        print(f"Error opening browser: {str(e)}")

def main():
    """Run both backend and frontend servers."""
    print("Starting Web Log Monitor development servers...")
    
    # Start the backend server in a separate thread
    backend_thread = threading.Thread(target=run_backend)
    backend_thread.daemon = True
    backend_thread.start()
    
    # Open the browser after a delay
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Run the frontend server in the main thread
    try:
        run_frontend()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
    except Exception as e:
        print(f"Error in main: {str(e)}")
    
    print("Development servers stopped.")

if __name__ == "__main__":
    main()
