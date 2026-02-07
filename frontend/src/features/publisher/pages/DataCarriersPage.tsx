import { useState, useEffect, useCallback } from 'react';
import { useAuth } from 'react-oidc-context';
import { QrCode, Download, RefreshCw, Link2, Copy, Check, Printer } from 'lucide-react';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface DPP {
    id: string;
    asset_ids: {
        manufacturerPartId?: string;
        serialNumber?: string;
    };
    status: string;
    created_at: string;
}

interface GS1DigitalLink {
    dpp_id: string;
    digital_link: string;
    gtin: string;
    serial: string;
    resolver_url: string;
}

type CarrierFormat = 'qr' | 'gs1_qr';
type OutputType = 'png' | 'svg' | 'pdf';

export default function DataCarriersPage() {
    const auth = useAuth();
    const token = auth.user?.access_token;

    const [dpps, setDpps] = useState<DPP[]>([]);
    const [selectedDpp, setSelectedDpp] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [gs1Link, setGs1Link] = useState<GS1DigitalLink | null>(null);
    const [copied, setCopied] = useState(false);

    // Carrier settings
    const [format, setFormat] = useState<CarrierFormat>('qr');
    const [outputType, setOutputType] = useState<OutputType>('png');
    const [size, setSize] = useState(400);
    const [foregroundColor, setForegroundColor] = useState('#000000');
    const [backgroundColor, setBackgroundColor] = useState('#FFFFFF');
    const [includeText, setIncludeText] = useState(true);

    // Preview state
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);

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
            // Handle both array and paginated response formats safely
            let dppList: DPP[] = [];
            if (Array.isArray(data)) {
                dppList = data;
            } else if (data && Array.isArray(data.items)) {
                dppList = data.items;
            } else if (data && Array.isArray(data.dpps)) {
                dppList = data.dpps;
            } else if (data && typeof data === 'object') {
                // Try to find any array property
                const arrayProp = Object.values(data).find((v) => Array.isArray(v));
                if (arrayProp) dppList = arrayProp as DPP[];
            }
            // Filter to only published DPPs
            const publishedDpps = dppList.filter(
                (d: DPP) => d.status === 'published'
            );
            setDpps(publishedDpps);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load DPPs');
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => {
        void loadDPPs();
    }, [loadDPPs]);

    const loadGS1Link = async (dppId: string) => {
        if (!token || !dppId) return;

        try {
            const response = await tenantApiFetch(`/qr/${dppId}/gs1`, {}, token);
            if (response.ok) {
                const data = await response.json();
                setGs1Link(data);
            }
        } catch (err) {
            console.error('Failed to load GS1 link:', err);
        }
    };

    const generatePreview = async () => {
        if (!token || !selectedDpp) return;
        setGenerating(true);
        setError(null);

        try {
            const response = await tenantApiFetch(
                `/qr/${selectedDpp}/carrier`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        format,
                        output_type: 'png', // Always use PNG for preview
                        size: Math.min(size, 600), // Limit preview size
                        foreground_color: foregroundColor,
                        background_color: backgroundColor,
                        include_text: includeText,
                    }),
                },
                token
            );

            if (response.ok) {
                const blob = await response.blob();
                // Revoke previous URL to prevent memory leak
                if (previewUrl) {
                    URL.revokeObjectURL(previewUrl);
                }
                const url = URL.createObjectURL(blob);
                setPreviewUrl(url);
            } else {
                const message = await getApiErrorMessage(response, 'Failed to generate preview');
                setError(message);
            }
        } catch (err) {
            setError('Failed to generate preview');
            console.error(err);
        } finally {
            setGenerating(false);
        }
    };

    const downloadCarrier = async () => {
        if (!token || !selectedDpp) return;
        setGenerating(true);

        try {
            const response = await tenantApiFetch(
                `/qr/${selectedDpp}/carrier`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        format,
                        output_type: outputType,
                        size,
                        foreground_color: foregroundColor,
                        background_color: backgroundColor,
                        include_text: includeText,
                    }),
                },
                token
            );

            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `carrier-${selectedDpp}.${outputType}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } else {
                const message = await getApiErrorMessage(response, 'Failed to download carrier');
                setError(message);
            }
        } catch (err) {
            setError('Failed to download carrier');
            console.error(err);
        } finally {
            setGenerating(false);
        }
    };

    const copyGS1Link = () => {
        if (gs1Link) {
            navigator.clipboard.writeText(gs1Link.digital_link);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const handleDppSelect = (dppId: string) => {
        setSelectedDpp(dppId);
        // Revoke previous preview URL when changing DPP
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
        setPreviewUrl(null);
        setGs1Link(null);
        if (dppId) {
            loadGS1Link(dppId);
        }
    };

    // Cleanup blob URL on unmount
    useEffect(() => {
        return () => {
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }
        };
    }, [previewUrl]);

    const selectedDppData = dpps.find((d) => d.id === selectedDpp);

    return (
        <div className="space-y-6">
            <PageHeader
                title="Data Carriers"
                description="Generate QR codes and GS1 Digital Links for product identification"
                actions={
                    <Button variant="outline" onClick={loadDPPs} disabled={loading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                }
            />

            {error && <ErrorBanner message={error} />}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Settings Panel */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Carrier Settings</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* DPP Selection */}
                        <div className="space-y-2">
                            <Label>Select Published DPP</Label>
                            <select
                                value={selectedDpp}
                                onChange={(e) => handleDppSelect(e.target.value)}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                            >
                                <option value="">-- Select a DPP --</option>
                                {dpps.map((dpp) => (
                                    <option key={dpp.id} value={dpp.id}>
                                        {dpp.asset_ids?.manufacturerPartId || dpp.id.slice(0, 8)} -{' '}
                                        {dpp.asset_ids?.serialNumber || 'No Serial'}
                                    </option>
                                ))}
                            </select>
                            {dpps.length === 0 && !loading && (
                                <p className="text-sm text-muted-foreground">
                                    No published DPPs available. Publish a DPP first.
                                </p>
                            )}
                        </div>

                        {/* Format Selection */}
                        <div className="space-y-2">
                            <Label>Carrier Format</Label>
                            <div className="flex gap-4">
                                <label className="flex items-center">
                                    <input
                                        type="radio"
                                        name="format"
                                        value="qr"
                                        checked={format === 'qr'}
                                        onChange={() => setFormat('qr')}
                                        className="mr-2"
                                    />
                                    <span className="text-sm">Standard QR</span>
                                </label>
                                <label className="flex items-center">
                                    <input
                                        type="radio"
                                        name="format"
                                        value="gs1_qr"
                                        checked={format === 'gs1_qr'}
                                        onChange={() => setFormat('gs1_qr')}
                                        className="mr-2"
                                    />
                                    <span className="text-sm">GS1 Digital Link</span>
                                </label>
                            </div>
                        </div>

                        {/* Output Type */}
                        <div className="space-y-2">
                            <Label>Output Format</Label>
                            <div className="flex gap-4">
                                {(['png', 'svg', 'pdf'] as OutputType[]).map((type) => (
                                    <label key={type} className="flex items-center">
                                        <input
                                            type="radio"
                                            name="outputType"
                                            value={type}
                                            checked={outputType === type}
                                            onChange={() => setOutputType(type)}
                                            className="mr-2"
                                        />
                                        <span className="text-sm uppercase">{type}</span>
                                    </label>
                                ))}
                            </div>
                        </div>

                        {/* Size */}
                        <div className="space-y-2">
                            <Label>Size: {size}px</Label>
                            <input
                                type="range"
                                min="100"
                                max="1000"
                                step="50"
                                value={size}
                                onChange={(e) => setSize(Number(e.target.value))}
                                className="w-full"
                            />
                        </div>

                        {/* Colors */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Foreground</Label>
                                <input
                                    type="color"
                                    value={foregroundColor}
                                    onChange={(e) => setForegroundColor(e.target.value)}
                                    className="w-full h-10 rounded cursor-pointer"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Background</Label>
                                <input
                                    type="color"
                                    value={backgroundColor}
                                    onChange={(e) => setBackgroundColor(e.target.value)}
                                    className="w-full h-10 rounded cursor-pointer"
                                />
                            </div>
                        </div>

                        {/* Include Text */}
                        <div className="flex items-center gap-3">
                            <Switch
                                checked={includeText}
                                onCheckedChange={setIncludeText}
                                id="include-text"
                            />
                            <Label htmlFor="include-text">Include product ID text below QR</Label>
                        </div>

                        {/* Actions */}
                        <div className="flex gap-3">
                            <Button
                                variant="outline"
                                className="flex-1"
                                onClick={generatePreview}
                                disabled={!selectedDpp || generating}
                            >
                                <QrCode className="h-4 w-4 mr-2" />
                                Preview
                            </Button>
                            <Button
                                className="flex-1"
                                onClick={downloadCarrier}
                                disabled={!selectedDpp || generating}
                            >
                                <Download className="h-4 w-4 mr-2" />
                                Download
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Preview Panel */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Preview</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Preview Image */}
                        <div className="border-2 border-dashed border-muted rounded-lg p-8 flex items-center justify-center min-h-[300px] bg-muted/30">
                            {generating ? (
                                <div className="text-center">
                                    <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-2" />
                                    <p className="text-muted-foreground">Generating...</p>
                                </div>
                            ) : previewUrl ? (
                                <img
                                    src={previewUrl}
                                    alt="QR Code Preview"
                                    className="max-w-full max-h-[300px]"
                                />
                            ) : (
                                <div className="text-center text-muted-foreground">
                                    <QrCode className="h-16 w-16 mx-auto mb-3" />
                                    <p>Select a DPP and click Preview</p>
                                </div>
                            )}
                        </div>

                        {/* GS1 Digital Link Info */}
                        {gs1Link && (
                            <Alert className="border-blue-200 bg-blue-50">
                                <Link2 className="h-4 w-4" />
                                <AlertDescription>
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-sm font-semibold text-blue-900">
                                            GS1 Digital Link
                                        </span>
                                        <button
                                            onClick={copyGS1Link}
                                            className="text-blue-600 hover:text-blue-800"
                                            title="Copy to clipboard"
                                        >
                                            {copied ? (
                                                <Check className="h-4 w-4" />
                                            ) : (
                                                <Copy className="h-4 w-4" />
                                            )}
                                        </button>
                                    </div>
                                    <code className="text-xs text-blue-800 break-all block">
                                        {gs1Link.digital_link}
                                    </code>
                                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-blue-700">
                                        <div>
                                            <span className="font-medium">GTIN:</span> {gs1Link.gtin}
                                        </div>
                                        <div>
                                            <span className="font-medium">Serial:</span> {gs1Link.serial}
                                        </div>
                                    </div>
                                </AlertDescription>
                            </Alert>
                        )}

                        {/* Selected DPP Info */}
                        {selectedDppData && (
                            <div className="p-4 bg-muted/50 rounded-lg">
                                <h3 className="text-sm font-semibold mb-2">
                                    Selected Product
                                </h3>
                                <dl className="grid grid-cols-2 gap-2 text-sm">
                                    <div>
                                        <dt className="text-muted-foreground">Part ID</dt>
                                        <dd className="font-medium">
                                            {selectedDppData.asset_ids?.manufacturerPartId || '-'}
                                        </dd>
                                    </div>
                                    <div>
                                        <dt className="text-muted-foreground">Serial</dt>
                                        <dd className="font-medium">
                                            {selectedDppData.asset_ids?.serialNumber || '-'}
                                        </dd>
                                    </div>
                                </dl>
                            </div>
                        )}

                        {/* Print Button */}
                        {previewUrl && (
                            <Button
                                variant="outline"
                                className="w-full"
                                onClick={() => window.print()}
                            >
                                <Printer className="h-4 w-4 mr-2" />
                                Print
                            </Button>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
