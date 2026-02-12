import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  AlertCircle,
  CheckCircle,
  FolderOpen,
  History,
  Link2,
  Play,
  Plus,
  RefreshCcw,
  Send,
  ShieldCheck,
  TestTube,
  XCircle,
} from 'lucide-react';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { EmptyState } from '@/components/empty-state';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const WIZARD_STEPS = [
  'Participant',
  'Trust & Secrets',
  'Runtime',
  'Policies',
  'Conformance',
  'Activate',
] as const;

interface DPPSummary {
  id: string;
  status: string;
  asset_ids?: { manufacturerPartId?: string };
}

interface DataspaceConnector {
  id: string;
  name: string;
  runtime: string;
  participant_id: string;
  display_name?: string | null;
  status: string;
  runtime_config: Record<string, unknown>;
  secret_refs: string[];
  last_validated_at?: string | null;
  created_at: string;
}

interface DataspaceAssetPublication {
  id: string;
  status: string;
  dpp_id: string;
  connector_id: string;
  asset_id: string;
  access_policy_id?: string | null;
  usage_policy_id?: string | null;
  contract_definition_id?: string | null;
  created_at: string;
  updated_at: string;
}

interface DataspaceNegotiation {
  id: string;
  connector_id: string;
  publication_id?: string | null;
  negotiation_id: string;
  state: string;
  contract_agreement_id?: string | null;
  created_at: string;
  updated_at: string;
}

interface DataspaceTransfer {
  id: string;
  connector_id: string;
  negotiation_id?: string | null;
  transfer_id: string;
  state: string;
  data_destination?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

interface DataspaceConformanceRun {
  id: string;
  connector_id?: string | null;
  run_type: string;
  status: string;
  request_payload: Record<string, unknown>;
  result_payload?: Record<string, unknown> | null;
  artifact_url?: string | null;
  created_at: string;
  updated_at: string;
}

interface CatalogEntry {
  id: string;
  title?: string | null;
  description?: string | null;
  asset_id?: string | null;
}

interface CatalogQueryResponse {
  status: string;
  entries: CatalogEntry[];
  raw?: Record<string, unknown>;
  error_message?: string | null;
}

interface RegulatoryEvidence {
  dpp_id: string;
  profile: string;
  generated_at: string;
  compliance_reports: Array<Record<string, unknown>>;
  credential_status: {
    exists: boolean;
    revoked?: boolean | null;
  };
  resolver_links: Array<Record<string, unknown>>;
  shell_descriptors: Array<Record<string, unknown>>;
  dataspace_publications: Array<Record<string, unknown>>;
  dataspace_negotiations: Array<Record<string, unknown>>;
  dataspace_transfers: Array<Record<string, unknown>>;
  dataspace_conformance_runs: Array<Record<string, unknown>>;
}

interface PolicyTemplateRecord {
  id: string;
  name: string;
  version: string;
  state: 'draft' | 'approved' | 'active' | 'superseded';
  policy: Record<string, unknown>;
  description?: string | null;
}

interface ManifestChange {
  resource: string;
  action: 'create' | 'update' | 'noop';
  field?: string | null;
  old_value?: unknown;
  new_value?: unknown;
}

interface ConnectorManifestPayload {
  connector: {
    name: string;
    runtime: 'edc' | 'catena_x_dtr';
    participant_id: string;
    display_name?: string;
    runtime_config: Record<string, unknown>;
    secrets: Array<{ secret_ref: string; value: string }>;
  };
  policy_templates: Array<{
    name: string;
    version: string;
    state: 'draft' | 'approved' | 'active' | 'superseded';
    policy: Record<string, unknown>;
    description?: string;
  }>;
}

interface WizardState {
  name: string;
  participantId: string;
  displayName: string;
  managementApiKeySecretRef: string;
  managementApiKeyValue: string;
  managementUrl: string;
  dspEndpoint: string;
  providerConnectorAddress: string;
  publicApiBaseUrl: string;
  allowedBpnsText: string;
  autoValidate: boolean;
}

const WIZARD_INITIAL_STATE: WizardState = {
  name: '',
  participantId: '',
  displayName: '',
  managementApiKeySecretRef: 'edc-mgmt-api-key',
  managementApiKeyValue: '',
  managementUrl: '',
  dspEndpoint: '',
  providerConnectorAddress: '',
  publicApiBaseUrl: '',
  allowedBpnsText: '',
  autoValidate: true,
};

function getConfigString(config: Record<string, unknown>, key: string): string | null {
  const value = config[key];
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

async function fetchDataspaceConnectors(token?: string) {
  const response = await tenantApiFetch('/dataspace/connectors', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch dataspace connectors'));
  }
  return response.json() as Promise<{ connectors: DataspaceConnector[]; count: number }>;
}

async function createDataspaceConnector(payload: Record<string, unknown>, token?: string) {
  const response = await tenantApiFetch(
    '/dataspace/connectors',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to create dataspace connector'));
  }
  return response.json() as Promise<DataspaceConnector>;
}

async function validateDataspaceConnector(connectorId: string, token?: string) {
  const response = await tenantApiFetch(
    `/dataspace/connectors/${connectorId}/validate`,
    { method: 'POST' },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to validate connector'));
  }
  return response.json() as Promise<{ status: string }>;
}

async function publishDataspaceAsset(connectorId: string, dppId: string, token?: string) {
  const response = await tenantApiFetch(
    '/dataspace/assets/publish',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connector_id: connectorId,
        dpp_id: dppId,
      }),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to publish to dataspace'));
  }
  return response.json();
}

