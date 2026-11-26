import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { LandingPage } from './pages/LandingPage';
import { OperationsPortal } from './pages/OperationsPortal';

export const App: React.FC = () => {
  return (
    <Routes>
      {/* Root redirect to default language TR */}
      <Route path="/" element={<Navigate to="/tr" replace />} />

      {/* Language-specific endpoints */}
      <Route path="/:lang" element={<LandingPage />} />
      <Route path="/:lang/portal" element={<OperationsPortal />} />

      {/* Fallback route */}
      <Route path="*" element={<Navigate to="/tr" replace />} />
    </Routes>
  );
};
