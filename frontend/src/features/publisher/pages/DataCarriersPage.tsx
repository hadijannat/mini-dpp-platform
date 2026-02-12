import { useState, useEffect, useCallback } from 'react';
import { useAuth } from 'react-oidc-context';
import {
  QrCode,
  Download,
  RefreshCw,
  Link2,
  Copy,
  Check,
  AlertTriangle,
  Package,
  Workflow,
  Layers,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import type {
  DataCarrierCreateRequest,
  DataCarrierPreSalePackResponse,
  DataCarrierRenderRequest,
  DataCarrierResponse,
  DataCarrierWithdrawRequest,
} from '@/api/types';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useDataCarriersApi } from '@/features/publisher/hooks/useDataCarriersApi';

type IdentityLevel = DataCarrierResponse['identity_level'];
type IdentifierScheme = DataCarrierResponse['identifier_scheme'];
type CarrierType = DataCarrierResponse['carrier_type'];
type ResolverStrategy = DataCarrierResponse['resolver_strategy'];

type LegacyCarrierFormat = 'qr' | 'gs1_qr';
type OutputType = 'png' | 'svg' | 'pdf';

interface DPP {
  id: string;
  asset_ids: {
    manufacturerPartId?: string;
    serialNumber?: string;
    batchId?: string;
    gtin?: string;
  };
  status: string;
  created_at: string;
}

const WIZARD_STEPS = [
  'Scope',
  'Carrier Type',
  'Identifier Build',
  'Resolver',
  'Preview / QA',
  'Export & Pre-sale',
  'Lifecycle',
] as const;

const DEFAULT_PROFILE = {
  name: 'generic_espr_v1',
  allowedCarrierTypes: ['qr', 'datamatrix'] as CarrierType[],
  nfcAvailable: true,
  defaultIdentityLevel: 'item' as IdentityLevel,
};

function computeGTINCheckDigit(payload: string): string {
  let sum = 0;
  const reversed = payload.split('').reverse();
  for (let i = 0; i < reversed.length; i += 1) {
    const digit = Number(reversed[i]);
    sum += digit * (i % 2 === 0 ? 3 : 1);
  }
  return String((10 - (sum % 10)) % 10);
}

function validateGTIN(gtin: string): boolean {
  const digits = gtin.replace(/\D/g, '');
  if (![8, 12, 13, 14].includes(digits.length)) return false;
  const payload = digits.slice(0, -1);
  return digits.slice(-1) === computeGTINCheckDigit(payload);
}