async function fetchPublishedDPPs(token?: string) {
  const response = await tenantApiFetch('/dpps?status=published&limit=200', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load DPPs'));
  }
  return response.json() as Promise<{ dpps: DPPSummary[] }>;
}

async function fetchConnectorAssets(connectorId: string, token?: string) {
  const response = await tenantApiFetch(`/dataspace/connectors/${connectorId}/assets`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch published assets'));
  }
  return response.json() as Promise<{ items: DataspaceAssetPublication[]; count: number }>;
}

async function fetchConnectorNegotiations(connectorId: string, token?: string) {
  const response = await tenantApiFetch(
    `/dataspace/connectors/${connectorId}/negotiations`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch negotiations'));
  }
  return response.json() as Promise<{ items: DataspaceNegotiation[]; count: number }>;
}

async function fetchConnectorTransfers(connectorId: string, token?: string) {
  const response = await tenantApiFetch(`/dataspace/connectors/${connectorId}/transfers`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch transfers'));
  }
  return response.json() as Promise<{ items: DataspaceTransfer[]; count: number }>;
}

async function fetchConnectorConformanceRuns(connectorId: string, token?: string) {
  const response = await tenantApiFetch(
    `/dataspace/connectors/${connectorId}/conformance-runs`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch conformance runs'));
  }
  return response.json() as Promise<{ items: DataspaceConformanceRun[]; count: number }>;
}

async function queryCatalog(
  payload: {
    connector_id: string;
    connector_address: string;
    protocol: string;
    query_spec: Record<string, unknown>;
  },
  token?: string,
) {
  const response = await tenantApiFetch(
    '/dataspace/catalog/query',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to query catalog'));
  }
  return response.json() as Promise<CatalogQueryResponse>;
}

async function refreshNegotiation(negotiationId: string, token?: string) {
  const response = await tenantApiFetch(`/dataspace/negotiations/${negotiationId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to refresh negotiation'));
  }
  return response.json() as Promise<DataspaceNegotiation>;
}

async function refreshTransfer(transferId: string, token?: string) {
  const response = await tenantApiFetch(`/dataspace/transfers/${transferId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to refresh transfer'));
  }
  return response.json() as Promise<DataspaceTransfer>;
}

async function startConformanceRun(connectorId: string, token?: string) {
  const response = await tenantApiFetch(
    '/dataspace/conformance/dsp-tck/runs',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connector_id: connectorId,
        profile: 'dsp-tck',
        metadata: {},
      }),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to start conformance run'));
  }
  return response.json() as Promise<DataspaceConformanceRun>;
}

async function fetchRegulatoryEvidence(dppId: string, profile: string, token?: string) {
  const response = await tenantApiFetch(
    `/dataspace/evidence/dpps/${dppId}?profile=${encodeURIComponent(profile)}`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load evidence'));
  }
  return response.json() as Promise<RegulatoryEvidence>;
}

async function fetchPolicyTemplates(token?: string) {
  const response = await tenantApiFetch('/dataspace/policy-templates', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch policy templates'));
  }
  return response.json() as Promise<{ templates: PolicyTemplateRecord[]; count: number }>;
}

async function diffManifest(payload: ConnectorManifestPayload, token?: string) {
  const response = await tenantApiFetch(
    '/dataspace/manifests:diff',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to preview manifest'));
  }
  return response.json() as Promise<{ has_changes: boolean; changes: ManifestChange[] }>;
}

async function applyManifest(payload: ConnectorManifestPayload, token?: string) {
  const response = await tenantApiFetch(
    '/dataspace/manifests:apply',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to apply manifest'));
  }
  return response.json() as Promise<{
    status: 'applied' | 'noop';
    connector_id: string;
    applied_changes: ManifestChange[];
  }>;
}

