import { useState, useEffect } from 'react';
import { HelpCircle, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useOpcuaSources } from '../hooks/useOpcuaSources';
import {
  OPCUAMappingType,
  DPPBindingMode,
  type OPCUAMappingCreateInput,
  type OPCUAMappingResponse,
} from '../lib/opcuaApi';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MappingFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: OPCUAMappingCreateInput) => void;
  initialData?: OPCUAMappingResponse | null;
  isPending?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MappingFormDialog({
  open,
  onOpenChange,
  onSubmit,
  initialData,
  isPending,
}: MappingFormDialogProps) {
  const isEditing = !!initialData;

  // Source data for the dropdown
  const { data: sourcesData } = useOpcuaSources();
  const sources = sourcesData?.items ?? [];

  // ---- Section 1: OPC UA Source ----
  const [sourceId, setSourceId] = useState('');
  const [opcuaNodeId, setOpcuaNodeId] = useState('');
  const [opcuaBrowsePath, setOpcuaBrowsePath] = useState('');
  const [opcuaDatatype, setOpcuaDatatype] = useState('');
  const [samplingIntervalMs, setSamplingIntervalMs] = useState('');

  // ---- Section 2: Target ----
  const [mappingType, setMappingType] = useState<OPCUAMappingType>(OPCUAMappingType.AAS_PATCH);

  // AAS Patch fields
  const [dppBindingMode, setDppBindingMode] = useState<DPPBindingMode>(DPPBindingMode.BY_DPP_ID);
  const [dppId, setDppId] = useState('');
  const [assetIdQuery, setAssetIdQuery] = useState('');
  const [targetTemplateKey, setTargetTemplateKey] = useState('');
  const [targetSubmodelId, setTargetSubmodelId] = useState('');
  const [targetAasPath, setTargetAasPath] = useState('');
  const [patchOp, setPatchOp] = useState('replace');
  const [valueTransformExpr, setValueTransformExpr] = useState('');
  const [unitHint, setUnitHint] = useState('');

  // EPCIS Event fields
  const [epcisEventType, setEpcisEventType] = useState('');
  const [epcisBizStep, setEpcisBizStep] = useState('');
  const [epcisDisposition, setEpcisDisposition] = useState('');
  const [epcisAction, setEpcisAction] = useState('');
  const [epcisReadPoint, setEpcisReadPoint] = useState('');
  const [epcisBizLocation, setEpcisBizLocation] = useState('');

  // ---- Section 3: SAMM ----
  const [sammOpen, setSammOpen] = useState(false);
  const [sammAspectUrn, setSammAspectUrn] = useState('');
  const [sammProperty, setSammProperty] = useState('');
  const [sammVersion, setSammVersion] = useState('');

  // ---- Enable toggle ----
  const [isEnabled, setIsEnabled] = useState(true);

  // ---- Reset / prefill on open ----
  useEffect(() => {
    if (open) {
      if (initialData) {
        // Map snake_case response fields to camelCase state
        setSourceId(initialData.source_id);
        setOpcuaNodeId(initialData.opcua_node_id);
        setOpcuaBrowsePath(initialData.opcua_browse_path ?? '');
        setOpcuaDatatype(initialData.opcua_datatype ?? '');
        setSamplingIntervalMs(
          initialData.sampling_interval_ms != null
            ? String(initialData.sampling_interval_ms)
            : '',
        );
        setMappingType(initialData.mapping_type);
        setDppBindingMode(initialData.dpp_binding_mode);
        setDppId(initialData.dpp_id ?? '');
        setAssetIdQuery(
          initialData.asset_id_query != null
            ? JSON.stringify(initialData.asset_id_query, null, 2)
            : '',
        );
        setTargetTemplateKey(initialData.target_template_key ?? '');
        setTargetSubmodelId(initialData.target_submodel_id ?? '');
        setTargetAasPath(initialData.target_aas_path ?? '');
        setPatchOp(initialData.patch_op ?? 'replace');
        setValueTransformExpr(initialData.value_transform_expr ?? '');
        setUnitHint(initialData.unit_hint ?? '');
        setEpcisEventType(initialData.epcis_event_type ?? '');
        setEpcisBizStep(initialData.epcis_biz_step ?? '');
        setEpcisDisposition(initialData.epcis_disposition ?? '');
        setEpcisAction(initialData.epcis_action ?? '');
        setEpcisReadPoint(initialData.epcis_read_point ?? '');
        setEpcisBizLocation(initialData.epcis_biz_location ?? '');
        setSammAspectUrn(initialData.samm_aspect_urn ?? '');
        setSammProperty(initialData.samm_property ?? '');
        setSammVersion(initialData.samm_version ?? '');
        setIsEnabled(initialData.is_enabled);

        // Auto-expand SAMM section if any SAMM field is populated
        setSammOpen(
          !!(initialData.samm_aspect_urn || initialData.samm_property || initialData.samm_version),
        );
      } else {
        // Reset to defaults for create
        setSourceId('');
        setOpcuaNodeId('');
        setOpcuaBrowsePath('');
        setOpcuaDatatype('');
        setSamplingIntervalMs('');
        setMappingType(OPCUAMappingType.AAS_PATCH);
        setDppBindingMode(DPPBindingMode.BY_DPP_ID);
        setDppId('');
        setAssetIdQuery('');
        setTargetTemplateKey('');
        setTargetSubmodelId('');
        setTargetAasPath('');
        setPatchOp('replace');
        setValueTransformExpr('');
        setUnitHint('');
        setEpcisEventType('');
        setEpcisBizStep('');
        setEpcisDisposition('');
        setEpcisAction('');
        setEpcisReadPoint('');
        setEpcisBizLocation('');
        setSammAspectUrn('');
        setSammProperty('');
        setSammVersion('');
        setIsEnabled(true);
        setSammOpen(false);
      }
    }
  }, [open, initialData]);

  // ---- Submit ----
  function handleSubmit() {
    const interval = samplingIntervalMs ? Number(samplingIntervalMs) : null;

    let parsedAssetIdQuery: Record<string, unknown> | null = null;
    if (dppBindingMode === DPPBindingMode.BY_ASSET_ID_QUERY && assetIdQuery.trim()) {
      try {
        parsedAssetIdQuery = JSON.parse(assetIdQuery) as Record<string, unknown>;
      } catch {
        // If JSON parse fails, leave null — backend will validate
        parsedAssetIdQuery = null;
      }
    }

    const data: OPCUAMappingCreateInput = {
      sourceId,
      mappingType,
      opcuaNodeId,
      opcuaBrowsePath: opcuaBrowsePath || null,
      opcuaDatatype: opcuaDatatype || null,
      samplingIntervalMs: interval,
      dppBindingMode,
      dppId: dppBindingMode === DPPBindingMode.BY_DPP_ID ? dppId || null : null,
      assetIdQuery:
        dppBindingMode === DPPBindingMode.BY_ASSET_ID_QUERY ? parsedAssetIdQuery : null,
      isEnabled,
    };

    // AAS Patch fields
    if (mappingType === OPCUAMappingType.AAS_PATCH) {
      data.targetTemplateKey = targetTemplateKey || null;
      data.targetSubmodelId = targetSubmodelId || null;
      data.targetAasPath = targetAasPath || null;
      data.patchOp = patchOp || null;
      data.valueTransformExpr = valueTransformExpr || null;
      data.unitHint = unitHint || null;
    }

    // EPCIS Event fields
    if (mappingType === OPCUAMappingType.EPCIS_EVENT) {
      data.epcisEventType = epcisEventType || null;
      data.epcisBizStep = epcisBizStep || null;
      data.epcisDisposition = epcisDisposition || null;
      data.epcisAction = epcisAction || null;
      data.epcisReadPoint = epcisReadPoint || null;
      data.epcisBizLocation = epcisBizLocation || null;
    }

    // SAMM fields (always included if populated)
    data.sammAspectUrn = sammAspectUrn || null;
    data.sammProperty = sammProperty || null;
    data.sammVersion = sammVersion || null;

    onSubmit(data);
  }

  const isValid = sourceId.trim() !== '' && opcuaNodeId.trim() !== '';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Mapping' : 'Add Mapping'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the OPC UA mapping configuration.'
              : 'Create a mapping from an OPC UA variable to a DPP target.'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* ---- Section 1: OPC UA Source ---- */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold text-foreground">OPC UA Source</legend>

            <div className="space-y-2">
              <Label htmlFor="mapping-source">Source *</Label>
              <Select value={sourceId} onValueChange={setSourceId}>
                <SelectTrigger id="mapping-source">
                  <SelectValue placeholder="Select a source" />
                </SelectTrigger>
                <SelectContent>
                  {sources.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="mapping-node-id">Node ID *</Label>
              <Input
                id="mapping-node-id"
                value={opcuaNodeId}
                onChange={(e) => setOpcuaNodeId(e.target.value)}
                placeholder="ns=2;s=MyVariable"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="mapping-browse-path">Browse Path</Label>
              <Input
                id="mapping-browse-path"
                value={opcuaBrowsePath}
                onChange={(e) => setOpcuaBrowsePath(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="mapping-datatype">Data Type</Label>
                <Input
                  id="mapping-datatype"
                  value={opcuaDatatype}
                  onChange={(e) => setOpcuaDatatype(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mapping-interval">Sampling Interval (ms)</Label>
                <Input
                  id="mapping-interval"
                  type="number"
                  min={50}
                  value={samplingIntervalMs}
                  onChange={(e) => setSamplingIntervalMs(e.target.value)}
                  placeholder="1000"
                />
              </div>
            </div>
          </fieldset>

          {/* ---- Section 2: Target ---- */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold text-foreground">Target</legend>

            <div className="space-y-2">
              <Label htmlFor="mapping-type">Mapping Type</Label>
              <Select
                value={mappingType}
                onValueChange={(v) => setMappingType(v as OPCUAMappingType)}
              >
                <SelectTrigger id="mapping-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={OPCUAMappingType.AAS_PATCH}>AAS Value Patch</SelectItem>
                  <SelectItem value={OPCUAMappingType.EPCIS_EVENT}>EPCIS Event</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* ---- AAS Patch fields ---- */}
            {mappingType === OPCUAMappingType.AAS_PATCH && (
              <div className="space-y-4 rounded-md border p-4">
                <div className="space-y-2">
                  <Label htmlFor="mapping-binding-mode">DPP Binding Mode</Label>
                  <Select
                    value={dppBindingMode}
                    onValueChange={(v) => setDppBindingMode(v as DPPBindingMode)}
                  >
                    <SelectTrigger id="mapping-binding-mode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={DPPBindingMode.BY_DPP_ID}>By DPP ID</SelectItem>
                      <SelectItem value={DPPBindingMode.BY_ASSET_ID_QUERY}>
                        By Asset ID Query
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {dppBindingMode === DPPBindingMode.BY_DPP_ID && (
                  <div className="space-y-2">
                    <Label htmlFor="mapping-dpp-id">DPP ID</Label>
                    <Input
                      id="mapping-dpp-id"
                      value={dppId}
                      onChange={(e) => setDppId(e.target.value)}
                    />
                  </div>
                )}

                {dppBindingMode === DPPBindingMode.BY_ASSET_ID_QUERY && (
                  <div className="space-y-2">
                    <Label htmlFor="mapping-asset-query">Asset ID Query (JSON)</Label>
                    <Textarea
                      id="mapping-asset-query"
                      value={assetIdQuery}
                      onChange={(e) => setAssetIdQuery(e.target.value)}
                      placeholder='{"globalAssetId": "..."}'
                      rows={3}
                      className="font-mono text-xs"
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="mapping-template-key">Template Key</Label>
                    <Input
                      id="mapping-template-key"
                      value={targetTemplateKey}
                      onChange={(e) => setTargetTemplateKey(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mapping-submodel-id">Submodel ID</Label>
                    <Input
                      id="mapping-submodel-id"
                      value={targetSubmodelId}
                      onChange={(e) => setTargetSubmodelId(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mapping-aas-path">AAS Path</Label>
                  <Input
                    id="mapping-aas-path"
                    value={targetAasPath}
                    onChange={(e) => setTargetAasPath(e.target.value)}
                    placeholder="Nameplate.ManufacturerName"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="mapping-patch-op">Patch Op</Label>
                    <Select value={patchOp} onValueChange={setPatchOp}>
                      <SelectTrigger id="mapping-patch-op">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="replace">replace</SelectItem>
                        <SelectItem value="add">add</SelectItem>
                        <SelectItem value="remove">remove</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mapping-unit-hint">Unit Hint</Label>
                    <Input
                      id="mapping-unit-hint"
                      value={unitHint}
                      onChange={(e) => setUnitHint(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="mapping-transform">Transform Expression</Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <HelpCircle className="h-3.5 w-3.5 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          A CEL or simple expression to transform the OPC UA value before writing it
                          to the AAS target (e.g. &quot;value * 0.001&quot; or
                          &quot;string(value)&quot;).
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <Input
                    id="mapping-transform"
                    value={valueTransformExpr}
                    onChange={(e) => setValueTransformExpr(e.target.value)}
                    placeholder='value * 0.001'
                  />
                </div>
              </div>
            )}

            {/* ---- EPCIS Event fields ---- */}
            {mappingType === OPCUAMappingType.EPCIS_EVENT && (
              <div className="space-y-4 rounded-md border p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="mapping-epcis-event-type">EPCIS Event Type</Label>
                    <Input
                      id="mapping-epcis-event-type"
                      value={epcisEventType}
                      onChange={(e) => setEpcisEventType(e.target.value)}
                      placeholder="ObjectEvent"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mapping-epcis-biz-step">Biz Step</Label>
                    <Input
                      id="mapping-epcis-biz-step"
                      value={epcisBizStep}
                      onChange={(e) => setEpcisBizStep(e.target.value)}
                      placeholder="commissioning"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="mapping-epcis-disposition">Disposition</Label>
                    <Input
                      id="mapping-epcis-disposition"
                      value={epcisDisposition}
                      onChange={(e) => setEpcisDisposition(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mapping-epcis-action">Action</Label>
                    <Input
                      id="mapping-epcis-action"
                      value={epcisAction}
                      onChange={(e) => setEpcisAction(e.target.value)}
                      placeholder="OBSERVE"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="mapping-epcis-read-point">Read Point</Label>
                    <Input
                      id="mapping-epcis-read-point"
                      value={epcisReadPoint}
                      onChange={(e) => setEpcisReadPoint(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mapping-epcis-biz-location">Biz Location</Label>
                    <Input
                      id="mapping-epcis-biz-location"
                      value={epcisBizLocation}
                      onChange={(e) => setEpcisBizLocation(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            )}
          </fieldset>

          {/* ---- Section 3: SAMM (collapsible) ---- */}
          <Collapsible open={sammOpen} onOpenChange={setSammOpen}>
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="flex w-full items-center justify-between rounded-md border px-4 py-2 text-sm font-semibold hover:bg-muted/50 transition-colors"
              >
                <span>SAMM Mapping</span>
                <ChevronDown
                  className={`h-4 w-4 text-muted-foreground transition-transform ${
                    sammOpen ? 'rotate-180' : ''
                  }`}
                />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-4 rounded-b-md border border-t-0 p-4">
                <div className="space-y-2">
                  <Label htmlFor="mapping-samm-urn">Aspect URN</Label>
                  <Input
                    id="mapping-samm-urn"
                    value={sammAspectUrn}
                    onChange={(e) => setSammAspectUrn(e.target.value)}
                    placeholder="urn:samm:io.catenax..."
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="mapping-samm-property">Property</Label>
                    <Input
                      id="mapping-samm-property"
                      value={sammProperty}
                      onChange={(e) => setSammProperty(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mapping-samm-version">Version</Label>
                    <Input
                      id="mapping-samm-version"
                      value={sammVersion}
                      onChange={(e) => setSammVersion(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* ---- Enabled toggle ---- */}
          <div className="flex items-center gap-2">
            <Checkbox
              id="mapping-enabled"
              checked={isEnabled}
              onCheckedChange={(checked) => setIsEnabled(checked === true)}
            />
            <Label htmlFor="mapping-enabled" className="cursor-pointer">
              Enabled
            </Label>
          </div>
        </div>

        <DialogFooter className="mt-6">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!isValid || isPending}>
            {isPending
              ? isEditing
                ? 'Saving...'
                : 'Creating...'
              : isEditing
                ? 'Save Changes'
                : 'Create Mapping'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
