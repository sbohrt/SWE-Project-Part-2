import React, { useState } from 'react';
import { modelService } from '../services/modelService';
import { LineageNode } from '../types/model';
import Loading from '../components/Loading';
import ErrorMessage from '../components/ErrorMessage';

const Lineage: React.FC = () => {
  const [modelId, setModelId] = useState('');
  const [lineage, setLineage] = useState<LineageNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!modelId.trim()) {
      setError('Please enter a model ID');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await modelService.getLineage(modelId);
      setLineage(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch lineage data');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Model Lineage Graph</h1>

      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <form onSubmit={handleFetch} className="flex gap-4">
          <input
            type="text"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            placeholder="Enter Model ID"
            className="flex-1 shadow appearance-none border rounded py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
            aria-label="Enter model ID to view lineage"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded"
          >
            {loading ? 'Loading...' : 'View Lineage'}
          </button>
        </form>
      </div>

      {error && <ErrorMessage message={error} />}

      {lineage && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-bold mb-4">{lineage.name}</h2>
          
          {lineage.parents && lineage.parents.length > 0 && (
            <div className="mb-4">
              <h3 className="font-semibold text-gray-700 mb-2">Parent Models:</h3>
              <ul className="list-disc list-inside">
                {lineage.parents.map((parent, idx) => (
                  <li key={idx} className="text-blue-600">{parent}</li>
                ))}
              </ul>
            </div>
          )}

          {lineage.children && lineage.children.length > 0 && (
            <div>
              <h3 className="font-semibold text-gray-700 mb-2">Child Models:</h3>
              <ul className="list-disc list-inside">
                {lineage.children.map((child, idx) => (
                  <li key={idx} className="text-green-600">{child}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-sm text-gray-500 mt-4">
            Note: D3 visualization will be added in the next iteration
          </p>
        </div>
      )}
    </div>
  );
};

export default Lineage;