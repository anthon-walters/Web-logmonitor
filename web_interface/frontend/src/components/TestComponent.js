import React, { useState, useEffect } from 'react';

const TestComponent = () => {
  const [count, setCount] = useState(0);
  const [apiData, setApiData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const incrementCount = () => {
    setCount(count + 1);
  };

  const fetchApiData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Get authentication credentials
      const username = process.env.REACT_APP_API_USERNAME || 'admin';
      const password = process.env.REACT_APP_API_PASSWORD || 'changeme';
      
      // Create fetch options with authentication
      const fetchOptions = {
        headers: {
          'Authorization': 'Basic ' + btoa(`${username}:${password}`)
        },
        // Add a longer timeout for debugging
        timeout: 30000
      };
      
      // Fetch status from the API
      const response = await fetch('/api/status', fetchOptions);
      
      if (response.ok) {
        const data = await response.json();
        setApiData(data);
      } else {
        setError(`API error: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      setError(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Fetch data on component mount
  useEffect(() => {
    fetchApiData();
  }, []);

  return (
    <div className="bg-white shadow rounded-lg p-4 mb-4">
      <h2 className="text-lg font-semibold mb-2">React Test Component</h2>
      
      <div className="p-4 bg-blue-100 rounded mb-4">
        <p className="text-blue-800 mb-2">Counter: {count}</p>
        <button 
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          onClick={incrementCount}
        >
          Increment
        </button>
      </div>
      
      <div className="p-4 bg-green-100 rounded">
        <h3 className="font-medium mb-2">API Data Test</h3>
        
        {loading && <p className="text-gray-600">Loading...</p>}
        
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}
        
        {apiData && (
          <div>
            <p className="text-green-800 mb-2">API Response:</p>
            <pre className="bg-gray-100 p-2 rounded text-xs">
              {JSON.stringify(apiData, null, 2)}
            </pre>
          </div>
        )}
        
        <button 
          className="mt-4 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
          onClick={fetchApiData}
          disabled={loading}
        >
          {loading ? 'Loading...' : 'Refresh Data'}
        </button>
      </div>
      
      <div className="mt-4 p-4 bg-yellow-100 rounded">
        <h3 className="font-medium mb-2">Environment Variables</h3>
        <pre className="bg-gray-100 p-2 rounded text-xs">
          {JSON.stringify({
            NODE_ENV: process.env.NODE_ENV,
            REACT_APP_API_USERNAME: process.env.REACT_APP_API_USERNAME,
            REACT_APP_API_PASSWORD: process.env.REACT_APP_API_PASSWORD ? '[REDACTED]' : undefined,
            REACT_APP_API_TIMEOUT: process.env.REACT_APP_API_TIMEOUT,
            REACT_APP_POLLING_INTERVAL: process.env.REACT_APP_POLLING_INTERVAL
          }, null, 2)}
        </pre>
      </div>
    </div>
  );
};

export default TestComponent;
