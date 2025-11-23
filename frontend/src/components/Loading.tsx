import React from 'react';

const Loading: React.FC = () => {
  return (
    <div className="flex justify-center items-center p-8" role="status" aria-live="polite">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      <span className="sr-only">Loading...</span>
    </div>
  );
};

export default Loading;