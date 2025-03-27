import React, { useState, useEffect, useCallback } from 'react';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import FileCountWidget from './components/FileCountWidget';
import StatusWidget from './components/StatusWidget';
import PiMonitorWidget from './components/PiMonitorWidget';
import ProcessingStatusGrid from './components/ProcessingStatusGrid';
import PiStatusDisplay from './components/PiStatusDisplay';
import ChartsWidget from './components/ChartsWidget';

// Register Chart.js components
ChartJS.register(ArcElement, Tooltip, Legend);

function App() {
  const [data, setData] = useState({
    file_counts: { counts: [], total: 0 },
    pi_status: { statuses: {} },
    pi_statistics: { sent: [], tagged: [], bibs: [], totals: [0, 0, 0] },
    pi_monitor: { data: [] },
    success_rates: { cv_rate: 0, bib_rate: 0 },
    processing_status: { statuses: {} },
    timestamp: null,
    title: "Web Log Monitor"
  });
  
  const [connected, setConnected] = useState(false);
  const [monitoringStates, setMonitoringStates] = useState({});

  // Initialize monitoring states for all devices
  useEffect(() => {
    const initialStates = {};
    for (let i = 1; i <= 10; i++) {
      initialStates[`H${i}`] = true;
    }
    setMonitoringStates(initialStates);
  }, []);

  // WebSocket connection
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;

    const connectWebSocket = () => {
      // Determine WebSocket URL based on environment
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = process.env.NODE_ENV === 'production' ? window.location.host : 'localhost:7171';
      const wsUrl = `${wsProtocol}//${wsHost}/ws`;

      console.log(`Attempting to connect WebSocket to: ${wsUrl}`);
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        // Clear any reconnect timeout
        if (reconnectTimeout) {
          clearTimeout(reconnectTimeout);
          reconnectTimeout = null;
        }
        // Optional: Send authentication if needed after connection
        // const username = process.env.REACT_APP_API_USERNAME || 'admin';
        // const password = process.env.REACT_APP_API_PASSWORD || 'changeme';
        // ws.send(JSON.stringify({ type: 'auth', data: { username, password } }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          // console.log('WebSocket message received:', message);

          if (message.type === 'all_data') {
            // Directly use the data structure from the backend
            setData(prevData => ({
              ...prevData, // Keep existing title if not provided by WS
              ...message.data, // Overwrite with new data from WebSocket
              timestamp: message.data.timestamp || new Date().toISOString() // Ensure timestamp is updated
            }));
          } else {
             console.log('Received unhandled WebSocket message type:', message.type);
          }
        } catch (error) {
          console.error('Error processing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Don't set connected to false immediately, wait for onclose
      };

      ws.onclose = (event) => {
        console.log(`WebSocket disconnected: ${event.code} ${event.reason}`);
        setConnected(false);
        ws = null; // Ensure ws is nullified

        // Attempt to reconnect after a delay
        if (!reconnectTimeout) {
          const reconnectDelay = 5000; // 5 seconds
          console.log(`Attempting to reconnect WebSocket in ${reconnectDelay / 1000} seconds...`);
          reconnectTimeout = setTimeout(connectWebSocket, reconnectDelay);
        }
      };
    };

    connectWebSocket();

    // Clean up on component unmount
    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (ws) {
        console.log('Closing WebSocket connection on component unmount');
        ws.close();
        ws = null;
      }
    };
  }, []); // Empty dependency array ensures this runs only once on mount

  // Handle toggling monitoring for a device
  const toggleMonitoring = useCallback((device, state) => {
    setMonitoringStates(prev => ({
      ...prev,
      [device]: state
    }));
    
    // In development mode, connect directly to the backend API
    const apiBaseUrl = process.env.NODE_ENV === 'production'
      ? ''
      : 'http://localhost:7171';
    
    // Send update to server with authentication
    const username = process.env.REACT_APP_API_USERNAME || 'admin';
    const password = process.env.REACT_APP_API_PASSWORD || 'changeme';
    
    // Get API timeout from environment variable or use default
    const apiTimeout = parseInt(process.env.REACT_APP_API_TIMEOUT || '10000', 10);
    
    // Create AbortController for timeout
    const controller = new AbortController();
    setTimeout(() => controller.abort(), apiTimeout);
    
    fetch(`${apiBaseUrl}/api/monitoring/${device}?state=${state}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + btoa(`${username}:${password}`)
      },
      signal: controller.signal
    })
    .then(response => {
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please check your credentials.');
        }
        throw new Error(`Server responded with status: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      console.log('Monitoring state updated:', data);
    })
    .catch(error => {
      console.error('Error updating monitoring state:', error);
      // Revert the UI state since the server update failed
      setMonitoringStates(prev => ({
        ...prev,
        [device]: !state
      }));
      // You could also add a toast notification here to inform the user
      alert(`Failed to update monitoring state: ${error.message}`);
    });
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <header className="bg-white shadow rounded-lg p-4 mb-4">
        <h1 className="text-2xl font-bold text-gray-800">{data.title}</h1>
        <div className="flex items-center mt-2">
          <span className={`h-3 w-3 rounded-full mr-2 ${connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span className="text-sm text-gray-600">{connected ? 'Connected' : 'Disconnected'}</span>
          {data.timestamp && (
            <span className="text-xs text-gray-500 ml-4">
              Last updated: {new Date(data.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>
      
      
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 mb-4">
        <FileCountWidget data={data.file_counts} monitoringStates={monitoringStates} />
        <StatusWidget 
          title="JPG files sent for Tagging" 
          data={data.pi_statistics.sent} 
          total={data.pi_statistics.totals[0]} 
          monitoringStates={monitoringStates} 
        />
        <StatusWidget 
          title="JPG files tagged" 
          data={data.pi_statistics.tagged} 
          total={data.pi_statistics.totals[1]} 
          monitoringStates={monitoringStates} 
        />
        <StatusWidget 
          title="Bibs found" 
          data={data.pi_statistics.bibs} 
          total={data.pi_statistics.totals[2]} 
          monitoringStates={monitoringStates} 
        />
        <PiMonitorWidget data={data.pi_monitor.data} monitoringStates={monitoringStates} />
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3 bg-white shadow rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Processing Status</h2>
          {/* Log the data being passed to ProcessingStatusGrid */}
          {/* Removed console logs */}
          <ProcessingStatusGrid statuses={data.processing_status ? data.processing_status.statuses : {}} />
        </div>

        <div className="lg:col-span-1 bg-white shadow rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Success Rates</h2>
          <ChartsWidget 
            cvRate={data.success_rates.cv_rate} 
            bibRate={data.success_rates.bib_rate} 
          />
        </div>
      </div>
      
      <div className="mt-4 bg-white shadow rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4">Devices Online</h2>
        {/* Log the data being passed to PiStatusDisplay */}
          {/* Removed console logs */}
          <PiStatusDisplay
            statuses={data.pi_status ? data.pi_status.statuses : {}}
            monitoringStates={monitoringStates}
            onToggleMonitoring={toggleMonitoring}
          />
      </div>
    </div>
  );
}

export default App;
