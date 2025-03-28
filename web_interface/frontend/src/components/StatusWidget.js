import React from 'react';

const StatusWidget = ({ title, data, total, monitoringStates }) => { // Add monitoringStates prop

  // Filter data based on monitoringStates
  const filteredData = data.filter(item => {
    // Keep the item only if the device is explicitly monitored (state is true)
    return monitoringStates[item.device] === true;
  });

  // Recalculate total based on filtered data
  const filteredTotal = filteredData.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="bg-white shadow rounded-lg p-4">
      {/* Display filteredTotal */}
      <h2 className="text-lg font-semibold mb-2">{title}: {filteredTotal}</h2>
      
      <div className="overflow-auto max-h-48">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Device
              </th>
              <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                Count
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {/* Map over filteredData */}
            {filteredData.map((item, index) => (
              <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                <td className="px-6 py-2 whitespace-nowrap text-sm text-gray-900">
                  {item.device}
                </td>
                <td className="px-6 py-2 whitespace-nowrap text-sm text-gray-900 text-center">
                  {item.count}
                </td>
              </tr>
            ))}
            {/* Check filteredData length */}
            {filteredData.length === 0 && (
              <tr>
                <td colSpan="2" className="px-6 py-4 text-center text-sm text-gray-500">
                  No data available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default StatusWidget;
