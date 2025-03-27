import React from 'react';

const FileCountWidget = ({ data, monitoringStates }) => { // Add monitoringStates prop
  const { counts, total } = data;

  // Filter counts based on monitoringStates
  const filteredCounts = counts.filter(item => {
    // Extract device name (e.g., "H1") from item.directory
    const deviceMatch = item.directory.match(/^H\d+/);
    const deviceName = deviceMatch ? deviceMatch[0] : null;
    // Keep the item if the device is monitored (or if deviceName couldn't be extracted)
    return deviceName ? monitoringStates[deviceName] !== false : true; // Default to true if no device match
  });

  return (
    <div className="bg-white shadow rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2">Overall total JPG files: {total}</h2>
      
      <div className="overflow-auto max-h-48">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Directory
              </th>
              <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                Count
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {/* Map over filteredCounts instead of counts */}
            {filteredCounts.map((item, index) => (
              <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                <td className="px-6 py-2 whitespace-nowrap text-sm text-gray-900">
                  {item.directory} {/* Assuming directory is like 'H1', 'H2' etc. */}
                </td>
                <td className="px-6 py-2 whitespace-nowrap text-sm text-gray-900 text-center">
                  {item.count}
                </td>
              </tr>
            ))}
            {/* Check filteredCounts length for the "No data" message */}
            {filteredCounts.length === 0 && (
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

export default FileCountWidget;
