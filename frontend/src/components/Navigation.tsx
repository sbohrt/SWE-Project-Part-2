import React from 'react';
import { Link } from 'react-router-dom';

const Navigation: React.FC = () => {
  return (
    <nav className="bg-gray-800 text-white p-4" role="navigation" aria-label="Main navigation">
      <div className="container mx-auto flex justify-between items-center">
        <h1 className="text-2xl font-bold">
          <Link to="/" className="hover:text-gray-300">Model Registry</Link>
        </h1>
        <ul className="flex space-x-6">
          <li><Link to="/" className="hover:text-gray-300">Home</Link></li>
          <li><Link to="/models" className="hover:text-gray-300">Models</Link></li>
          <li><Link to="/ingest" className="hover:text-gray-300">Ingest</Link></li>
          <li><Link to="/lineage" className="hover:text-gray-300">Lineage</Link></li>
          <li><Link to="/health" className="hover:text-gray-300">Health</Link></li>
        </ul>
      </div>
    </nav>
  );
};

export default Navigation;