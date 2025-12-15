import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navigation from './components/Navigation';
import Home from './pages/Home';
import Models from './pages/Models';
import Ingest from './pages/Ingest';
import Health from './pages/Health';
import Lineage from './pages/Lineage';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100">
        {/* Skip navigation link for keyboard users */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 focus:z-50 focus:bg-blue-600 focus:text-white focus:p-4 focus:m-2"
        >
          Skip to main content
        </a>

        <Navigation />

        <main id="main-content" role="main">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/models" element={<Models />} />
            <Route path="/ingest" element={<Ingest />} />
            <Route path="/health" element={<Health />} />
            <Route path="/lineage" element={<Lineage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;