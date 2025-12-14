import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { modelService } from '../services/modelService';
import ErrorMessage from '../components/ErrorMessage';

// Validate URL matches supported sources
const validateUrl = (url: string): { valid: boolean; error?: string } => {
  const trimmed = url.trim();
  
  // HuggingFace Model: https://huggingface.co/[org]/[model] (not datasets)
  const hfModelPattern = /^https:\/\/huggingface\.co\/(?!datasets\/)[\w.-]+\/[\w.-]+\/?$/i;
  
  // HuggingFace Dataset: https://huggingface.co/datasets/[org]/[dataset] or [dataset]
  const hfDatasetPattern = /^https:\/\/huggingface\.co\/datasets\/[\w.-]+(\/[\w.-]+)?\/?$/i;
  
  // GitHub Repository: https://github.com/[user]/[repo]
  const githubPattern = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/i;
  
  if (hfModelPattern.test(trimmed)) return { valid: true };
  if (hfDatasetPattern.test(trimmed)) return { valid: true };
  if (githubPattern.test(trimmed)) return { valid: true };
  
  return {
    valid: false,
    error: 'Invalid URL. Please enter a valid HuggingFace model/dataset or GitHub repository URL.'
  };
};

const Ingest: React.FC = () => {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!url.trim()) {
      setError('Please enter a valid URL');
      return;
    }

    // Validate URL format
    const validation = validateUrl(url);
    if (!validation.valid) {
      setError(validation.error || 'Invalid URL format');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(false);
      
      await modelService.rateModel(url);
      
      setSuccess(true);
      setUrl('');
      
      setTimeout(() => {
        navigate('/models');
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to ingest model');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Ingest New Model</h1>
      
      <div className="bg-white rounded-lg shadow-md p-6">
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label htmlFor="model-url" className="block text-gray-700 text-sm font-bold mb-2">
              Model URL
            </label>
            <input
              id="model-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://huggingface.co/model-name"
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              aria-label="Enter HuggingFace or GitHub model URL"
              required
            />
            <p className="text-gray-600 text-sm mt-2">
              Enter a HuggingFace model URL or GitHub repository URL
            </p>
          </div>

          {error && <ErrorMessage message={error} />}
          
          {success && (
            <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4" role="alert">
              Model successfully ingested! Redirecting to models list...
            </div>
          )}

          <div className="flex items-center justify-between">
            <button
              type="submit"
              disabled={loading}
              className={`bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline ${
                loading ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {loading ? 'Processing...' : 'Ingest Model'}
            </button>
            
            <button
              type="button"
              onClick={() => navigate('/models')}
              className="text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>

      <div className="mt-8 bg-blue-50 border-l-4 border-blue-500 p-4">
        <h3 className="font-bold text-blue-800 mb-2">Supported Sources:</h3>
        <ul className="list-disc list-inside text-blue-700">
          <li>HuggingFace Models: https://huggingface.co/[model-name]</li>
          <li>HuggingFace Datasets: https://huggingface.co/datasets/[dataset-name]</li>
          <li>GitHub Repositories: https://github.com/[user]/[repo]</li>
        </ul>
      </div>
    </div>
  );
};

export default Ingest;