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

  // Use polling instead of WebSockets for more stability
  useEffect(() => {
    let pollInterval = null;
    let isPolling = false;
    
    const fetchData = async () => {
      if (isPolling) return; // Prevent overlapping requests
      
      isPolling = true;
      
      try {
        // In development mode, connect directly to the backend API
        const apiBaseUrl = process.env.NODE_ENV === 'production'
          ? ''
          : 'http://localhost:7171';
        
        console.log(`Connecting to API at: ${apiBaseUrl} - ${new Date().toISOString()}`);
        
        // Get authentication credentials
        const username = process.env.REACT_APP_API_USERNAME || 'admin';
        const password = process.env.REACT_APP_API_PASSWORD || 'changeme';
        
        console.log(`Using credentials: ${username}/${password}`);
        
        // Get API timeout from environment variable or use default
        const apiTimeout = parseInt(process.env.REACT_APP_API_TIMEOUT || '10000', 10);
        
        // Common fetch options with authentication
        const fetchOptions = {
          headers: {
            'Authorization': 'Basic ' + btoa(`${username}:${password}`)
          }
        };
        
        console.log('Fetching data from API endpoints...');
        
        // Fetch status first to check if the API is accessible
        console.log('Fetching status...');
        const statusRes = await fetch(`${apiBaseUrl}/api/status`, fetchOptions);
        console.log(`Status response: ${statusRes.status} ${statusRes.statusText}`);
        
        if (!statusRes.ok) {
          console.error(`Status API error: ${statusRes.status} ${statusRes.statusText}`);
          setConnected(false);
          return;
        }
        
        // If status is OK, fetch the rest of the data
        console.log('Fetching remaining endpoints...');
        const [titleRes, fileCountsRes, piStatusRes, piStatisticsRes, piMonitorRes, successRatesRes] = await Promise.all([
          fetch(`${apiBaseUrl}/api/title`, fetchOptions),
          fetch(`${apiBaseUrl}/api/file-counts`, fetchOptions),
          fetch(`${apiBaseUrl}/api/pi-status`, fetchOptions),
          fetch(`${apiBaseUrl}/api/pi-statistics`, fetchOptions),
          fetch(`${apiBaseUrl}/api/pi-monitor`, fetchOptions),
          fetch(`${apiBaseUrl}/api/success-rates`, fetchOptions)
        ]);
        
        // Log response status for each endpoint
        console.log(`Title response: ${titleRes.status} ${titleRes.statusText}`);
        console.log(`File counts response: ${fileCountsRes.status} ${fileCountsRes.statusText}`);
        console.log(`Pi status response: ${piStatusRes.status} ${piStatusRes.statusText}`);
        console.log(`Pi statistics response: ${piStatisticsRes.status} ${piStatisticsRes.statusText}`);
        console.log(`Pi monitor response: ${piMonitorRes.status} ${piMonitorRes.statusText}`);
        console.log(`Success rates response: ${successRatesRes.status} ${successRatesRes.statusText}`);
        
        // Check if all requests were successful
        if (statusRes.ok && titleRes.ok && fileCountsRes.ok && piStatusRes.ok && piStatisticsRes.ok && piMonitorRes.ok && successRatesRes.ok) {
          // Parse all responses
          const [statusData, titleData, file_counts, pi_status, pi_statistics, pi_monitor, success_rates] = await Promise.all([
            statusRes.json(),
            titleRes.json(),
            fileCountsRes.json(),
            piStatusRes.json(),
            piStatisticsRes.json(),
            piMonitorRes.json(),
            successRatesRes.json()
          ]);
          
          // Generate processing status from pi_status
          const processing_status = {
            statuses: {}
          };
          
          // Convert pi_status to processing_status format
          if (pi_status && pi_status.statuses) {
            Object.entries(pi_status.statuses).forEach(([device, isOnline]) => {
              // If monitoring is disabled for this device, mark as disabled
              if (!monitoringStates[device]) {
                processing_status.statuses[device] = { status: 'disabled', count: 0 };
              } else if (isOnline) {
                // If device is online, mark as processing
                processing_status.statuses[device] = { status: 'processing', count: 0 };
                
                // Try to get count from pi_monitor data
                const deviceData = pi_monitor.data.find(item => item.device === device);
                if (deviceData) {
                  processing_status.statuses[device].count = deviceData.processed;
                }
              } else {
                // If device is offline, mark as waiting
                processing_status.statuses[device] = { status: 'waiting', count: 0 };
              }
            });
          }
          
          // Log the data received from the API
          console.log('Data received from API:');
          console.log('title:', titleData);
          console.log('file_counts:', file_counts);
          console.log('pi_status:', pi_status);
          console.log('pi_statistics:', pi_statistics);
          console.log('pi_monitor:', pi_monitor);
          console.log('success_rates:', success_rates);
          console.log('processing_status:', processing_status);
          
          // Update state with all data
          setData({
            file_counts,
            pi_status,
            pi_statistics,
            pi_monitor,
            success_rates,
            processing_status,
            timestamp: new Date().toISOString(),
            title: titleData.title
          });
          
          setConnected(true);
        } else {
          console.error('One or more API requests failed');
          setConnected(false);
        }
      } catch (error) {
        console.error('Error fetching data:', error);
        setConnected(false);
      } finally {
        isPolling = false;
      }
    };
    
    // Initial fetch
    fetchData();
    
    // Get polling interval from environment variable or use default
    const pollingInterval = parseInt(process.env.REACT_APP_POLLING_INTERVAL || '5000', 10);
    console.log(`Setting up polling with interval: ${pollingInterval}ms`);
    
    // Set up polling interval
    pollInterval = setInterval(fetchData, pollingInterval);
    
    // Clean up on unmount
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [monitoringStates]); // Add monitoringStates as dependency to update processing status when monitoring changes

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
          {/* Log the data being passed to ProcessingStatusGrid */}
          {console.log('Data passed to ProcessingStatusGrid:', {
            statuses: data.processing_status.statuses
          })}
          {console.log('ProcessingStatusGrid data details:', JSON.stringify(data.processing_status.statuses))}
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
        {/* Log the data being passed to PiStatusDisplay */}
        {console.log('Data passed to PiStatusDisplay:', {
          statuses: data.pi_status.statuses,
          monitoringStates: monitoringStates
        })}
        {console.log('PiStatusDisplay data details:', JSON.stringify(data.pi_status.statuses))}
        {console.log('PiStatusDisplay monitoringStates details:', JSON.stringify(monitoringStates))}
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
