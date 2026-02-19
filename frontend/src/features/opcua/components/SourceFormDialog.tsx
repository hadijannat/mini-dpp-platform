import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  OPCUAAuthType,
  type OPCUASourceCreateInput,
  type OPCUASourceResponse,
} from '../lib/opcuaApi';

interface SourceFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: OPCUASourceCreateInput) => void;
  initialData?: OPCUASourceResponse | null;
  isPending?: boolean;
}

export function SourceFormDialog({
  open,
  onOpenChange,
  onSubmit,
  initialData,
  isPending,
}: SourceFormDialogProps) {
  const isEditing = !!initialData;

  const [name, setName] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [authType, setAuthType] = useState<OPCUAAuthType>(OPCUAAuthType.ANONYMOUS);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [securityPolicy, setSecurityPolicy] = useState('');
  const [securityMode, setSecurityMode] = useState('');

  useEffect(() => {
    if (open) {
      if (initialData) {
        setName(initialData.name);
        setEndpointUrl(initialData.endpoint_url);
        setAuthType(initialData.auth_type);
        setUsername(initialData.username ?? '');
        setPassword('');
        setSecurityPolicy(initialData.security_policy ?? '');
        setSecurityMode(initialData.security_mode ?? '');
      } else {
        setName('');
        setEndpointUrl('');
        setAuthType(OPCUAAuthType.ANONYMOUS);
        setUsername('');
        setPassword('');
        setSecurityPolicy('');
        setSecurityMode('');
      }
    }
  }, [open, initialData]);

  function handleSubmit() {
    const data: OPCUASourceCreateInput = {
      name,
      endpointUrl,
      authType,
      securityPolicy: securityPolicy || null,
      securityMode: securityMode || null,
    };

    if (authType === OPCUAAuthType.USERNAME_PASSWORD) {
      data.username = username || null;
      if (password) {
        data.password = password;
      }
    }

    onSubmit(data);
  }

  const isValid = name.trim() !== '' && endpointUrl.trim() !== '';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Source' : 'Add OPC UA Source'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the OPC UA server connection settings.'
              : 'Configure a new OPC UA server connection for data ingestion.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="source-name">Name</Label>
            <Input
              id="source-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Production PLC"
            />
          </div>
          <div>
            <Label htmlFor="source-endpoint">Endpoint URL</Label>
            <Input
              id="source-endpoint"
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
              placeholder="opc.tcp://192.168.1.100:4840"
            />
          </div>
          <div>
            <Label htmlFor="source-auth-type">Auth Type</Label>
            <Select value={authType} onValueChange={(v) => setAuthType(v as OPCUAAuthType)}>
              <SelectTrigger id="source-auth-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={OPCUAAuthType.ANONYMOUS}>Anonymous</SelectItem>
                <SelectItem value={OPCUAAuthType.USERNAME_PASSWORD}>
                  Username &amp; Password
                </SelectItem>
                <SelectItem value={OPCUAAuthType.CERTIFICATE}>Certificate</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {authType === OPCUAAuthType.USERNAME_PASSWORD && (
            <>
              <div>
                <Label htmlFor="source-username">Username</Label>
                <Input
                  id="source-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="source-password">Password</Label>
                <Input
                  id="source-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={
                    isEditing && initialData?.has_password ? '(unchanged)' : undefined
                  }
                />
              </div>
            </>
          )}
          <div>
            <Label htmlFor="source-security-policy">Security Policy</Label>
            <Input
              id="source-security-policy"
              value={securityPolicy}
              onChange={(e) => setSecurityPolicy(e.target.value)}
              placeholder="http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256"
            />
          </div>
          <div>
            <Label htmlFor="source-security-mode">Security Mode</Label>
            <Input
              id="source-security-mode"
              value={securityMode}
              onChange={(e) => setSecurityMode(e.target.value)}
              placeholder="SignAndEncrypt"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!isValid || isPending}>
            {isPending
              ? isEditing
                ? 'Saving...'
                : 'Creating...'
              : isEditing
                ? 'Save Changes'
                : 'Create Source'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
