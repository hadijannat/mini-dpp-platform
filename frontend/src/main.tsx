import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from 'react-oidc-context';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from '@/lib/toast';
import App from './App';
import './styles/globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

const internalKeycloakUrl = import.meta.env.VITE_KEYCLOAK_URL_INTERNAL;
const useInternalKeycloak =
  import.meta.env.VITE_USE_INTERNAL_KEYCLOAK === 'true' ||
  (import.meta.env.VITE_USE_INTERNAL_KEYCLOAK === undefined &&
    new Set(['dpp-frontend', 'frontend']).has(window.location.hostname));
const resolvedKeycloakUrl =
  internalKeycloakUrl && useInternalKeycloak
    ? internalKeycloakUrl
    : import.meta.env.VITE_KEYCLOAK_URL;

const oidcConfig = {
  authority: resolvedKeycloakUrl + '/realms/' + import.meta.env.VITE_KEYCLOAK_REALM,
  client_id: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
  redirect_uri: window.location.origin + '/callback',
  post_logout_redirect_uri: window.location.origin,
  scope: 'openid profile email',
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider {...oidcConfig}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
          <Toaster />
        </BrowserRouter>
      </QueryClientProvider>
    </AuthProvider>
  </React.StrictMode>
);
