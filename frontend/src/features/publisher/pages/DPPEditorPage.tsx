import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { ArrowLeft, Send, Download, QrCode } from 'lucide-react';
import { apiFetch } from '@/lib/api';

async function fetchDPP(dppId: string, token?: string) {
  const response = await apiFetch(`/api/v1/dpps/${dppId}`, {}, token);
  if (!response.ok) throw new Error('Failed to fetch DPP');
  return response.json();
}

async function publishDPP(dppId: string, token?: string) {
  const response = await apiFetch(`/api/v1/dpps/${dppId}/publish`, {
    method: 'POST',
  }, token);
  if (!response.ok) throw new Error('Failed to publish DPP');
  return response.json();
}

async function downloadExport(dppId: string, format: 'json' | 'aasx' | 'pdf', token?: string) {
  const response = await apiFetch(`/api/v1/export/${dppId}?format=${format}`, {}, token);
  if (!response.ok) {
    throw new Error(`Failed to export ${format.toUpperCase()}`);
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `dpp-${dppId}.${format === 'json' ? 'json' : format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

async function openQrCode(dppId: string, token?: string) {
  const response = await apiFetch(`/api/v1/qr/${dppId}?format=png`, {}, token);
  if (!response.ok) {
    throw new Error('Failed to generate QR code');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 1000);
}

export default function DPPEditorPage() {
  const { dppId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const auth = useAuth();
  const token = auth.user?.access_token;

  const { data: dpp, isLoading } = useQuery({
    queryKey: ['dpp', dppId],
    queryFn: () => fetchDPP(dppId!, token),
    enabled: !!dppId,
  });

  const publishMutation = useMutation({
    mutationFn: () => publishDPP(dppId!, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpp', dppId] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    );
  }

  if (!dpp) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">DPP not found</p>
      </div>
    );
  }

  const handleExport = async (format: 'json' | 'aasx' | 'pdf') => {
    try {
      await downloadExport(dpp.id, format, token);
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error(error);
    }
  };

  const handleQrCode = async () => {
    try {
      await openQrCode(dpp.id, token);
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error(error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/console/dpps')}
            className="text-gray-400 hover:text-gray-600"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {dpp.asset_ids?.manufacturerPartId || 'DPP Editor'}
            </h1>
            <p className="text-sm text-gray-500">ID: {dpp.id}</p>
          </div>
        </div>
        <div className="flex space-x-3">
          {dpp.status === 'published' && (
            <button
              onClick={() => { void handleQrCode(); }}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              type="button"
            >
              <QrCode className="h-4 w-4 mr-2" />
              QR Code
            </button>
          )}
          <button
            onClick={() => { void handleExport('json'); }}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export JSON
          </button>
          <button
            onClick={() => { void handleExport('pdf'); }}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export PDF
          </button>
          <button
            onClick={() => { void handleExport('aasx'); }}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export AASX
          </button>
          {dpp.status === 'draft' && (
            <button
              onClick={() => publishMutation.mutate()}
              disabled={publishMutation.isPending}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50"
            >
              <Send className="h-4 w-4 mr-2" />
              {publishMutation.isPending ? 'Publishing...' : 'Publish'}
            </button>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Status</h2>
            <span className={`mt-2 inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              dpp.status === 'published'
                ? 'bg-green-100 text-green-800'
                : dpp.status === 'archived'
                ? 'bg-gray-100 text-gray-800'
                : 'bg-yellow-100 text-yellow-800'
            }`}>
              {dpp.status}
            </span>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">Revision</p>
            <p className="text-lg font-medium text-gray-900">
              #{dpp.current_revision_no || 1}
            </p>
          </div>
        </div>
      </div>

      {/* Asset Information */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Asset Information</h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Object.entries(dpp.asset_ids || {}).map(([key, value]) => (
            <div key={key}>
              <dt className="text-sm font-medium text-gray-500">{key}</dt>
              <dd className="mt-1 text-sm text-gray-900">{String(value)}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Submodels */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Submodels</h2>
        <div className="space-y-4">
          {(dpp.aas_environment?.submodels || []).map((submodel: any, index: number) => (
            <div key={index} className="border rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium text-gray-900">{submodel.idShort}</h3>
                  <p className="text-sm text-gray-500">{submodel.id}</p>
                </div>
              </div>
              {submodel.submodelElements && (
                <div className="mt-4 space-y-2">
                  {submodel.submodelElements.map((element: any, idx: number) => (
                    <div key={idx} className="flex justify-between text-sm border-b pb-2">
                      <span className="text-gray-600">{element.idShort}</span>
                      <span className="text-gray-900">{element.value || '-'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Integrity */}
      {dpp.digest_sha256 && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Integrity</h2>
          <div>
            <dt className="text-sm font-medium text-gray-500">SHA-256 Digest</dt>
            <dd className="mt-1 text-xs font-mono text-gray-900 break-all bg-gray-50 p-2 rounded">
              {dpp.digest_sha256}
            </dd>
          </div>
        </div>
      )}
    </div>
  );
}
