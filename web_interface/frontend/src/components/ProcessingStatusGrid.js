import React from 'react';

const ProcessingStatusGrid = ({ statuses }) => {
  // Define status colors
  const statusColors = {
    processing: 'processing',
    waiting: 'waiting',
    done: 'done',
    disabled: 'disabled'
  };

  // Create an array of device names (H1 to H10)
  const devices = Array.from({ length: 10 }, (_, i) => `H${i + 1}`);

  // Create a grid with 5 columns and 2 rows
  const columns = 5;
  const rows = Math.ceil(devices.length / columns);
  const grid = Array.from({ length: rows }, () => Array(columns).fill(null));

  // Fill the grid with devices
  devices.forEach((device, index) => {
    const row = Math.floor(index / columns);
    const col = index % columns;
    grid[row][col] = device;
  });

  return (
    <div>
      {/* Status Legend */}
      <div className="flex items-center mb-4 space-x-4">
        <div className="text-sm font-medium">Status Legend:</div>
        <div className="flex items-center">
          <div className="w-4 h-4 bg-processing mr-1"></div>
          <span className="text-sm">Processing</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-4 bg-waiting mr-1"></div>
          <span className="text-sm">Waiting</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-4 bg-done mr-1"></div>
          <span className="text-sm">Done</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-4 bg-disabled mr-1"></div>
          <span className="text-sm">Disabled</span>
        </div>
      </div>

      {/* Status Grid */}
      <div className="grid grid-cols-5 gap-4">
        {devices.map((device) => {
          const status = statuses[device] || { status: 'waiting', count: 0 };
          const statusClass = statusColors[status.status] || 'waiting';
          
          return (
            <div 
              key={device} 
              className={`processing-status ${statusClass}`}
            >
              <div>{device}</div>
              <div>{status.count}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProcessingStatusGrid;
