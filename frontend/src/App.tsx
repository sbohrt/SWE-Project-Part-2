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
        <Navigation />
        <main>
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