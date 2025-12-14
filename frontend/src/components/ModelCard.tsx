import React from 'react';
import { ModelScore } from '../types/model';

interface ModelCardProps {
  model: ModelScore;
  onView?: (id: string) => void;
  onDelete?: (id: string) => void;
}

const ModelCard: React.FC<ModelCardProps> = ({ model, onView, onDelete }) => {
  const getScoreColor = (score: number | null | undefined): string => {
    if (score == null) return 'text-gray-400';
    if (score >= 0.7) return 'text-green-600';
    if (score >= 0.4) return 'text-yellow-600';
    return 'text-red-600';
  };

  const formatScore = (score: number | null | undefined): string => {
    if (score == null || isNaN(score)) return '—';
    return `${(score * 100).toFixed(0)}%`;
  };

  const formatNetScore = (score: number | null | undefined): string => {
    if (score == null || isNaN(score)) return '—';
    return `${(score * 100).toFixed(1)}%`;
  };

  // Truncate long names
  const displayName = model.name && model.name.length > 25 
    ? model.name.substring(0, 22) + '...' 
    : (model.name || 'Unnamed Model');

  return (
    <div className="border rounded-lg p-4 shadow-md hover:shadow-lg transition-shadow bg-white">
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-semibold text-gray-800" title={model.name}>
          {displayName}
        </h3>
        <span className={`text-xl font-bold ${getScoreColor(model.net_score)}`}>
          {formatNetScore(model.net_score)}
        </span>
      </div>
      
      <div className="text-xs text-gray-500 mb-2 font-mono">
        {model.modelId}
      </div>
      
      <div className="text-sm text-gray-600 mb-3">
        <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">{model.category || 'MODEL'}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div>
          <span className="text-gray-600">License:</span>
          <span className="ml-2 font-medium">{formatScore(model.license)}</span>
        </div>
        <div>
          <span className="text-gray-600">Bus Factor:</span>
          <span className="ml-2 font-medium">{formatScore(model.bus_factor)}</span>
        </div>
        <div>
          <span className="text-gray-600">Code Quality:</span>
          <span className="ml-2 font-medium">{formatScore(model.code_quality)}</span>
        </div>
        <div>
          <span className="text-gray-600">Ramp-Up:</span>
          <span className="ml-2 font-medium">{formatScore(model.ramp_up_time)}</span>
        </div>
      </div>

      <div className="flex space-x-2">
        {onView && (
          <button
            onClick={() => onView(model.modelId)}
            className="flex-1 bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
            aria-label={`View lineage for ${model.name}`}
          >
            View Lineage
          </button>
        )}
        {onDelete && (
          <button
            onClick={() => onDelete(model.modelId)}
            className="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
            aria-label={`Delete ${model.name}`}
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
};

export default ModelCard;