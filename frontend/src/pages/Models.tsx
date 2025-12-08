import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { modelService } from '../services/modelService';
import { ModelScore } from '../types/model';
import ModelCard from '../components/ModelCard';
import Loading from '../components/Loading';
import ErrorMessage from '../components/ErrorMessage';

const Models: React.FC = () => {
  const [models, setModels] = useState<ModelScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchModels = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await modelService.getAllModels();
      setModels(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch models');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const handleView = (id: string) => {
    navigate(`/models/${id}`);
  };

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this model?')) {
      try {
        await modelService.deleteModel(id);
        await fetchModels();
      } catch (err: any) {
        setError(err.message || 'Failed to delete model');
      }
    }
  };

  if (loading) return <Loading />;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Registered Models</h1>
        <button
          onClick={() => navigate('/ingest')}
          className="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded"
        >
          Ingest New Model
        </button>
      </div>

      {error && <ErrorMessage message={error} onRetry={fetchModels} />}

      {models.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-xl">No models found</p>
          <p className="mt-2">Get started by ingesting your first model</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {models.map((model) => (
            <ModelCard
              key={model.modelId}
              model={model}
              onView={handleView}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default Models;