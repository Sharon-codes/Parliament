import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ErrorBoundary } from 'react-error-boundary'
import './index.css'
import App from './App.jsx'

function Fallback({ error }) {
  return (
    <div style={{ padding: 40, color: "red", fontFamily: "sans-serif" }}>
      <h1>UI Crashed</h1>
      <pre>{error.stack || error.message}</pre>
    </div>
  );
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary FallbackComponent={Fallback}>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
