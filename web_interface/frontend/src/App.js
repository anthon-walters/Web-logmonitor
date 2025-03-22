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
    timestamp: null
  });
  
  const [connected, setConnected] = useState(false);
  const [socket, setSocket] = useState(null);
  const [monitoringStates, setMonitoringStates] = useState({});

  // Initialize monitoring states for all devices
  useEffect(() => {
    const initialStates = {};
    for (let i = 1; i <= 10; i++) {
      initialStates[`H${i}`] = true;
    }
    setMonitoringStates(initialStates);
  }, []);

  // Connect to WebSocket
  useEffect(() => {
    // Track reconnection attempts to implement exponential backoff
    let reconnectAttempts = 0;
    let reconnectTimeout = null;
    
    const connectWebSocket = () => {
      // Clear any existing reconnect timeout
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      
      // In development mode, connect directly to the backend WebSocket
      // Use explicit protocol, host, and port to avoid proxy issues
      const wsUrl = process.env.NODE_ENV === 'production'
        ? `ws://${window.location.host}/ws`
        : 'ws://localhost:7171/ws';
      
      // Don't attempt to connect if we already have a socket
      if (socket && socket.readyState !== WebSocket.CLOSED && socket.readyState !== WebSocket.CLOSING) {
        console.log('WebSocket already connected or connecting, not creating a new connection');
        return;
      }
      
      console.log('Connecting to WebSocket at:', wsUrl);
      
      try {
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('WebSocket connected');
          setConnected(true);
          reconnectAttempts = 0; // Reset reconnect attempts on successful connection
          
          // Request initial data
          try {
            ws.send(JSON.stringify({ type: 'request_data' }));
          } catch (error) {
            console.error('Error sending initial data request:', error);
          }
        };
        
        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === 'all_data') {
              setData(message.data);
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };
        
        ws.onclose = (event) => {
          console.log(`WebSocket disconnected with code: ${event.code}, reason: ${event.reason}`);
          setConnected(false);
          setSocket(null);
          
          // Implement exponential backoff for reconnection attempts
          reconnectAttempts++;
          const delay = Math.min(30000, Math.pow(2, reconnectAttempts) * 1000); // Max 30 seconds
          console.log(`Attempting to reconnect in ${delay/1000} seconds (attempt ${reconnectAttempts})`);
          
          reconnectTimeout = setTimeout(() => {
            connectWebSocket();
          }, delay);
        };
        
        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          // Don't close the socket here, let the onclose handler handle it
        };
        
        setSocket(ws);
      } catch (error) {
        console.error('Error creating WebSocket:', error);
        setConnected(false);
        setSocket(null);
        
        // Implement exponential backoff for reconnection attempts
        reconnectAttempts++;
        const delay = Math.min(30000, Math.pow(2, reconnectAttempts) * 1000); // Max 30 seconds
        console.log(`Attempting to reconnect in ${delay/1000} seconds (attempt ${reconnectAttempts})`);
        
        reconnectTimeout = setTimeout(() => {
          connectWebSocket();
        }, delay);
      }
    };
    
    // Add a small delay before the first connection attempt to ensure backend is ready
    const initialConnectionTimeout = setTimeout(() => {
      connectWebSocket();
    }, 2000); // 2 second delay before first connection attempt
    
  // Clean up on unmount
  return () => {
    if (socket) {
      socket.close();
    }
  };
}, [socket]);

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
    
    // Send update to server
    fetch(`${apiBaseUrl}/api/monitoring/${device}?state=${state}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log('Monitoring state updated:', data);
    })
    .catch(error => {
      console.error('Error updating monitoring state:', error);
    });
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <header className="bg-white shadow rounded-lg p-4 mb-4">
        <h1 className="text-2xl font-bold text-gray-800">Web Log Monitor</h1>
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
        <FileCountWidget data={data.file_counts} />
        <StatusWidget 
          title="JPG files sent for Tagging" 
          data={data.pi_statistics.sent} 
          total={data.pi_statistics.totals[0]} 
        />
        <StatusWidget 
          title="JPG files tagged" 
          data={data.pi_statistics.tagged} 
          total={data.pi_statistics.totals[1]} 
        />
        <StatusWidget 
          title="Bibs found" 
          data={data.pi_statistics.bibs} 
          total={data.pi_statistics.totals[2]} 
        />
        <PiMonitorWidget data={data.pi_monitor.data} />
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3 bg-white shadow rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Processing Status</h2>
          <ProcessingStatusGrid statuses={data.processing_status.statuses} />
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
        <PiStatusDisplay 
          statuses={data.pi_status.statuses} 
          monitoringStates={monitoringStates}
          onToggleMonitoring={toggleMonitoring}
        />
      </div>
    </div>
  );
}

export default App;
