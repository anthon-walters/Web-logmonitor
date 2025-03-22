import os
import sys
import subprocess
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

def build_frontend():
    """Build the React frontend for production."""
    try:
        # Get the absolute path to the frontend directory
        frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
        public_dir = os.path.join(frontend_dir, 'public')
        
        # Check if npm is installed
        npm_path = check_npm()
        if not npm_path:
            print("Skipping frontend build. The backend will still run, but without the frontend.")
            return False
        
        npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'
        
        # Check if package.json exists
        package_json_path = os.path.join(frontend_dir, 'package.json')
        if not os.path.exists(package_json_path):
            print(f"ERROR: package.json not found at {package_json_path}")
            print("Skipping frontend build. The backend will still run, but without the frontend.")
            return False
        
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
            
            print("Building frontend for production...")
            
            # Install dependencies if needed
            if not os.path.exists('node_modules'):
                print("Installing frontend dependencies...")
                try:
                    subprocess.run([npm_cmd, 'install'], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error installing dependencies: {str(e)}")
                    os.chdir(original_dir)  # Change back to original directory
                    return False
                except FileNotFoundError:
                    print("ERROR: npm command not found. Please make sure Node.js and npm are installed and in your PATH.")
                    os.chdir(original_dir)  # Change back to original directory
                    return False
            
            # Build the frontend
            try:
                subprocess.run([npm_cmd, 'run', 'build'], check=True)
                print("Frontend built successfully.")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Error building frontend: {str(e)}")
                return False
            except FileNotFoundError:
                print("ERROR: npm command not found. Please make sure Node.js and npm are installed and in your PATH.")
                return False
        finally:
            # Always change back to the original directory
            os.chdir(original_dir)
    except Exception as e:
        print(f"Error building frontend: {str(e)}")
        return False

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
        
        print("Starting backend server in production mode...")
        print("The server will be available at http://localhost:7171")
        print("Press Ctrl+C to stop the server")
        
        # Run the backend server without changing directory
        subprocess.run([sys.executable, backend_main])
    except Exception as e:
        print(f"Error running backend: {str(e)}")

def main():
    """Build the frontend and run the backend server."""
    print("Preparing Web Log Monitor for production...")
    
    # Build the frontend
    frontend_built = build_frontend()
    
    if frontend_built:
        print("Frontend built successfully. The web interface will be available at http://localhost:7171")
    else:
        print("Frontend build skipped or failed. Only the API will be available at http://localhost:7171")
    
    # Run the backend server
    run_backend()

if __name__ == "__main__":
    main()
