import { useState, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import { QrCode, Download, RefreshCw, Link2, Copy, Check, Printer } from 'lucide-react';
import { apiFetch } from '@/lib/api';

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

    useEffect(() => {
        loadDPPs();
    }, [token]);

    const loadDPPs = async () => {
        if (!token) return;
        setLoading(true);
        setError(null);

        try {
            const response = await apiFetch('/api/v1/dpps', {}, token);
            if (response.ok) {
                const data = await response.json();
                // Handle both array and paginated response formats safely
                let dppList: DPP[] = [];
                if (Array.isArray(data)) {
                    dppList = data;
                } else if (data && Array.isArray(data.items)) {
                    dppList = data.items;
                } else if (data && typeof data === 'object') {
                    // Try to find any array property
                    const arrayProp = Object.values(data).find(v => Array.isArray(v));
                    if (arrayProp) dppList = arrayProp as DPP[];
                }
                // Filter to only published DPPs
                const publishedDpps = dppList.filter(
                    (d: DPP) => d.status === 'published'
                );
                setDpps(publishedDpps);
            } else {
                setError('Failed to load DPPs');
            }
        } catch (err) {
            setError('Failed to load DPPs');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const loadGS1Link = async (dppId: string) => {
        if (!token || !dppId) return;

        try {
            const response = await apiFetch(`/api/v1/qr/${dppId}/gs1`, {}, token);
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
            const response = await apiFetch(
                `/api/v1/qr/${selectedDpp}/carrier`,
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
                const url = URL.createObjectURL(blob);
                setPreviewUrl(url);
            } else {
                const err = await response.json();
                setError(err.detail || 'Failed to generate preview');
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
            const response = await apiFetch(
                `/api/v1/qr/${selectedDpp}/carrier`,
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
        setPreviewUrl(null);
        setGs1Link(null);
        if (dppId) {
            loadGS1Link(dppId);
        }
    };

    const selectedDppData = dpps.find((d) => d.id === selectedDpp);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Data Carriers</h1>
                    <p className="text-gray-600 mt-1">
                        Generate QR codes and GS1 Digital Links for product identification
                    </p>
                </div>
                <button
                    onClick={loadDPPs}
                    disabled={loading}
                    className="inline-flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                    <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                    {error}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Settings Panel */}
                <div className="bg-white rounded-lg shadow p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">
                        Carrier Settings
                    </h2>

                    {/* DPP Selection */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Select Published DPP
                        </label>
                        <select
                            value={selectedDpp}
                            onChange={(e) => handleDppSelect(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
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
                            <p className="text-sm text-gray-500 mt-1">
                                No published DPPs available. Publish a DPP first.
                            </p>
                        )}
                    </div>

                    {/* Format Selection */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Carrier Format
                        </label>
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
                                <span>Standard QR</span>
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
                                <span>GS1 Digital Link</span>
                            </label>
                        </div>
                    </div>

                    {/* Output Type */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Output Format
                        </label>
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
                                    <span className="uppercase">{type}</span>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Size */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Size: {size}px
                        </label>
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
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Foreground
                            </label>
                            <input
                                type="color"
                                value={foregroundColor}
                                onChange={(e) => setForegroundColor(e.target.value)}
                                className="w-full h-10 rounded cursor-pointer"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Background
                            </label>
                            <input
                                type="color"
                                value={backgroundColor}
                                onChange={(e) => setBackgroundColor(e.target.value)}
                                className="w-full h-10 rounded cursor-pointer"
                            />
                        </div>
                    </div>

                    {/* Include Text */}
                    <div className="mb-6">
                        <label className="flex items-center">
                            <input
                                type="checkbox"
                                checked={includeText}
                                onChange={(e) => setIncludeText(e.target.checked)}
                                className="mr-2"
                            />
                            <span className="text-sm font-medium text-gray-700">
                                Include product ID text below QR
                            </span>
                        </label>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-3">
                        <button
                            onClick={generatePreview}
                            disabled={!selectedDpp || generating}
                            className="flex-1 inline-flex items-center justify-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <QrCode className="h-4 w-4 mr-2" />
                            Preview
                        </button>
                        <button
                            onClick={downloadCarrier}
                            disabled={!selectedDpp || generating}
                            className="flex-1 inline-flex items-center justify-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Download className="h-4 w-4 mr-2" />
                            Download
                        </button>
                    </div>
                </div>

                {/* Preview Panel */}
                <div className="bg-white rounded-lg shadow p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Preview</h2>

                    {/* Preview Image */}
                    <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 flex items-center justify-center min-h-[300px] bg-gray-50">
                        {generating ? (
                            <div className="text-center">
                                <RefreshCw className="h-8 w-8 animate-spin text-gray-400 mx-auto mb-2" />
                                <p className="text-gray-500">Generating...</p>
                            </div>
                        ) : previewUrl ? (
                            <img
                                src={previewUrl}
                                alt="QR Code Preview"
                                className="max-w-full max-h-[300px]"
                            />
                        ) : (
                            <div className="text-center text-gray-400">
                                <QrCode className="h-16 w-16 mx-auto mb-3" />
                                <p>Select a DPP and click Preview</p>
                            </div>
                        )}
                    </div>

                    {/* GS1 Digital Link Info */}
                    {gs1Link && (
                        <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                                <h3 className="text-sm font-semibold text-blue-900 flex items-center">
                                    <Link2 className="h-4 w-4 mr-2" />
                                    GS1 Digital Link
                                </h3>
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
                        </div>
                    )}

                    {/* Selected DPP Info */}
                    {selectedDppData && (
                        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                            <h3 className="text-sm font-semibold text-gray-700 mb-2">
                                Selected Product
                            </h3>
                            <dl className="grid grid-cols-2 gap-2 text-sm">
                                <div>
                                    <dt className="text-gray-500">Part ID</dt>
                                    <dd className="font-medium">
                                        {selectedDppData.asset_ids?.manufacturerPartId || '-'}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-gray-500">Serial</dt>
                                    <dd className="font-medium">
                                        {selectedDppData.asset_ids?.serialNumber || '-'}
                                    </dd>
                                </div>
                            </dl>
                        </div>
                    )}

                    {/* Print Button */}
                    {previewUrl && (
                        <button
                            onClick={() => window.print()}
                            className="mt-4 w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                        >
                            <Printer className="h-4 w-4 mr-2" />
                            Print
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
