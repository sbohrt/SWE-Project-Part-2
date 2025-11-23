import React, { useState, useEffect } from 'react';
import { modelService } from '../services/modelService';
import { HealthStatus } from '../types/model';
import Loading from '../components/Loading';
import ErrorMessage from '../components/ErrorMessage';

const Health: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await modelService.getHealth();
      setHealth(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch health status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    // Refresh every 30 seconds
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !health) return <Loading />;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">System Health</h1>
        <button
          onClick={fetchHealth}
          className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
          aria-label="Refresh health status"
        >
          Refresh
        </button>
      </div>

      {error && <ErrorMessage message={error} onRetry={fetchHealth} />}

      {health && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Status</p>
                <p className="text-2xl font-bold text-green-600">{health.status.toUpperCase()}</p>
              </div>
              <div className="text-4xl">✓</div>
            </div>
          </div>

          {health.metrics && (
            <>
              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-600 text-sm">Uploads (Last Hour)</p>
                    <p className="text-2xl font-bold text-blue-600">
                      {health.metrics.uploads_last_hour || 0}
                    </p>
                  </div>
                  <div className="text-4xl">↑</div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-600 text-sm">Errors (Last Hour)</p>
                    <p className="text-2xl font-bold text-red-600">
                      {health.metrics.errors_last_hour || 0}
                    </p>
                  </div>
                  <div className="text-4xl">⚠</div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {health?.timestamp && (
        <p className="text-gray-500 text-sm mt-4">
          Last updated: {new Date(health.timestamp).toLocaleString()}
        </p>
      )}
    </div>
  );
};

export default Health;