import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { captureEPCISEvents, BIZ_STEPS, DISPOSITIONS, ACTIONS } from '../lib/epcisApi';
import type { EPCISEventType } from '../lib/epcisApi';

function capitalize(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface CaptureDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dppId: string;
}

const DEFAULT_STATE = {
  eventType: 'ObjectEvent' as EPCISEventType,
  action: 'OBSERVE' as string,
  bizStep: '',
  disposition: '',
  readPoint: '',
  bizLocation: '',
  epcList: '',
  parentId: '',
  childEpcs: '',
  inputEpcList: '',
  outputEpcList: '',
  sensorDeviceId: '',
  sensorType: '',
  sensorValue: '',
  sensorUom: '',
};

export function CaptureDialog({ open, onOpenChange, dppId }: CaptureDialogProps) {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const queryClient = useQueryClient();
  const [form, setForm] = useState(DEFAULT_STATE);
  const [showSensor, setShowSensor] = useState(false);

  const mutation = useMutation({
    mutationFn: () => {
      const event = buildEvent(form);
      const document = {
        '@context': ['https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld'],
        type: 'EPCISDocument',
        schemaVersion: '2.0',
        creationDate: new Date().toISOString(),
        epcisBody: { eventList: [event] },
      };
      return captureEPCISEvents(dppId, document, token);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['epcis-events'] });
      setForm(DEFAULT_STATE);
      onOpenChange(false);
    },
  });

  const update = (patch: Partial<typeof form>) => setForm((prev) => ({ ...prev, ...patch }));

  const needsAction = form.eventType !== 'TransformationEvent';
  const needsParent =
    form.eventType === 'AggregationEvent' || form.eventType === 'AssociationEvent';
  const needsChildEpcs = needsParent;
  const needsEpcList =
    form.eventType === 'ObjectEvent' || form.eventType === 'TransactionEvent';
  const needsTransformLists = form.eventType === 'TransformationEvent';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Capture EPCIS Event</DialogTitle>
          <DialogDescription>
            Enter event details to capture a new EPCIS event for the selected DPP.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Event Type */}
          <div className="space-y-1.5">
            <Label>Event Type</Label>
            <Select
              value={form.eventType}
              onValueChange={(v) => update({ eventType: v as EPCISEventType })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ObjectEvent">Object Event</SelectItem>
                <SelectItem value="AggregationEvent">Aggregation Event</SelectItem>
                <SelectItem value="TransactionEvent">Transaction Event</SelectItem>
                <SelectItem value="TransformationEvent">Transformation Event</SelectItem>
                <SelectItem value="AssociationEvent">Association Event</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Action */}
          {needsAction && (
            <div className="space-y-1.5">
              <Label>Action</Label>
              <Select value={form.action} onValueChange={(v) => update({ action: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACTIONS.map((a) => (
                    <SelectItem key={a} value={a}>{a}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* EPC List (ObjectEvent, TransactionEvent) */}
          {needsEpcList && (
            <div className="space-y-1.5">
              <Label>EPCs (comma-separated)</Label>
              <Input
                value={form.epcList}
                onChange={(e) => update({ epcList: e.target.value })}
                placeholder="urn:epc:id:sgtin:0614141.107346.2017, ..."
              />
            </div>
          )}

          {/* Parent ID + Child EPCs (Aggregation, Association) */}
          {needsParent && (
            <div className="space-y-1.5">
              <Label>Parent ID</Label>
              <Input
                value={form.parentId}
                onChange={(e) => update({ parentId: e.target.value })}
                placeholder="urn:epc:id:sscc:0614141.1234567890"
              />
            </div>
          )}
          {needsChildEpcs && (
            <div className="space-y-1.5">
              <Label>Child EPCs (comma-separated)</Label>
              <Input
                value={form.childEpcs}
                onChange={(e) => update({ childEpcs: e.target.value })}
                placeholder="urn:epc:id:sgtin:..., ..."
              />
            </div>
          )}

          {/* Transformation lists */}
          {needsTransformLists && (
            <>
              <div className="space-y-1.5">
                <Label>Input EPCs (comma-separated)</Label>
                <Input
                  value={form.inputEpcList}
                  onChange={(e) => update({ inputEpcList: e.target.value })}
                  placeholder="urn:epc:id:sgtin:..., ..."
                />
              </div>
              <div className="space-y-1.5">
                <Label>Output EPCs (comma-separated)</Label>
                <Input
                  value={form.outputEpcList}
                  onChange={(e) => update({ outputEpcList: e.target.value })}
                  placeholder="urn:epc:id:sgtin:..., ..."
                />
              </div>
            </>
          )}

          {/* Common fields */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Business Step</Label>
              <Select
                value={form.bizStep || 'none'}
                onValueChange={(v) => update({ bizStep: v === 'none' ? '' : v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Optional" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {BIZ_STEPS.map((s) => (
                    <SelectItem key={s} value={s}>{capitalize(s)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Disposition</Label>
              <Select
                value={form.disposition || 'none'}
                onValueChange={(v) => update({ disposition: v === 'none' ? '' : v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Optional" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {DISPOSITIONS.map((d) => (
                    <SelectItem key={d} value={d}>{capitalize(d)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Read Point</Label>
              <Input
                value={form.readPoint}
                onChange={(e) => update({ readPoint: e.target.value })}
                placeholder="urn:epc:id:sgln:..."
              />
            </div>
            <div className="space-y-1.5">
              <Label>Business Location</Label>
              <Input
                value={form.bizLocation}
                onChange={(e) => update({ bizLocation: e.target.value })}
                placeholder="urn:epc:id:sgln:..."
              />
            </div>
          </div>

          {/* Sensor Data (collapsible) */}
          <div className="space-y-2">
            <button
              type="button"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setShowSensor((prev) => !prev)}
            >
              {showSensor ? '- Hide Sensor Data' : '+ Add Sensor Data'}
            </button>
            {showSensor && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Device ID</Label>
                  <Input
                    value={form.sensorDeviceId}
                    onChange={(e) => update({ sensorDeviceId: e.target.value })}
                    placeholder="urn:epc:id:giai:..."
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Sensor Type</Label>
                  <Input
                    value={form.sensorType}
                    onChange={(e) => update({ sensorType: e.target.value })}
                    placeholder="gs1:Temperature"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Value</Label>
                  <Input
                    type="number"
                    value={form.sensorValue}
                    onChange={(e) => update({ sensorValue: e.target.value })}
                    placeholder="26.5"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Unit of Measure</Label>
                  <Input
                    value={form.sensorUom}
                    onChange={(e) => update({ sensorUom: e.target.value })}
                    placeholder="CEL"
                  />
                </div>
              </div>
            )}
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {(mutation.error as Error).message}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? 'Capturing...' : 'Capture Event'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Build EPCIS event payload from form state
// ---------------------------------------------------------------------------

function splitEpcs(csv: string): string[] {
  return csv.split(',').map((s) => s.trim()).filter(Boolean);
}

function buildEvent(form: typeof DEFAULT_STATE): Record<string, unknown> {
  const now = new Date();
  const base: Record<string, unknown> = {
    type: form.eventType,
    eventTime: now.toISOString(),
    eventTimeZoneOffset: formatTimezoneOffset(now.getTimezoneOffset()),
  };

  if (form.bizStep) base.bizStep = form.bizStep;
  if (form.disposition) base.disposition = form.disposition;
  if (form.readPoint) base.readPoint = form.readPoint;
  if (form.bizLocation) base.bizLocation = form.bizLocation;

  switch (form.eventType) {
    case 'ObjectEvent':
      base.action = form.action;
      base.epcList = splitEpcs(form.epcList);
      break;
    case 'AggregationEvent':
      base.action = form.action;
      if (form.parentId) base.parentID = form.parentId;
      base.childEPCs = splitEpcs(form.childEpcs);
      break;
    case 'TransactionEvent':
      base.action = form.action;
      base.epcList = splitEpcs(form.epcList);
      base.bizTransactionList = [];
      break;
    case 'TransformationEvent':
      base.inputEPCList = splitEpcs(form.inputEpcList);
      base.outputEPCList = splitEpcs(form.outputEpcList);
      break;
    case 'AssociationEvent':
      base.action = form.action;
      if (form.parentId) base.parentID = form.parentId;
      base.childEPCs = splitEpcs(form.childEpcs);
      break;
  }

  // Sensor data
  if (form.sensorType && form.sensorValue) {
    base.sensorElementList = [{
      sensorMetadata: form.sensorDeviceId ? { deviceID: form.sensorDeviceId } : undefined,
      sensorReport: [{
        type: form.sensorType,
        value: parseFloat(form.sensorValue),
        uom: form.sensorUom || undefined,
      }],
    }];
  }

  return base;
}

function formatTimezoneOffset(offsetMinutes: number): string {
  const sign = offsetMinutes <= 0 ? '+' : '-';
  const abs = Math.abs(offsetMinutes);
  const h = String(Math.floor(abs / 60)).padStart(2, '0');
  const m = String(abs % 60).padStart(2, '0');
  return `${sign}${h}:${m}`;
}
