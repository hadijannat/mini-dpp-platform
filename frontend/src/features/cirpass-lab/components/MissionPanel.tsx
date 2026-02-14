import { useMemo, useState } from 'react';
import type { CirpassLevel, CirpassLevelKey } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type {
  AccessLevelPayload,
  CreateLevelPayload,
  DeactivateLevelPayload,
  TransferLevelPayload,
  UpdateLevelPayload,
} from '../machines/cirpassMachine';

interface MissionPanelProps {
  currentLevel: CirpassLevelKey;
  levels: CirpassLevel[];
  onSubmit: (
    level: CirpassLevelKey,
    payload:
      | CreateLevelPayload
      | AccessLevelPayload
      | UpdateLevelPayload
      | TransferLevelPayload
      | DeactivateLevelPayload,
  ) => void;
  onHint: (level: CirpassLevelKey) => void;
}

const hintText: Record<CirpassLevelKey, string> = {
  create: 'Include identifier, material composition, and positive carbon footprint.',
  access: 'Consumer and authority must both pass, with restricted fields masked for consumer.',
  update: 'Provide old/new hashes and a non-empty repair event without hash collision.',
  transfer: 'From and to actors must differ, and confidentiality must remain enabled.',
  deactivate: 'Set lifecycle to end_of_life, provide recovered materials, and spawn next passport.',
};

