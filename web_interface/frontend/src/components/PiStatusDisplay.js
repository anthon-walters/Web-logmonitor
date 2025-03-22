import React, { useEffect } from 'react';
import { FaToggleOn, FaToggleOff } from 'react-icons/fa';

const PiStatusDisplay = ({ statuses, monitoringStates, onToggleMonitoring }) => {
  // Create an array of device names (H1 to H10)
  const devices = Array.from({ length: 10 }, (_, i) => `H${i + 1}`);
  
  // Log the props for debugging
  useEffect(() => {
    console.log('PiStatusDisplay props:', { statuses, monitoringStates });
  }, [statuses, monitoringStates]);

  return (
    <div className="flex flex-wrap gap-2 justify-between">
      {devices.map((device) => {
        const isOnline = statuses[device] || false;
        const isMonitored = monitoringStates[device] || false;
        
        let statusClass = 'status-offline';
        if (!isMonitored) {
          statusClass = 'status-disabled';
        } else if (isOnline) {
          statusClass = 'status-online';
        }
        
        return (
          <div key={device} className="flex items-center justify-between px-1">
            <div className="flex items-center">
              <span className={`status-indicator ${statusClass}`}></span>
              <span className="text-sm font-medium">{device}</span>
            </div>
            <button
              onClick={() => onToggleMonitoring(device, !isMonitored)}
              className="text-blue-500 hover:text-blue-700 focus:outline-none"
              title={isMonitored ? "Disable monitoring" : "Enable monitoring"}
            >
              {isMonitored ? (
                <FaToggleOn className="h-5 w-5" />
              ) : (
                <FaToggleOff className="h-5 w-5" />
              )}
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default PiStatusDisplay;