export default function DataCarriersPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const {
    listCarriers,
    createCarrier,
    renderCarrier,
    deprecateCarrier,
    withdrawCarrier,
    reissueCarrier,
    getPreSalePack,
  } = useDataCarriersApi(token);

  const [dpps, setDpps] = useState<DPP[]>([]);
  const [selectedDpp, setSelectedDpp] = useState<string>('');
  const [carriers, setCarriers] = useState<DataCarrierResponse[]>([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [step, setStep] = useState(0);
  const [activeCarrier, setActiveCarrier] = useState<DataCarrierResponse | null>(null);
  const [preSalePack, setPreSalePack] = useState<DataCarrierPreSalePackResponse | null>(null);

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Managed carrier workflow fields
  const [identityLevel, setIdentityLevel] = useState<IdentityLevel>(DEFAULT_PROFILE.defaultIdentityLevel);
  const [identifierScheme, setIdentifierScheme] = useState<IdentifierScheme>('gs1_gtin');
  const [carrierType, setCarrierType] = useState<CarrierType>('qr');
  const [resolverStrategy, setResolverStrategy] = useState<ResolverStrategy>('dynamic_linkset');
  const [preSaleEnabled, setPreSaleEnabled] = useState(true);
  const [outputType, setOutputType] = useState<OutputType>('png');

  const [gtin, setGtin] = useState('');
  const [serial, setSerial] = useState('');
  const [batch, setBatch] = useState('');
  const [manufacturerPartId, setManufacturerPartId] = useState('');
  const [directUrl, setDirectUrl] = useState('');

  const [size, setSize] = useState(400);
  const [foregroundColor, setForegroundColor] = useState('#000000');
  const [backgroundColor, setBackgroundColor] = useState('#FFFFFF');
  const [includeText, setIncludeText] = useState(true);
  const [textLabel, setTextLabel] = useState('');

  const [placementTarget, setPlacementTarget] = useState('product');
  const [placementZone, setPlacementZone] = useState('');
  const [placementInstructions, setPlacementInstructions] = useState('');
  const [fallbackText, setFallbackText] = useState('');

  // Legacy quick-QR compatibility fields
  const [showLegacy, setShowLegacy] = useState(false);
  const [legacyFormat, setLegacyFormat] = useState<LegacyCarrierFormat>('qr');
  const [legacyOutputType, setLegacyOutputType] = useState<OutputType>('png');

  const loadDPPs = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const response = await tenantApiFetch('/dpps', {}, token);
      if (!response.ok) {
        const message = await getApiErrorMessage(response, 'Failed to load DPPs');
        setError(message);
        return;
      }
      const data = await response.json();
      const all = Array.isArray(data)
        ? data
        : Array.isArray(data?.items)
          ? data.items
          : Array.isArray(data?.dpps)
            ? data.dpps
            : [];
      setDpps(all.filter((d: DPP) => d.status === 'published'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load DPPs');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadCarriers = useCallback(async () => {
    if (!selectedDpp) {
      setCarriers([]);
      return;
    }
    try {
      const data = await listCarriers({ dppId: selectedDpp });
      setCarriers(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data carriers');
    }
  }, [selectedDpp, listCarriers]);

  useEffect(() => {
    void loadDPPs();
  }, [loadDPPs]);

  useEffect(() => {
    void loadCarriers();
  }, [loadCarriers]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const selectedDppData = dpps.find((d) => d.id === selectedDpp);

  useEffect(() => {
    if (!selectedDppData) return;
    if (!manufacturerPartId) {
      setManufacturerPartId(selectedDppData.asset_ids?.manufacturerPartId || '');
    }
    if (!serial) {
      setSerial(selectedDppData.asset_ids?.serialNumber || '');
    }
    if (!batch) {
      setBatch(selectedDppData.asset_ids?.batchId || '');
    }
    if (!gtin) {
      setGtin(selectedDppData.asset_ids?.gtin || '');
    }
  }, [selectedDppData, manufacturerPartId, serial, batch, gtin]);

  const identifierValidationError = (() => {
    if (!selectedDpp) return 'Select a published DPP first.';
    if (identifierScheme === 'gs1_gtin') {
      if (!gtin.trim()) return 'GTIN is required for GS1 carriers.';
      if (!validateGTIN(gtin)) return 'GTIN must include a valid GS1 check digit.';
      if (identityLevel === 'item' && !serial.trim()) return 'Serial is required for item-level.';
      if (identityLevel === 'batch' && !batch.trim()) return 'Batch is required for batch-level.';
      return null;
    }
    if (identifierScheme === 'iec61406') {
      if (!manufacturerPartId.trim()) return 'Manufacturer part ID is required for IEC 61406.';
      if (identityLevel === 'item' && !serial.trim()) return 'Serial is required for item-level.';
      if (identityLevel === 'batch' && !batch.trim()) return 'Batch is required for batch-level.';
      return null;
    }
    if (identifierScheme === 'direct_url') {
      if (!directUrl.trim()) return 'Direct URL is required.';
      try {
        const parsed = new URL(directUrl);
        if (!['http:', 'https:'].includes(parsed.protocol)) return 'URL must use http/https.';
      } catch {
        return 'Direct URL must be a valid absolute URL.';
      }
    }
    return null;
  })();

  const createManagedCarrier = async () => {
    if (!token || !selectedDpp) return;
    if (identifierValidationError) {
      setError(identifierValidationError);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const payload: DataCarrierCreateRequest = {
        dpp_id: selectedDpp,
        identity_level: identityLevel,
        identifier_scheme: identifierScheme,
        carrier_type: carrierType,
        resolver_strategy: resolverStrategy,
        pre_sale_enabled: preSaleEnabled,
        identifier_data: {
          gtin: gtin || undefined,
          serial: serial || undefined,
          batch: batch || undefined,
          manufacturer_part_id: manufacturerPartId || undefined,
          direct_url: directUrl || undefined,
        },
        layout_profile: {
          size,
          foreground_color: foregroundColor,
          background_color: backgroundColor,
          include_text: includeText,
          text_label: textLabel || undefined,
          error_correction: 'H',
          quiet_zone_modules: 4,
        },
        placement_metadata: {
          target: placementTarget,
          zone: placementZone || undefined,
          instructions: placementInstructions || undefined,
          human_readable_fallback: fallbackText || undefined,
        },
      };

      const created = await createCarrier(payload);
      setActiveCarrier(created);
      await loadCarriers();
      setStep(Math.max(step, 4));
      await renderManagedPreview(created.id, 'png');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create data carrier');
    } finally {
      setSaving(false);
    }
  };

  const renderManagedPreview = async (carrierId: string, type: OutputType) => {
    if (!token) return;
    setGenerating(true);
    setError(null);

    try {
      const request: DataCarrierRenderRequest = {
        output_type: type,
        persist_artifact: false,
      };
      const blob = await renderCarrier(carrierId, request);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to render data carrier');
    } finally {
      setGenerating(false);
    }
  };

  const downloadManagedCarrier = async (carrierId: string, type: OutputType) => {
    if (!token) return;
    setGenerating(true);
    try {
      const request: DataCarrierRenderRequest = {
        output_type: type,
        persist_artifact: true,
      };
      const blob = await renderCarrier(carrierId, request);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `data-carrier-${carrierId}.${type}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download data carrier');
    } finally {
      setGenerating(false);
    }
  };

  const loadPreSalePack = async (carrierId: string) => {
    if (!token) return;
    try {
      setPreSalePack(await getPreSalePack(carrierId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pre-sale pack');
    }
  };

  const runLifecycleAction = async (action: 'deprecate' | 'withdraw' | 'reissue') => {
    if (!token || !activeCarrier) return;
    setSaving(true);
    try {
      let updated: DataCarrierResponse;
      if (action === 'deprecate') {
        updated = await deprecateCarrier(activeCarrier.id);
      } else if (action === 'withdraw') {
        const payload: DataCarrierWithdrawRequest = { reason: 'Withdrawn by publisher' };
        updated = await withdrawCarrier(activeCarrier.id, payload);
      } else {
        updated = await reissueCarrier(activeCarrier.id);
      }

      setActiveCarrier(updated);
      await loadCarriers();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} carrier`);
    } finally {
      setSaving(false);
    }
  };

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const generateLegacyPreview = async () => {
    if (!token || !selectedDpp) return;
    setGenerating(true);
    try {
      const response = await tenantApiFetch(
        `/qr/${selectedDpp}/carrier`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            format: legacyFormat,
            output_type: 'png',
            size: Math.min(size, 600),
            foreground_color: foregroundColor,
            background_color: backgroundColor,
            include_text: includeText,
          }),
        },
        token
      );
      if (!response.ok) {
        const message = await getApiErrorMessage(response, 'Failed to generate legacy preview');
        setError(message);
        return;
      }
      const blob = await response.blob();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate legacy preview');
    } finally {
      setGenerating(false);
    }
  };

  const downloadLegacyCarrier = async () => {
    if (!token || !selectedDpp) return;
    setGenerating(true);
    try {
      const response = await tenantApiFetch(
        `/qr/${selectedDpp}/carrier`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            format: legacyFormat,
            output_type: legacyOutputType,
            size,
            foreground_color: foregroundColor,
            background_color: backgroundColor,
            include_text: includeText,
          }),
        },
        token
      );
      if (!response.ok) {
        const message = await getApiErrorMessage(response, 'Failed to download legacy carrier');
        setError(message);
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `legacy-carrier-${selectedDpp}.${legacyOutputType}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download legacy carrier');
    } finally {
      setGenerating(false);
    }
  };

  const canGoNext = step < WIZARD_STEPS.length - 1;
  const canGoBack = step > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Data Carriers"
        description="Lifecycle-managed ESPR-aligned carrier workflows with GS1 GTIN strict validation"
        actions={
          <Button variant="outline" onClick={loadDPPs} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {error && <ErrorBanner message={error} />}

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Workflow className="h-4 w-4" />
            Managed Carrier Wizard
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap gap-2">
            {WIZARD_STEPS.map((label, idx) => (
              <div
                key={label}
                className={`px-3 py-1 rounded-full text-xs border ${idx === step ? 'bg-primary text-primary-foreground border-primary' : 'bg-muted/40 text-muted-foreground border-border'}`}
              >
                {idx + 1}. {label}
              </div>
            ))}
          </div>

          {step === 0 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="managed-dpp-select">Select Published DPP</Label>
                <select
                  id="managed-dpp-select"
                  value={selectedDpp}
                  onChange={(e) => {
                    setSelectedDpp(e.target.value);
                    setActiveCarrier(null);
                    setPreSalePack(null);
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">-- Select a DPP --</option>
                  {dpps.map((dpp) => (
                    <option key={dpp.id} value={dpp.id}>
                      {(dpp.asset_ids?.manufacturerPartId || dpp.id.slice(0, 8))} - {dpp.asset_ids?.serialNumber || 'No Serial'}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Identity level</Label>
                  <div className="mt-2 flex gap-3">
                    {(['model', 'batch', 'item'] as IdentityLevel[]).map((level) => (
                      <label key={level} className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          checked={identityLevel === level}
                          onChange={() => setIdentityLevel(level)}
                        />
                        {level}
                      </label>
                    ))}
                  </div>
                </div>
                <div className="p-3 rounded-md border bg-muted/20">
                  <div className="text-xs font-medium text-muted-foreground mb-1">Compliance profile</div>
                  <div className="text-sm font-semibold">{DEFAULT_PROFILE.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Allowed: {DEFAULT_PROFILE.allowedCarrierTypes.join(', ')}; NFC: {DEFAULT_PROFILE.nfcAvailable ? 'enabled' : 'disabled'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="managed-identifier-scheme">Identifier scheme</Label>
                <select
                  id="managed-identifier-scheme"
                  value={identifierScheme}
                  onChange={(e) => {
                    const next = e.target.value as IdentifierScheme;
                    setIdentifierScheme(next);
                    if (next === 'gs1_gtin') setResolverStrategy('dynamic_linkset');
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="gs1_gtin">GS1 GTIN</option>
                  <option value="iec61406">IEC 61406</option>
                  <option value="direct_url">Direct URL</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Carrier type</Label>
                <select
                  value={carrierType}
                  onChange={(e) => setCarrierType(e.target.value as CarrierType)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="qr">QR</option>
                  <option value="datamatrix">DataMatrix</option>
                  <option value="nfc">NFC</option>
                </select>
                {!DEFAULT_PROFILE.allowedCarrierTypes.includes(carrierType) && carrierType !== 'nfc' && (
                  <p className="text-xs text-amber-600">Carrier type is outside profile defaults.</p>
                )}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              {identifierScheme === 'gs1_gtin' && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <Label>GTIN</Label>
                    <input className="w-full h-10 rounded-md border px-3" value={gtin} onChange={(e) => setGtin(e.target.value)} />
                  </div>
                  <div>
                    <Label>Serial</Label>
                    <input className="w-full h-10 rounded-md border px-3" value={serial} onChange={(e) => setSerial(e.target.value)} />
                  </div>
                  <div>
                    <Label>Batch</Label>
                    <input className="w-full h-10 rounded-md border px-3" value={batch} onChange={(e) => setBatch(e.target.value)} />
                  </div>
                </div>
              )}

              {identifierScheme === 'iec61406' && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <Label>Manufacturer part ID</Label>
                    <input className="w-full h-10 rounded-md border px-3" value={manufacturerPartId} onChange={(e) => setManufacturerPartId(e.target.value)} />
                  </div>
                  <div>
                    <Label>Serial</Label>
                    <input className="w-full h-10 rounded-md border px-3" value={serial} onChange={(e) => setSerial(e.target.value)} />
                  </div>
                  <div>
                    <Label>Batch</Label>
                    <input className="w-full h-10 rounded-md border px-3" value={batch} onChange={(e) => setBatch(e.target.value)} />
                  </div>
                </div>
              )}

              {identifierScheme === 'direct_url' && (
                <div>
                  <Label>Direct URL</Label>
                  <input
                    className="w-full h-10 rounded-md border px-3"
                    value={directUrl}
                    onChange={(e) => setDirectUrl(e.target.value)}
                    placeholder="https://example.com/path"
                  />
                </div>
              )}

              {identifierValidationError ? (
                <Alert className="border-amber-300 bg-amber-50">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{identifierValidationError}</AlertDescription>
                </Alert>
              ) : (
                <Alert className="border-emerald-300 bg-emerald-50">
                  <Check className="h-4 w-4" />
                  <AlertDescription>Identifier validation passed.</AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Resolver strategy</Label>
                  <select
                    value={resolverStrategy}
                    onChange={(e) => setResolverStrategy(e.target.value as ResolverStrategy)}
                    disabled={identifierScheme === 'gs1_gtin'}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="dynamic_linkset">dynamic_linkset</option>
                    <option value="direct_public_dpp">direct_public_dpp</option>
                  </select>
                  {identifierScheme === 'gs1_gtin' && (
                    <p className="text-xs text-muted-foreground mt-1">GS1 is locked to dynamic_linkset.</p>
                  )}
                </div>
                <div className="flex items-center gap-3 pt-6">
                  <Switch checked={preSaleEnabled} onCheckedChange={setPreSaleEnabled} id="pre-sale-enabled" />
                  <Label htmlFor="pre-sale-enabled">Enable pre-sale pack</Label>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Size: {size}px</Label>
                  <input type="range" min="100" max="1000" step="50" value={size} onChange={(e) => setSize(Number(e.target.value))} className="w-full" />
                </div>
                <div className="flex items-center gap-3 pt-6">
                  <Switch checked={includeText} onCheckedChange={setIncludeText} id="include-text" />
                  <Label htmlFor="include-text">Include text on carrier</Label>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label>Foreground</Label>
                  <input type="color" value={foregroundColor} onChange={(e) => setForegroundColor(e.target.value)} className="w-full h-10 rounded" />
                </div>
                <div>
                  <Label>Background</Label>
                  <input type="color" value={backgroundColor} onChange={(e) => setBackgroundColor(e.target.value)} className="w-full h-10 rounded" />
                </div>
                <div>
                  <Label>Text label</Label>
                  <input className="w-full h-10 rounded-md border px-3" value={textLabel} onChange={(e) => setTextLabel(e.target.value)} placeholder="Optional" />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Placement target</Label>
                  <input className="w-full h-10 rounded-md border px-3" value={placementTarget} onChange={(e) => setPlacementTarget(e.target.value)} />
                </div>
                <div>
                  <Label>Placement zone</Label>
                  <input className="w-full h-10 rounded-md border px-3" value={placementZone} onChange={(e) => setPlacementZone(e.target.value)} />
                </div>
              </div>

              <div>
                <Label>Placement instructions</Label>
                <textarea className="w-full rounded-md border px-3 py-2 min-h-[80px]" value={placementInstructions} onChange={(e) => setPlacementInstructions(e.target.value)} />
              </div>

              <div>
                <Label>Human-readable fallback</Label>
                <input className="w-full h-10 rounded-md border px-3" value={fallbackText} onChange={(e) => setFallbackText(e.target.value)} />
              </div>

              <Button onClick={createManagedCarrier} disabled={saving || !!identifierValidationError}>
                <Package className="h-4 w-4 mr-2" />
                {saving ? 'Creating...' : 'Create Managed Carrier'}
              </Button>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              {!activeCarrier ? (
                <p className="text-sm text-muted-foreground">Create a managed carrier in Step 4 first.</p>
              ) : (
                <>
                  <div className="p-3 border rounded-md bg-muted/20">
                    <div className="text-xs text-muted-foreground">Active carrier</div>
                    <div className="font-mono text-xs break-all mt-1">{activeCarrier.encoded_uri}</div>
                  </div>

                  <div className="flex gap-3">
                    <Button variant="outline" onClick={() => void renderManagedPreview(activeCarrier.id, 'png')} disabled={generating}>
                      <QrCode className="h-4 w-4 mr-2" />
                      Preview PNG
                    </Button>
                    <Button onClick={() => void downloadManagedCarrier(activeCarrier.id, outputType)} disabled={generating}>
                      <Download className="h-4 w-4 mr-2" />
                      Download {outputType.toUpperCase()}
                    </Button>
                  </div>

                  {previewUrl && <img src={previewUrl} alt="Managed carrier preview" className="max-h-[280px] border rounded-md p-3 bg-white" />}
                </>
              )}
            </div>
          )}

          {step === 5 && (
            <div className="space-y-4">
              {!activeCarrier ? (
                <p className="text-sm text-muted-foreground">No active managed carrier selected.</p>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label>Download output format</Label>
                    <div className="flex gap-4">
                      {(['png', 'svg', 'pdf'] as OutputType[]).map((type) => (
                        <label key={type} className="flex items-center gap-2 text-sm">
                          <input type="radio" checked={outputType === type} onChange={() => setOutputType(type)} />
                          {type.toUpperCase()}
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button onClick={() => void downloadManagedCarrier(activeCarrier.id, outputType)}>
                      <Download className="h-4 w-4 mr-2" />
                      Download Artifact
                    </Button>
                    <Button variant="outline" onClick={() => void loadPreSalePack(activeCarrier.id)}>
                      <Link2 className="h-4 w-4 mr-2" />
                      Generate Pre-sale Pack
                    </Button>
                  </div>

                  {preSalePack && (
                    <Alert className="border-blue-300 bg-blue-50">
                      <AlertDescription>
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-semibold text-blue-900">Pre-sale URL</span>
                          <button onClick={() => void copyText(preSalePack.consumer_url)} className="text-blue-700">
                            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                          </button>
                        </div>
                        <code className="text-xs break-all block text-blue-800">{preSalePack.consumer_url}</code>
                      </AlertDescription>
                    </Alert>
                  )}
                </>
              )}
            </div>
          )}

          {step === 6 && (
            <div className="space-y-4">
              {!activeCarrier ? (
                <p className="text-sm text-muted-foreground">No managed carrier selected.</p>
              ) : (
                <>
                  <div className="p-3 rounded-md border bg-muted/20">
                    <div className="text-sm">Current status: <strong>{activeCarrier.status}</strong></div>
                    {activeCarrier.withdrawn_reason && (
                      <div className="text-xs text-muted-foreground mt-1">Reason: {activeCarrier.withdrawn_reason}</div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={() => void runLifecycleAction('deprecate')} disabled={saving}>Deprecate</Button>
                    <Button variant="destructive" onClick={() => void runLifecycleAction('withdraw')} disabled={saving}>Withdraw</Button>
                    <Button onClick={() => void runLifecycleAction('reissue')} disabled={saving}>Reissue</Button>
                  </div>
                </>
              )}
            </div>
          )}

          <div className="flex items-center justify-between">
            <Button variant="outline" disabled={!canGoBack} onClick={() => setStep((s) => Math.max(0, s - 1))}>
              Back
            </Button>
            <Button disabled={!canGoNext} onClick={() => setStep((s) => Math.min(WIZARD_STEPS.length - 1, s + 1))}>
              Next
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Layers className="h-4 w-4" />
              Managed Carriers for Selected DPP
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!selectedDpp ? (
            <p className="text-sm text-muted-foreground">Select a DPP to list carriers.</p>
          ) : carriers.length === 0 ? (
            <p className="text-sm text-muted-foreground">No carriers found.</p>
          ) : (
            <div className="space-y-2">
              {carriers.map((carrier) => (
                <button
                  key={carrier.id}
                  className={`w-full text-left border rounded-md p-3 ${activeCarrier?.id === carrier.id ? 'border-primary bg-primary/5' : 'border-border'}`}
                  onClick={() => {
                    setActiveCarrier(carrier);
                    setPreSalePack(null);
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{carrier.identifier_scheme} / {carrier.identity_level}</span>
                    <span className="text-xs uppercase text-muted-foreground">{carrier.status}</span>
                  </div>
                  <code className="text-xs block mt-1 break-all">{carrier.identifier_key}</code>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Legacy Quick QR (Compatibility)
            </span>
            <Button variant="ghost" size="sm" onClick={() => setShowLegacy((v) => !v)}>
              {showLegacy ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </CardTitle>
        </CardHeader>
        {showLegacy && (
          <CardContent className="space-y-4">
            <Alert>
              <AlertDescription>
                `/qr/*` endpoints are compatibility wrappers and are marked deprecated in OpenAPI.
              </AlertDescription>
            </Alert>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Legacy format</Label>
                <div className="mt-2 flex gap-4">
                  <label className="text-sm flex items-center gap-2"><input type="radio" checked={legacyFormat === 'qr'} onChange={() => setLegacyFormat('qr')} />qr</label>
                  <label className="text-sm flex items-center gap-2"><input type="radio" checked={legacyFormat === 'gs1_qr'} onChange={() => setLegacyFormat('gs1_qr')} />gs1_qr</label>
                </div>
              </div>
              <div>
                <Label>Output</Label>
                <div className="mt-2 flex gap-4">
                  {(['png', 'svg', 'pdf'] as OutputType[]).map((type) => (
                    <label key={type} className="text-sm flex items-center gap-2">
                      <input type="radio" checked={legacyOutputType === type} onChange={() => setLegacyOutputType(type)} />
                      {type}
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => void generateLegacyPreview()} disabled={!selectedDpp || generating}>
                <QrCode className="h-4 w-4 mr-2" />
                Preview Legacy
              </Button>
              <Button onClick={() => void downloadLegacyCarrier()} disabled={!selectedDpp || generating}>
                <Download className="h-4 w-4 mr-2" />
                Download Legacy
              </Button>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
