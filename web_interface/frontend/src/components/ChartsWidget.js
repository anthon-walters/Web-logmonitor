import React from 'react';
import { Pie } from 'react-chartjs-2';

const ChartsWidget = ({ cvRate, bibRate }) => {
  // Format rates to ensure they're valid numbers between 0 and 100
  const formattedCvRate = Math.min(Math.max(parseFloat(cvRate) || 0, 0), 100);
  const formattedBibRate = Math.min(Math.max(parseFloat(bibRate) || 0, 0), 100);
  
  // Create data for CV success rate pie chart
  const cvData = {
    labels: ['Success', 'Failure'],
    datasets: [
      {
        data: [formattedCvRate, 100 - formattedCvRate],
        backgroundColor: ['#4CAF50', '#F44336'],
        borderWidth: 1,
      },
    ],
  };
  
  // Create data for bib detection rate pie chart
  const bibData = {
    labels: ['Success', 'Failure'],
    datasets: [
      {
        data: [formattedBibRate, 100 - formattedBibRate],
        backgroundColor: ['#2196F3', '#9E9E9E'],
        borderWidth: 1,
      },
    ],
  };
  
  // Chart options
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          boxWidth: 12,
          font: {
            size: 10
          }
        }
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            return `${context.label}: ${context.raw.toFixed(1)}%`;
          }
        }
      }
    }
  };

  return (
    <div className="grid grid-cols-2 gap-4 h-full">
      <div className="flex flex-col items-center">
        <h3 className="text-sm font-medium mb-2">CV Success</h3>
        <div className="h-24 w-full">
          <Pie data={cvData} options={options} />
        </div>
        <div className="text-sm font-bold mt-2">{formattedCvRate.toFixed(1)}%</div>
      </div>
      
      <div className="flex flex-col items-center">
        <h3 className="text-sm font-medium mb-2">Bib Detection</h3>
        <div className="h-24 w-full">
          <Pie data={bibData} options={options} />
        </div>
        <div className="text-sm font-bold mt-2">{formattedBibRate.toFixed(1)}%</div>
      </div>
    </div>
  );
};

export default ChartsWidget;
