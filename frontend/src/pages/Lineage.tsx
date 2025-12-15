import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { modelService } from '../services/modelService';
import { LineageNode } from '../types/model';
import ErrorMessage from '../components/ErrorMessage';

const Lineage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [modelId, setModelId] = useState(searchParams.get('artifactId') || '');
  const [lineage, setLineage] = useState<LineageNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    document.title = 'Model Lineage - Model Registry';
  }, []);

  const fetchLineage = async (id: string) => {
    if (!id.trim()) {
      setError('Please enter a model ID');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await modelService.getLineage(id);
      setLineage(data);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to fetch lineage data');
    } finally {
      setLoading(false);
    }
  };

  // Auto-fetch if artifactId is in URL
  useEffect(() => {
    const artifactId = searchParams.get('artifactId');
    if (artifactId) {
      setModelId(artifactId);
      fetchLineage(artifactId);
    }
  }, [searchParams]);

  const handleFetch = async (e: React.FormEvent) => {
    e.preventDefault();
    fetchLineage(modelId);
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
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded"
          >
            {loading ? 'Loading...' : 'View Lineage'}
          </button>
        </form>
      </div>

      {error && <ErrorMessage message={error} />}

      {lineage && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-bold mb-4">Lineage Graph</h2>
          
          {lineage.nodes && lineage.nodes.length > 0 && (
            <div className="mb-4">
              <h3 className="font-semibold text-gray-700 mb-2">Nodes ({lineage.nodes.length}):</h3>
              <ul className="list-disc list-inside space-y-1">
                {lineage.nodes.map((node, idx) => (
                  <li key={idx} className="text-blue-600">
                    <span className="font-medium">{node.name || node.artifact_id}</span>
                    <span className="text-gray-500 text-sm ml-2">({node.artifact_id})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {lineage.edges && lineage.edges.length > 0 && (
            <div>
              <h3 className="font-semibold text-gray-700 mb-2">Relationships ({lineage.edges.length}):</h3>
              <ul className="list-disc list-inside space-y-1">
                {lineage.edges.map((edge, idx) => (
                  <li key={idx} className="text-green-600">
                    <span className="font-mono text-sm">{edge.from_node_artifact_id}</span>
                    <span className="mx-2">→</span>
                    <span className="font-mono text-sm">{edge.to_node_artifact_id}</span>
                    <span className="text-gray-500 text-sm ml-2">({edge.relationship})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(!lineage.edges || lineage.edges.length === 0) && (
            <p className="text-gray-500 mt-2">No lineage relationships found for this model.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default Lineage;