export default function ConnectorsPage() {
  const queryClient = useQueryClient();
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();

  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [wizard, setWizard] = useState<WizardState>(WIZARD_INITIAL_STATE);

  const [publishConnectorId, setPublishConnectorId] = useState<string | null>(null);
  const [selectedDppId, setSelectedDppId] = useState('');
  const [selectedConnectorId, setSelectedConnectorId] = useState<string | null>(null);
  const [catalogAddress, setCatalogAddress] = useState('');
  const [catalogQuerySpec, setCatalogQuerySpec] = useState('{"offset":0,"limit":20}');
  const [catalogJsonError, setCatalogJsonError] = useState<string | null>(null);
  const [evidenceDppId, setEvidenceDppId] = useState('');
  const [evidenceProfile, setEvidenceProfile] = useState('espr_core');
  const [showManifestDialog, setShowManifestDialog] = useState(false);
  const [manifestText, setManifestText] = useState('');
  const [manifestJsonError, setManifestJsonError] = useState<string | null>(null);

  const { data: connectorData, isLoading, isError, error } = useQuery({
    queryKey: ['dataspace-connectors', tenantSlug],
    queryFn: () => fetchDataspaceConnectors(token),
    enabled: Boolean(token),
  });

  const connectors = useMemo(
    () => connectorData?.connectors ?? [],
    [connectorData?.connectors],
  );

  useEffect(() => {
    if (selectedConnectorId && connectors.some((item) => item.id === selectedConnectorId)) {
      return;
    }
    const firstConnector = connectorData?.connectors?.[0];
    if (firstConnector) {
      setSelectedConnectorId(firstConnector.id);
      return;
    }
    setSelectedConnectorId(null);
  }, [connectorData?.connectors, connectors, selectedConnectorId]);

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => createDataspaceConnector(payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dataspace-connectors', tenantSlug] });
    },
  });

  const validateMutation = useMutation({
    mutationFn: (connectorId: string) => validateDataspaceConnector(connectorId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dataspace-connectors', tenantSlug] });
    },
  });

  const publishMutation = useMutation({
    mutationFn: ({ connectorId, dppId }: { connectorId: string; dppId: string }) =>
      publishDataspaceAsset(connectorId, dppId, token),
    onSuccess: (_data, variables) => {
      setPublishConnectorId(null);
      setSelectedDppId('');
      queryClient.invalidateQueries({
        queryKey: ['dataspace-connector-assets', tenantSlug, variables.connectorId],
      });
    },
  });

  const { data: publishedDppsData } = useQuery({
    queryKey: ['published-dpps-connectors', tenantSlug],
    queryFn: () => fetchPublishedDPPs(token),
    enabled: Boolean(token) && (publishConnectorId !== null || selectedConnectorId !== null),
  });

  const selectedConnector = useMemo(
    () => connectors.find((connector) => connector.id === selectedConnectorId) ?? null,
    [connectors, selectedConnectorId],
  );

  useEffect(() => {
    if (!selectedConnector) {
      setCatalogAddress('');
      return;
    }
    setCatalogAddress(getConfigString(selectedConnector.runtime_config, 'provider_connector_address') ?? '');
  }, [selectedConnector]);

  const connectorAssetsQuery = useQuery({
    queryKey: ['dataspace-connector-assets', tenantSlug, selectedConnectorId],
    queryFn: () => fetchConnectorAssets(selectedConnectorId!, token),
    enabled: Boolean(token) && Boolean(selectedConnectorId),
  });

  const connectorNegotiationsQuery = useQuery({
    queryKey: ['dataspace-connector-negotiations', tenantSlug, selectedConnectorId],
    queryFn: () => fetchConnectorNegotiations(selectedConnectorId!, token),
    enabled: Boolean(token) && Boolean(selectedConnectorId),
  });

  const connectorTransfersQuery = useQuery({
    queryKey: ['dataspace-connector-transfers', tenantSlug, selectedConnectorId],
    queryFn: () => fetchConnectorTransfers(selectedConnectorId!, token),
    enabled: Boolean(token) && Boolean(selectedConnectorId),
  });

  const connectorConformanceQuery = useQuery({
    queryKey: ['dataspace-connector-conformance', tenantSlug, selectedConnectorId],
    queryFn: () => fetchConnectorConformanceRuns(selectedConnectorId!, token),
    enabled: Boolean(token) && Boolean(selectedConnectorId),
  });

  const catalogMutation = useMutation({
    mutationFn: (payload: {
      connector_id: string;
      connector_address: string;
      protocol: string;
      query_spec: Record<string, unknown>;
    }) => queryCatalog(payload, token),
  });

  const refreshNegotiationMutation = useMutation({
    mutationFn: (negotiationId: string) => refreshNegotiation(negotiationId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['dataspace-connector-negotiations', tenantSlug, selectedConnectorId],
      });
    },
  });

  const refreshTransferMutation = useMutation({
    mutationFn: (transferId: string) => refreshTransfer(transferId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['dataspace-connector-transfers', tenantSlug, selectedConnectorId],
      });
    },
  });

  const conformanceMutation = useMutation({
    mutationFn: (connectorId: string) => startConformanceRun(connectorId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['dataspace-connector-conformance', tenantSlug, selectedConnectorId],
      });
    },
  });

  const evidenceMutation = useMutation({
    mutationFn: ({ dppId, profile }: { dppId: string; profile: string }) =>
      fetchRegulatoryEvidence(dppId, profile, token),
  });

  const policyTemplatesQuery = useQuery({
    queryKey: ['dataspace-policy-templates', tenantSlug],
    queryFn: () => fetchPolicyTemplates(token),
    enabled: Boolean(token) && Boolean(selectedConnectorId),
  });

  const manifestDiffMutation = useMutation({
    mutationFn: (payload: ConnectorManifestPayload) => diffManifest(payload, token),
  });

  const manifestApplyMutation = useMutation({
    mutationFn: (payload: ConnectorManifestPayload) => applyManifest(payload, token),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dataspace-connectors', tenantSlug] }),
        queryClient.invalidateQueries({
          queryKey: ['dataspace-policy-templates', tenantSlug],
        }),
      ]);
    },
  });

  const pageError =
    (evidenceMutation.error as Error | undefined) ??
    (conformanceMutation.error as Error | undefined) ??
    (refreshTransferMutation.error as Error | undefined) ??
    (refreshNegotiationMutation.error as Error | undefined) ??
    (catalogMutation.error as Error | undefined) ??
    (publishMutation.error as Error | undefined) ??
    (validateMutation.error as Error | undefined) ??
    (createMutation.error as Error | undefined) ??
    (connectorAssetsQuery.error as Error | undefined) ??
    (connectorNegotiationsQuery.error as Error | undefined) ??
    (connectorTransfersQuery.error as Error | undefined) ??
    (connectorConformanceQuery.error as Error | undefined) ??
    (policyTemplatesQuery.error as Error | undefined) ??
    (manifestDiffMutation.error as Error | undefined) ??
    (manifestApplyMutation.error as Error | undefined) ??
    (isError ? (error as Error) : undefined);
  const sessionExpired = Boolean(pageError?.message?.includes('Session expired'));

  const parsedAllowedBpns = useMemo(
    () =>
      wizard.allowedBpnsText
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean),
    [wizard.allowedBpnsText],
  );
  const connectorAssets = connectorAssetsQuery.data?.items ?? [];
  const connectorNegotiations = connectorNegotiationsQuery.data?.items ?? [];
  const connectorTransfers = connectorTransfersQuery.data?.items ?? [];
  const connectorConformanceRuns = connectorConformanceQuery.data?.items ?? [];
  const catalogEntries = catalogMutation.data?.entries ?? [];
  const policyTemplates = policyTemplatesQuery.data?.templates ?? [];

  const canAdvanceWizard = useMemo(() => {
    if (wizardStep === 0) {
      return wizard.name.trim().length > 0 && wizard.participantId.trim().length > 0;
    }
    if (wizardStep === 1) {
      return (
        wizard.managementApiKeySecretRef.trim().length > 0 &&
        wizard.managementApiKeyValue.trim().length > 0
      );
    }
    if (wizardStep === 2) {
      return wizard.managementUrl.trim().length > 0;
    }
    return true;
  }, [
    wizard.managementApiKeySecretRef,
    wizard.managementApiKeyValue,
    wizard.managementUrl,
    wizard.name,
    wizard.participantId,
    wizardStep,
  ]);

  const resetWizard = () => {
    setWizard(WIZARD_INITIAL_STATE);
    setWizardStep(0);
  };

  const openWizard = () => {
    resetWizard();
    setShowWizard(true);
  };

  const closeWizard = () => {
    resetWizard();
    setShowWizard(false);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    }
  };

  const handleCreateConnector = async () => {
    const payload = {
      name: wizard.name.trim(),
      runtime: 'edc',
      participant_id: wizard.participantId.trim(),
      display_name: wizard.displayName.trim() || undefined,
      runtime_config: {
        management_url: wizard.managementUrl.trim(),
        dsp_endpoint: wizard.dspEndpoint.trim() || undefined,
        provider_connector_address: wizard.providerConnectorAddress.trim() || undefined,
        management_api_key_secret_ref: wizard.managementApiKeySecretRef.trim(),
        public_api_base_url: wizard.publicApiBaseUrl.trim() || undefined,
        allowed_bpns: parsedAllowedBpns,
        protocol: 'dataspace-protocol-http',
      },
      secrets: [
        {
          secret_ref: wizard.managementApiKeySecretRef.trim(),
          value: wizard.managementApiKeyValue,
        },
      ],
    };

    const created = await createMutation.mutateAsync(payload);
    setSelectedConnectorId(created.id);
    if (wizard.autoValidate) {
      await validateMutation.mutateAsync(created.id);
    }
    closeWizard();
  };

  const handleCatalogQuery = async () => {
    if (!selectedConnector) {
      return;
    }
    if (!catalogAddress.trim()) {
      setCatalogJsonError('Connector address is required for catalog queries.');
      return;
    }
    let querySpecPayload: Record<string, unknown> = {};
    try {
      querySpecPayload = catalogQuerySpec.trim()
        ? (JSON.parse(catalogQuerySpec) as Record<string, unknown>)
        : {};
      setCatalogJsonError(null);
    } catch {
      setCatalogJsonError('Query spec must be valid JSON.');
      return;
    }

    await catalogMutation.mutateAsync({
      connector_id: selectedConnector.id,
      connector_address: catalogAddress.trim(),
      protocol: 'dataspace-protocol-http',
      query_spec: querySpecPayload,
    });
  };

  const buildConnectorManifest = (): ConnectorManifestPayload | null => {
    if (!selectedConnector) {
      return null;
    }
    return {
      connector: {
        name: selectedConnector.name,
        runtime:
          selectedConnector.runtime === 'catena_x_dtr'
            ? 'catena_x_dtr'
            : 'edc',
        participant_id: selectedConnector.participant_id,
        display_name: selectedConnector.display_name ?? undefined,
        runtime_config: selectedConnector.runtime_config,
        secrets: selectedConnector.secret_refs.map((secretRef) => ({
          secret_ref: secretRef,
          value: 'REDACTED_CHANGE_ME',
        })),
      },
      policy_templates: policyTemplates.map((template) => ({
        name: template.name,
        version: template.version,
        state: template.state,
        policy: template.policy,
        description: template.description ?? undefined,
      })),
    };
  };

  const handleExportManifest = () => {
    const manifest = buildConnectorManifest();
    if (!manifest || !selectedConnector) {
      return;
    }

    const payload = JSON.stringify(manifest, null, 2);
    setManifestText(payload);
    const blob = new Blob([payload], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${selectedConnector.name}-dataspace-manifest.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const parseManifestInput = (): ConnectorManifestPayload | null => {
    try {
      const parsed = JSON.parse(manifestText) as ConnectorManifestPayload;
      setManifestJsonError(null);
      return parsed;
    } catch {
      setManifestJsonError('Manifest must be valid JSON.');
      return null;
    }
  };

  const handlePreviewManifest = async () => {
    const parsed = parseManifestInput();
    if (!parsed) {
      return;
    }
    await manifestDiffMutation.mutateAsync(parsed);
  };

  const handleApplyManifest = async () => {
    const parsed = parseManifestInput();
    if (!parsed) {
      return;
    }
    const result = await manifestApplyMutation.mutateAsync(parsed);
    setSelectedConnectorId(result.connector_id);
    setShowManifestDialog(false);
  };

  const renderWizardStep = () => {
    if (wizardStep === 0) {
      return (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wizard-name">Connector Name</Label>
            <Input
              id="wizard-name"
              value={wizard.name}
              onChange={(event) => setWizard((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="supplier-edc-eu-west"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wizard-participant">Participant ID (BPN)</Label>
            <Input
              id="wizard-participant"
              value={wizard.participantId}
              onChange={(event) =>
                setWizard((prev) => ({ ...prev, participantId: event.target.value }))
              }
              placeholder="BPNL000000000001"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wizard-display-name">Display Name (optional)</Label>
            <Input
              id="wizard-display-name"
              value={wizard.displayName}
              onChange={(event) =>
                setWizard((prev) => ({ ...prev, displayName: event.target.value }))
              }
              placeholder="EU Primary Connector"
            />
          </div>
        </div>
      );
    }

    if (wizardStep === 1) {
      return (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wizard-secret-ref">Management API Key Secret Ref</Label>
            <Input
              id="wizard-secret-ref"
              value={wizard.managementApiKeySecretRef}
              onChange={(event) =>
                setWizard((prev) => ({
                  ...prev,
                  managementApiKeySecretRef: event.target.value,
                }))
              }
              placeholder="edc-mgmt-api-key"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wizard-secret-value">Management API Key Value</Label>
            <Input
              id="wizard-secret-value"
              type="password"
              value={wizard.managementApiKeyValue}
              onChange={(event) =>
                setWizard((prev) => ({
                  ...prev,
                  managementApiKeyValue: event.target.value,
                }))
              }
              placeholder="Paste EDC management API key"
            />
          </div>
        </div>
      );
    }

    if (wizardStep === 2) {
      return (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wizard-management-url">Management URL</Label>
            <Input
              id="wizard-management-url"
              value={wizard.managementUrl}
              onChange={(event) =>
                setWizard((prev) => ({ ...prev, managementUrl: event.target.value }))
              }
              placeholder="http://edc-controlplane:19193/management"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wizard-dsp-endpoint">DSP Endpoint (optional)</Label>
            <Input
              id="wizard-dsp-endpoint"
              value={wizard.dspEndpoint}
              onChange={(event) =>
                setWizard((prev) => ({ ...prev, dspEndpoint: event.target.value }))
              }
              placeholder="http://edc-controlplane:19194/protocol"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wizard-provider-address">Provider Connector Address (optional)</Label>
            <Input
              id="wizard-provider-address"
              value={wizard.providerConnectorAddress}
              onChange={(event) =>
                setWizard((prev) => ({
                  ...prev,
                  providerConnectorAddress: event.target.value,
                }))
              }
              placeholder="http://provider-controlplane:19193/management"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wizard-public-api">Public DPP API Base URL (optional)</Label>
            <Input
              id="wizard-public-api"
              value={wizard.publicApiBaseUrl}
              onChange={(event) =>
                setWizard((prev) => ({ ...prev, publicApiBaseUrl: event.target.value }))
              }
              placeholder="https://dpp-platform.dev/api/v1/public"
            />
          </div>
        </div>
      );
    }

    if (wizardStep === 3) {
      return (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wizard-allowed-bpns">Allowed BPNs (comma separated)</Label>
            <Textarea
              id="wizard-allowed-bpns"
              value={wizard.allowedBpnsText}
              onChange={(event) =>
                setWizard((prev) => ({ ...prev, allowedBpnsText: event.target.value }))
              }
              placeholder="BPNL000000000001, BPNL000000000002"
            />
          </div>
        </div>
      );
    }

    if (wizardStep === 4) {
      return (
        <div className="space-y-4">
          <div className="rounded-lg border p-4 space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="wizard-auto-validate">Run validation on activation</Label>
              <Switch
                id="wizard-auto-validate"
                checked={wizard.autoValidate}
                onCheckedChange={(checked) =>
                  setWizard((prev) => ({ ...prev, autoValidate: checked }))
                }
              />
            </div>
            <p className="text-sm text-muted-foreground">
              Executes connector health validation immediately after provisioning.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-4 text-sm">
        <div className="rounded-lg border p-4 space-y-2">
          <p><strong>Name:</strong> {wizard.name}</p>
          <p><strong>Participant:</strong> {wizard.participantId}</p>
          <p><strong>Management URL:</strong> {wizard.managementUrl}</p>
          <p><strong>DSP Endpoint:</strong> {wizard.dspEndpoint || 'Not set'}</p>
          <p><strong>Secret Ref:</strong> {wizard.managementApiKeySecretRef}</p>
          <p><strong>Allowed BPNs:</strong> {parsedAllowedBpns.join(', ') || 'Any'}</p>
          <p><strong>Auto Validate:</strong> {wizard.autoValidate ? 'Enabled' : 'Disabled'}</p>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dataspace Connectors"
        description="Provision and operate DSP/EDC connector instances"
        actions={
          <Button onClick={openWizard}>
            <Plus className="h-4 w-4 mr-2" />
            New Dataspace Connector
          </Button>
        }
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Something went wrong.'}
          showSignIn={sessionExpired}
          onSignIn={() => {
            void auth.signinRedirect();
          }}
        />
      )}

      <Dialog open={showWizard} onOpenChange={(open) => (!open ? closeWizard() : setShowWizard(true))}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Dataspace Connector</DialogTitle>
          </DialogHeader>

          <div className="grid grid-cols-6 gap-2">
            {WIZARD_STEPS.map((step, index) => (
              <button
                key={step}
                type="button"
                className={`rounded border px-2 py-1 text-xs ${
                  index === wizardStep ? 'bg-primary text-primary-foreground' : 'bg-background'
                }`}
                onClick={() => setWizardStep(index)}
              >
                {index + 1}. {step}
              </button>
            ))}
          </div>

          {renderWizardStep()}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={closeWizard}
              disabled={createMutation.isPending || validateMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={() => setWizardStep((value) => Math.max(0, value - 1))}
              disabled={wizardStep === 0}
            >
              Back
            </Button>
            {wizardStep < WIZARD_STEPS.length - 1 ? (
              <Button
                onClick={() => setWizardStep((value) => Math.min(WIZARD_STEPS.length - 1, value + 1))}
                disabled={!canAdvanceWizard}
              >
                Next
              </Button>
            ) : (
              <Button
                onClick={() => {
                  void handleCreateConnector();
                }}
                disabled={createMutation.isPending || validateMutation.isPending || !canAdvanceWizard}
              >
                {createMutation.isPending || validateMutation.isPending
                  ? 'Provisioning...'
                  : 'Create Connector'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Runtime</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Participant</TableHead>
                  <TableHead>Last Validated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {connectors.map((connector) => (
                  <TableRow
                    key={connector.id}
                    className={
                      connector.id === selectedConnectorId ? 'bg-muted/40 transition-colors' : ''
                    }
                  >
                    <TableCell className="font-medium">{connector.name}</TableCell>
                    <TableCell className="text-muted-foreground">{connector.runtime}</TableCell>
                    <TableCell>
                      <div className="flex items-center">
                        {getStatusIcon(connector.status)}
                        <span className="ml-2">{connector.status}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{connector.participant_id}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {connector.last_validated_at
                        ? new Date(connector.last_validated_at).toLocaleString()
                        : 'Never'}
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedConnectorId(connector.id)}
                      >
                        <FolderOpen className="h-4 w-4 mr-1" />
                        Open
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => validateMutation.mutate(connector.id)}
                        disabled={validateMutation.isPending}
                      >
                        <TestTube className="h-4 w-4 mr-1" />
                        Validate
                      </Button>
                      <Button variant="ghost" size="sm" asChild>
                        <Link to={`/console/activity?type=dataspace_connector&id=${connector.id}`}>
                          <History className="h-4 w-4 mr-1" />
                          Activity
                        </Link>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setPublishConnectorId(connector.id)}
                      >
                        <Send className="h-4 w-4 mr-1" />
                        Publish
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {connectors.length === 0 && (
              <EmptyState
                icon={Link2}
                title="No dataspace connectors configured"
                description="Create a connector to publish DPP assets into your dataspace."
              />
            )}
          </Card>

          {selectedConnector && (
            <Card className="p-4">
              <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-lg font-semibold">{selectedConnector.name}</h2>
                  <p className="text-sm text-muted-foreground">
                    Participant {selectedConnector.participant_id} · Runtime {selectedConnector.runtime}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={handleExportManifest}>
                    Export Manifest
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      const manifest = buildConnectorManifest();
                      if (manifest) {
                        setManifestText(JSON.stringify(manifest, null, 2));
                        setManifestJsonError(null);
                        manifestDiffMutation.reset();
                      }
                      setShowManifestDialog(true);
                    }}
                  >
                    Import/Apply Manifest
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => validateMutation.mutate(selectedConnector.id)}
                    disabled={validateMutation.isPending}
                  >
                    <TestTube className="h-4 w-4 mr-2" />
                    Validate
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => conformanceMutation.mutate(selectedConnector.id)}
                    disabled={conformanceMutation.isPending}
                  >
                    <ShieldCheck className="h-4 w-4 mr-2" />
                    {conformanceMutation.isPending ? 'Running TCK...' : 'Run DSP TCK'}
                  </Button>
                </div>
              </div>

              <Tabs defaultValue="health">
                <TabsList className="w-full flex-wrap h-auto gap-1 justify-start">
                  <TabsTrigger value="health">Health</TabsTrigger>
                  <TabsTrigger value="assets">Published Assets</TabsTrigger>
                  <TabsTrigger value="catalog">Catalog</TabsTrigger>
                  <TabsTrigger value="negotiations">Negotiations</TabsTrigger>
                  <TabsTrigger value="transfers">Transfers</TabsTrigger>
                  <TabsTrigger value="conformance">Conformance</TabsTrigger>
                  <TabsTrigger value="evidence">Evidence</TabsTrigger>
                </TabsList>

                <TabsContent value="health" className="space-y-3">
                  {selectedConnector.runtime === 'catena_x_dtr' ? (
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">DTR Base URL</p>
                        <p className="text-sm break-all">
                          {getConfigString(selectedConnector.runtime_config, 'dtr_base_url') ??
                            'Not configured'}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">Submodel Base URL</p>
                        <p className="text-sm break-all">
                          {getConfigString(selectedConnector.runtime_config, 'submodel_base_url') ??
                            'Not configured'}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">Auth Type</p>
                        <p className="text-sm break-all">
                          {getConfigString(selectedConnector.runtime_config, 'auth_type') ??
                            'Not configured'}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">EDC DSP Endpoint</p>
                        <p className="text-sm break-all">
                          {getConfigString(selectedConnector.runtime_config, 'edc_dsp_endpoint') ??
                            'Not configured'}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3 md:col-span-2">
                        <p className="text-xs text-muted-foreground mb-1">Secret Refs</p>
                        <p className="text-sm break-all">
                          {selectedConnector.secret_refs.join(', ') || 'None'}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">Management URL</p>
                        <p className="text-sm break-all">
                          {getConfigString(selectedConnector.runtime_config, 'management_url') ??
                            'Not configured'}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">DSP Endpoint</p>
                        <p className="text-sm break-all">
                          {getConfigString(selectedConnector.runtime_config, 'dsp_endpoint') ??
                            'Not configured'}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">Provider Connector Address</p>
                        <p className="text-sm break-all">
                          {getConfigString(
                            selectedConnector.runtime_config,
                            'provider_connector_address',
                          ) ?? 'Not configured'}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">Secret Refs</p>
                        <p className="text-sm break-all">
                          {selectedConnector.secret_refs.join(', ') || 'None'}
                        </p>
                      </div>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="assets" className="space-y-3">
                  {connectorAssetsQuery.isLoading ? (
                    <LoadingSpinner />
                  ) : connectorAssets.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No published assets found for this connector.
                    </p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Asset ID</TableHead>
                          <TableHead>DPP</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Updated</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {connectorAssets.map((asset) => (
                          <TableRow key={asset.id}>
                            <TableCell className="font-medium">{asset.asset_id}</TableCell>
                            <TableCell className="text-muted-foreground">{asset.dpp_id}</TableCell>
                            <TableCell>{asset.status}</TableCell>
                            <TableCell className="text-muted-foreground">
                              {new Date(asset.updated_at).toLocaleString()}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </TabsContent>

                <TabsContent value="catalog" className="space-y-3">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="catalog-address">Remote Connector Address</Label>
                      <Input
                        id="catalog-address"
                        value={catalogAddress}
                        onChange={(event) => setCatalogAddress(event.target.value)}
                        placeholder="http://provider-controlplane:19193/management"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="catalog-query">Query Spec (JSON)</Label>
                      <Textarea
                        id="catalog-query"
                        value={catalogQuerySpec}
                        onChange={(event) => setCatalogQuerySpec(event.target.value)}
                        className="min-h-[96px]"
                      />
                    </div>
                  </div>
                  {catalogJsonError && <p className="text-sm text-red-600">{catalogJsonError}</p>}
                  <Button onClick={() => void handleCatalogQuery()} disabled={catalogMutation.isPending}>
                    <Play className="h-4 w-4 mr-2" />
                    {catalogMutation.isPending ? 'Querying...' : 'Query Catalog'}
                  </Button>
                  {catalogMutation.data && (
                    <div className="space-y-3">
                      {catalogMutation.data.status !== 'ok' && (
                        <p className="text-sm text-red-600">
                          {catalogMutation.data.error_message || 'Catalog query failed'}
                        </p>
                      )}
                      {catalogMutation.data.status === 'ok' && catalogEntries.length === 0 && (
                        <p className="text-sm text-muted-foreground">No catalog entries returned.</p>
                      )}
                      {catalogEntries.length > 0 && (
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Entry</TableHead>
                              <TableHead>Title</TableHead>
                              <TableHead>Asset</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {catalogEntries.map((entry) => (
                              <TableRow key={entry.id}>
                                <TableCell className="font-medium">{entry.id}</TableCell>
                                <TableCell>{entry.title || 'Untitled'}</TableCell>
                                <TableCell>{entry.asset_id || '-'}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      )}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="negotiations" className="space-y-3">
                  {connectorNegotiationsQuery.isLoading ? (
                    <LoadingSpinner />
                  ) : connectorNegotiations.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No negotiations found.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Negotiation ID</TableHead>
                          <TableHead>State</TableHead>
                          <TableHead>Agreement</TableHead>
                          <TableHead>Updated</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {connectorNegotiations.map((negotiation) => (
                          <TableRow key={negotiation.id}>
                            <TableCell className="font-medium">{negotiation.negotiation_id}</TableCell>
                            <TableCell>{negotiation.state}</TableCell>
                            <TableCell className="text-muted-foreground">
                              {negotiation.contract_agreement_id || '-'}
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {new Date(negotiation.updated_at).toLocaleString()}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => refreshNegotiationMutation.mutate(negotiation.id)}
                                disabled={refreshNegotiationMutation.isPending}
                              >
                                <RefreshCcw className="h-4 w-4 mr-1" />
                                Refresh
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </TabsContent>

                <TabsContent value="transfers" className="space-y-3">
                  {connectorTransfersQuery.isLoading ? (
                    <LoadingSpinner />
                  ) : connectorTransfers.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No transfers found.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Transfer ID</TableHead>
                          <TableHead>State</TableHead>
                          <TableHead>Negotiation</TableHead>
                          <TableHead>Updated</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {connectorTransfers.map((transfer) => (
                          <TableRow key={transfer.id}>
                            <TableCell className="font-medium">{transfer.transfer_id}</TableCell>
                            <TableCell>{transfer.state}</TableCell>
                            <TableCell className="text-muted-foreground">
                              {transfer.negotiation_id || '-'}
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {new Date(transfer.updated_at).toLocaleString()}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => refreshTransferMutation.mutate(transfer.id)}
                                disabled={refreshTransferMutation.isPending}
                              >
                                <RefreshCcw className="h-4 w-4 mr-1" />
                                Refresh
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </TabsContent>

                <TabsContent value="conformance" className="space-y-3">
                  {connectorConformanceQuery.isLoading ? (
                    <LoadingSpinner />
                  ) : connectorConformanceRuns.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No conformance runs recorded for this connector.
                    </p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Run Type</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Created</TableHead>
                          <TableHead>Artifact</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {connectorConformanceRuns.map((run) => (
                          <TableRow key={run.id}>
                            <TableCell>{run.run_type}</TableCell>
                            <TableCell>{run.status}</TableCell>
                            <TableCell className="text-muted-foreground">
                              {new Date(run.created_at).toLocaleString()}
                            </TableCell>
                            <TableCell>
                              {run.artifact_url ? (
                                <span className="text-xs text-muted-foreground break-all">
                                  {run.artifact_url}
                                </span>
                              ) : (
                                '-'
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </TabsContent>

                <TabsContent value="evidence" className="space-y-3">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="evidence-dpp">DPP</Label>
                      <Select value={evidenceDppId} onValueChange={setEvidenceDppId}>
                        <SelectTrigger id="evidence-dpp">
                          <SelectValue placeholder="Select DPP for evidence pack" />
                        </SelectTrigger>
                        <SelectContent>
                          {(publishedDppsData?.dpps ?? []).map((dpp) => (
                            <SelectItem key={dpp.id} value={dpp.id}>
                              {dpp.asset_ids?.manufacturerPartId || dpp.id.slice(0, 8)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="evidence-profile">Evidence Profile</Label>
                      <Select value={evidenceProfile} onValueChange={setEvidenceProfile}>
                        <SelectTrigger id="evidence-profile">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="espr_core">ESPR Core</SelectItem>
                          <SelectItem value="battery_reg">Battery Regulation</SelectItem>
                          <SelectItem value="sector_profile">Sector Profile</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <Button
                    onClick={() => {
                      if (evidenceDppId) {
                        evidenceMutation.mutate({ dppId: evidenceDppId, profile: evidenceProfile });
                      }
                    }}
                    disabled={!evidenceDppId || evidenceMutation.isPending}
                  >
                    {evidenceMutation.isPending ? 'Loading Evidence...' : 'Load Evidence'}
                  </Button>
                  {evidenceMutation.data && (
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground">Compliance Reports</p>
                        <p className="text-2xl font-semibold">
                          {evidenceMutation.data.compliance_reports.length}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground">Dataspace Publications</p>
                        <p className="text-2xl font-semibold">
                          {evidenceMutation.data.dataspace_publications.length}
                        </p>
                      </div>
                      <div className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground">Conformance Runs</p>
                        <p className="text-2xl font-semibold">
                          {evidenceMutation.data.dataspace_conformance_runs.length}
                        </p>
                      </div>
                      <div className="md:col-span-3 rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground mb-1">Generated</p>
                        <p className="text-sm">
                          {new Date(evidenceMutation.data.generated_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </Card>
          )}
        </>
      )}

      <Dialog open={showManifestDialog} onOpenChange={setShowManifestDialog}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Connector Manifest</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="manifest-json">Manifest JSON</Label>
              <Textarea
                id="manifest-json"
                value={manifestText}
                onChange={(event) => setManifestText(event.target.value)}
                className="min-h-[260px] font-mono text-xs"
                placeholder='{"connector": {...}, "policy_templates": []}'
              />
            </div>
            {manifestJsonError && <p className="text-sm text-red-600">{manifestJsonError}</p>}
            {manifestDiffMutation.data && (
              <div className="rounded-lg border p-3 space-y-2">
                <p className="text-sm font-medium">
                  Diff Preview: {manifestDiffMutation.data.has_changes ? 'Changes detected' : 'No changes'}
                </p>
                {manifestDiffMutation.data.changes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Manifest is already in sync.</p>
                ) : (
                  <div className="space-y-1 max-h-40 overflow-auto">
                    {manifestDiffMutation.data.changes.map((change, index) => (
                      <p key={`${change.resource}-${change.field}-${index}`} className="text-xs">
                        {change.action.toUpperCase()} · {change.resource}
                        {change.field ? ` · ${change.field}` : ''}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowManifestDialog(false)}>
              Close
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                void handlePreviewManifest();
              }}
              disabled={manifestDiffMutation.isPending || manifestApplyMutation.isPending}
            >
              {manifestDiffMutation.isPending ? 'Previewing...' : 'Preview Diff'}
            </Button>
            <Button
              onClick={() => {
                void handleApplyManifest();
              }}
              disabled={manifestApplyMutation.isPending}
            >
              {manifestApplyMutation.isPending ? 'Applying...' : 'Apply Manifest'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={publishConnectorId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPublishConnectorId(null);
            setSelectedDppId('');
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Publish DPP to Dataspace</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="publish-dpp">Published DPP</Label>
              <Select value={selectedDppId} onValueChange={setSelectedDppId}>
                <SelectTrigger id="publish-dpp">
                  <SelectValue placeholder="Select a published DPP" />
                </SelectTrigger>
                <SelectContent>
                  {(publishedDppsData?.dpps ?? []).map((dpp) => (
                    <SelectItem key={dpp.id} value={dpp.id}>
                      {dpp.asset_ids?.manufacturerPartId || dpp.id.slice(0, 8)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setPublishConnectorId(null);
                setSelectedDppId('');
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (publishConnectorId && selectedDppId) {
                  void publishMutation.mutateAsync({
                    connectorId: publishConnectorId,
                    dppId: selectedDppId,
                  });
                }
              }}
              disabled={!selectedDppId || publishMutation.isPending}
            >
              {publishMutation.isPending ? 'Publishing...' : 'Publish'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