export default function MissionPanel({ currentLevel, levels, onSubmit, onHint }: MissionPanelProps) {
  const [createPayload, setCreatePayload] = useState<CreateLevelPayload>({
    identifier: '',
    materialComposition: '',
    carbonFootprint: null,
  });
  const [accessPayload, setAccessPayload] = useState<AccessLevelPayload>({
    consumerViewEnabled: false,
    authorityCredentialValidated: false,
    restrictedFieldsHiddenFromConsumer: false,
  });
  const [updatePayload, setUpdatePayload] = useState<UpdateLevelPayload>({
    previousHash: '',
    newEventHash: '',
    repairEvent: '',
  });
  const [transferPayload, setTransferPayload] = useState<TransferLevelPayload>({
    fromActor: '',
    toActor: '',
    confidentialityMaintained: false,
  });
  const [deactivatePayload, setDeactivatePayload] = useState<DeactivateLevelPayload>({
    lifecycleStatus: 'active',
    recoveredMaterials: '',
    spawnNextPassport: false,
  });

  const levelContent = useMemo(
    () => levels.find((entry) => entry.level === currentLevel),
    [currentLevel, levels],
  );

  return (
    <section className="rounded-3xl border border-landing-ink/15 bg-white/85 p-5 shadow-[0_24px_40px_-34px_rgba(17,37,49,0.65)]">
      <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">Mission Control</p>
      <h3 className="mt-2 font-display text-2xl font-semibold text-landing-ink" data-testid="cirpass-current-level">
        {currentLevel.toUpperCase()}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-landing-muted">
        {levelContent?.objective ?? 'Complete this step to continue the loop.'}
      </p>

      <div className="mt-4 rounded-2xl border border-landing-ink/12 bg-landing-surface-0/70 p-4">
        {currentLevel === 'create' && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="create-identifier">Identifier</Label>
              <Input
                id="create-identifier"
                value={createPayload.identifier}
                onChange={(event) =>
                  setCreatePayload((prev) => ({ ...prev, identifier: event.target.value }))
                }
                data-testid="cirpass-create-identifier"
              />
            </div>
            <div>
              <Label htmlFor="create-material">Material composition</Label>
              <Textarea
                id="create-material"
                value={createPayload.materialComposition}
                onChange={(event) =>
                  setCreatePayload((prev) => ({ ...prev, materialComposition: event.target.value }))
                }
                data-testid="cirpass-create-material"
              />
            </div>
            <div>
              <Label htmlFor="create-carbon">Carbon footprint (kg CO2e)</Label>
              <Input
                id="create-carbon"
                type="number"
                value={createPayload.carbonFootprint ?? ''}
                onChange={(event) =>
                  setCreatePayload((prev) => ({
                    ...prev,
                    carbonFootprint:
                      event.target.value.trim() === '' ? null : Number.parseFloat(event.target.value),
                  }))
                }
                data-testid="cirpass-create-carbon"
              />
            </div>
          </div>
        )}

        {currentLevel === 'access' && (
          <div className="space-y-3 text-sm text-landing-ink">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={accessPayload.consumerViewEnabled}
                onChange={(event) =>
                  setAccessPayload((prev) => ({
                    ...prev,
                    consumerViewEnabled: event.target.checked,
                  }))
                }
                data-testid="cirpass-access-consumer"
              />
              Consumer default access enabled
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={accessPayload.authorityCredentialValidated}
                onChange={(event) =>
                  setAccessPayload((prev) => ({
                    ...prev,
                    authorityCredentialValidated: event.target.checked,
                  }))
                }
                data-testid="cirpass-access-authority"
              />
              Authority credential validated
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={accessPayload.restrictedFieldsHiddenFromConsumer}
                onChange={(event) =>
                  setAccessPayload((prev) => ({
                    ...prev,
                    restrictedFieldsHiddenFromConsumer: event.target.checked,
                  }))
                }
                data-testid="cirpass-access-restricted"
              />
              Restricted fields hidden from consumer view
            </label>
          </div>
        )}

        {currentLevel === 'update' && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="update-prev">Previous hash</Label>
              <Input
                id="update-prev"
                value={updatePayload.previousHash}
                onChange={(event) =>
                  setUpdatePayload((prev) => ({ ...prev, previousHash: event.target.value }))
                }
                data-testid="cirpass-update-prev-hash"
              />
            </div>
            <div>
              <Label htmlFor="update-next">New event hash</Label>
              <Input
                id="update-next"
                value={updatePayload.newEventHash}
                onChange={(event) =>
                  setUpdatePayload((prev) => ({ ...prev, newEventHash: event.target.value }))
                }
                data-testid="cirpass-update-new-hash"
              />
            </div>
            <div>
              <Label htmlFor="update-event">Repair event</Label>
              <Textarea
                id="update-event"
                value={updatePayload.repairEvent}
                onChange={(event) =>
                  setUpdatePayload((prev) => ({ ...prev, repairEvent: event.target.value }))
                }
                data-testid="cirpass-update-repair-event"
              />
            </div>
          </div>
        )}

        {currentLevel === 'transfer' && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="transfer-from">From actor</Label>
              <Input
                id="transfer-from"
                value={transferPayload.fromActor}
                onChange={(event) =>
                  setTransferPayload((prev) => ({ ...prev, fromActor: event.target.value }))
                }
                data-testid="cirpass-transfer-from"
              />
            </div>
            <div>
              <Label htmlFor="transfer-to">To actor</Label>
              <Input
                id="transfer-to"
                value={transferPayload.toActor}
                onChange={(event) =>
                  setTransferPayload((prev) => ({ ...prev, toActor: event.target.value }))
                }
                data-testid="cirpass-transfer-to"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-landing-ink">
              <input
                type="checkbox"
                checked={transferPayload.confidentialityMaintained}
                onChange={(event) =>
                  setTransferPayload((prev) => ({
                    ...prev,
                    confidentialityMaintained: event.target.checked,
                  }))
                }
                data-testid="cirpass-transfer-confidentiality"
              />
              Confidentiality boundary preserved
            </label>
          </div>
        )}

        {currentLevel === 'deactivate' && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="deactivate-status">Lifecycle status</Label>
              <select
                id="deactivate-status"
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={deactivatePayload.lifecycleStatus}
                onChange={(event) =>
                  setDeactivatePayload((prev) => ({
                    ...prev,
                    lifecycleStatus: event.target.value,
                  }))
                }
                data-testid="cirpass-deactivate-status"
              >
                <option value="active">active</option>
                <option value="end_of_life">end_of_life</option>
              </select>
            </div>
            <div>
              <Label htmlFor="deactivate-materials">Recovered materials</Label>
              <Textarea
                id="deactivate-materials"
                value={deactivatePayload.recoveredMaterials}
                onChange={(event) =>
                  setDeactivatePayload((prev) => ({
                    ...prev,
                    recoveredMaterials: event.target.value,
                  }))
                }
                data-testid="cirpass-deactivate-materials"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-landing-ink">
              <input
                type="checkbox"
                checked={deactivatePayload.spawnNextPassport}
                onChange={(event) =>
                  setDeactivatePayload((prev) => ({
                    ...prev,
                    spawnNextPassport: event.target.checked,
                  }))
                }
                data-testid="cirpass-deactivate-spawn"
              />
              Spawn material insight for next passport
            </label>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          className="rounded-full px-5"
          onClick={() => {
            if (currentLevel === 'create') {
              onSubmit('create', createPayload);
              return;
            }
            if (currentLevel === 'access') {
              onSubmit('access', accessPayload);
              return;
            }
            if (currentLevel === 'update') {
              onSubmit('update', updatePayload);
              return;
            }
            if (currentLevel === 'transfer') {
              onSubmit('transfer', transferPayload);
              return;
            }
            onSubmit('deactivate', deactivatePayload);
          }}
          data-testid="cirpass-level-submit"
        >
          Validate & Continue
        </Button>
        <Button
          type="button"
          variant="outline"
          className="rounded-full px-5"
          onClick={() => onHint(currentLevel)}
          data-testid="cirpass-level-hint"
        >
          Use Hint
        </Button>
      </div>

      <p className="mt-3 text-xs font-medium text-landing-muted">Hint: {hintText[currentLevel]}</p>
    </section>
  );
}
