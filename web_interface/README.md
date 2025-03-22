# Web Log Monitor Interface

A modern web interface for the Log Monitor application, providing real-time monitoring of log files and device statuses.

## Features

- Modern, responsive web interface
- Real-time updates via WebSockets
- Interactive device monitoring controls
- Visual status indicators
- Success rate charts
- Processing status grid

## Architecture

The web interface consists of two main components:

1. **Backend**: A FastAPI server that interfaces with the existing Log Monitor application and provides data to the frontend via REST API and WebSockets.
2. **Frontend**: A React application that provides a modern user interface for monitoring log files and device statuses.

## Setup

### Prerequisites

- Python 3.7+
- Node.js 14+ and npm (required for development and building the frontend)
- The existing Log Monitor application

### Installation

1. Install backend dependencies:

```bash
cd web_interface/backend
pip install -r requirements.txt
```

2. Install frontend dependencies (only needed for development or building):

```bash
cd web_interface/frontend
npm install
```

## Running the Application

### Development Mode

There are multiple ways to run the application in development mode:

#### Option 1: Run both backend and frontend (requires Node.js and npm)

To run both the backend and frontend in development mode:

```bash
python web_interface/run_dev.py
```

This will:
- Check if Node.js and npm are installed
- Install frontend dependencies if needed
- Start the FastAPI backend on port 7171
- Start the React development server on port 3000
- Open your browser to http://localhost:3000

#### Option 2: Run only the backend

If you just want to run the backend server:

```bash
python web_interface/run_backend.py
```

This will:
- Install backend dependencies if needed
- Start the FastAPI backend on port 7171
- Serve the static frontend files if they exist (from a previous build)

You can then access the application at http://localhost:7171

### Production Mode

There are two ways to run the application in production mode:

#### Option 1: One-step production deployment

To build the frontend and run the backend in a single step:

```bash
python web_interface/run_production.py
```

This will:
- Build the frontend for production (if Node.js and npm are available)
- Start the FastAPI backend on port 7171
- Serve the static frontend files from the same server

#### Option 2: Manual build and run

To manually build the frontend for production:

```bash
cd web_interface/frontend
npm install
npm run build
```

Then, to run the application in production mode:

```bash
python web_interface/run_backend.py
```

This will serve both the API and the static frontend files from the same server on port 7171.

## Troubleshooting

### Node.js and npm not found

If you get an error about npm not being found, you need to install Node.js and npm:

1. Download and install Node.js from https://nodejs.org/
2. Make sure Node.js and npm are in your PATH

### Backend dependencies not found

If you get an error about missing Python dependencies:

```bash
cd web_interface/backend
pip install -r requirements.txt
```

## API Endpoints

The backend provides the following API endpoints:

- `GET /api/status`: Get the current status of the monitoring system
- `GET /api/file-counts`: Get file counts for each Pi directory
- `GET /api/pi-status`: Get the status of all Pi devices
- `GET /api/pi-statistics`: Get statistics for all Pi devices
- `GET /api/pi-monitor`: Get monitoring data for all Pi devices
- `GET /api/success-rates`: Get CV and bib detection success rates
- `POST /api/monitoring/{device}`: Set the monitoring state for a device
- `WebSocket /ws`: WebSocket endpoint for real-time updates

## Technologies Used

### Backend
- FastAPI: Modern, high-performance web framework
- Uvicorn: ASGI server
- WebSockets: For real-time updates

### Frontend
- React: JavaScript library for building user interfaces
- Tailwind CSS: Utility-first CSS framework
- Chart.js: For creating charts
- React Icons: For modern, customizable icons

## Customization

The web interface can be customized by modifying the following files:

- `web_interface/frontend/src/App.js`: Main application component
- `web_interface/frontend/src/components/`: UI components
- `web_interface/frontend/src/index.css`: CSS styles
- `web_interface/frontend/tailwind.config.js`: Tailwind CSS configuration
