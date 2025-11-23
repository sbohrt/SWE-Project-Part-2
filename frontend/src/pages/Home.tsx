import React from 'react';
import { Link } from 'react-router-dom';

const Home: React.FC = () => {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-4xl font-bold mb-6 text-gray-800">
        Model Registry Dashboard
      </h1>
      
      <p className="text-lg text-gray-600 mb-8">
        Welcome to the ACME Model Registry - A trustworthy ML model evaluation system
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Link to="/models" className="block p-6 bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow">
          <h2 className="text-2xl font-semibold mb-2 text-blue-600">Browse Models</h2>
          <p className="text-gray-600">View and manage all registered models in the system</p>
        </Link>

        <Link to="/ingest" className="block p-6 bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow">
          <h2 className="text-2xl font-semibold mb-2 text-green-600">Ingest Model</h2>
          <p className="text-gray-600">Add new models from HuggingFace or GitHub</p>
        </Link>

        <Link to="/lineage" className="block p-6 bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow">
          <h2 className="text-2xl font-semibold mb-2 text-purple-600">Lineage Graph</h2>
          <p className="text-gray-600">Explore model parent-child relationships</p>
        </Link>

        <Link to="/health" className="block p-6 bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow">
          <h2 className="text-2xl font-semibold mb-2 text-yellow-600">System Health</h2>
          <p className="text-gray-600">Monitor system status and metrics</p>
        </Link>
      </div>
    </div>
  );
};

export default Home;