using System.Text.Json.Serialization;
using TagDataTranslation;

var builder = WebApplication.CreateBuilder(args);
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
});

var app = builder.Build();

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapPost("/v1/encode", (EncodeRequest request) =>
{
    if (!string.Equals(request.TdsScheme, "sgtin++", StringComparison.OrdinalIgnoreCase))
    {
        return Results.BadRequest(new ErrorResponse("unsupported_scheme", "Only sgtin++ is supported"));
    }

    if (request.TagLength is not (96 or 198))
    {
        return Results.BadRequest(new ErrorResponse("invalid_tag_length", "tagLength must be 96 or 198"));
    }

    var digitalLink = request.DigitalLink;
    if (string.IsNullOrWhiteSpace(digitalLink))
    {
        if (string.IsNullOrWhiteSpace(request.Hostname) ||
            string.IsNullOrWhiteSpace(request.Gtin) ||
            string.IsNullOrWhiteSpace(request.Serial))
        {
            return Results.BadRequest(
                new ErrorResponse(
                    "missing_input",
                    "Provide digitalLink or hostname+gtin+serial"
                )
            );
        }

        digitalLink = BuildDigitalLink(request.Hostname!, request.Gtin!, request.Serial!);
    }

    var parameters = BuildParameters(request.Filter, request.Gs1CompanyPrefixLength, request.TagLength);
    var engine = new TDTEngine();

    if (!engine.TryTranslate(
            digitalLink!,
            parameters,
            "BINARY",
            out var binary,
            out var errorCode
        ) || string.IsNullOrWhiteSpace(binary))
    {
        return Results.UnprocessableEntity(
            new ErrorResponse(
                "encode_failed",
                $"Failed translating to binary ({errorCode ?? "unknown"})"
            )
        );
    }

    var epcHex = engine.BinaryToHex(binary!);
    var details = engine.TranslateDetails(epcHex, $"tagLength={request.TagLength}", "TAG_ENCODING");
    var fields = ToDictionary(details.Fields);

    var hostname = ExtractHostname(fields, digitalLink!);
    var gtin = GetField(fields, "gtin") ?? request.Gtin;
    var serial = GetField(fields, "serial") ?? request.Serial;
    var outputDigitalLink = GetField(fields, "digitalLinkURI");
    if (string.IsNullOrWhiteSpace(outputDigitalLink) &&
        !string.IsNullOrWhiteSpace(hostname) &&
        !string.IsNullOrWhiteSpace(gtin) &&
        !string.IsNullOrWhiteSpace(serial))
    {
        outputDigitalLink = BuildDigitalLink(hostname!, gtin!, serial!);
    }

    var response = new EncodeResponse(
        TdsScheme: "sgtin++",
        TagLength: request.TagLength,
        EpcHex: epcHex,
        TagUri: GetField(fields, "tagURI"),
        PureIdentityUri: GetField(fields, "pureIdentityURI"),
        DigitalLink: outputDigitalLink,
        Hostname: hostname,
        Gtin: gtin,
        Serial: serial,
        Fields: fields
    );
    return Results.Ok(response);
});

app.MapPost("/v1/decode", (DecodeRequest request) =>
{
    if (request.TagLength is not (96 or 198))
    {
        return Results.BadRequest(new ErrorResponse("invalid_tag_length", "tagLength must be 96 or 198"));
    }

    if (string.IsNullOrWhiteSpace(request.EpcHex))
    {
        return Results.BadRequest(new ErrorResponse("missing_epc", "epcHex is required"));
    }

    var engine = new TDTEngine();
    var normalizedHex = request.EpcHex.Trim().ToLowerInvariant();
    object details;
    try
    {
        details = engine.TranslateDetails(normalizedHex, $"tagLength={request.TagLength}", "TAG_ENCODING");
    }
    catch (Exception ex)
    {
        return Results.UnprocessableEntity(new ErrorResponse("decode_failed", ex.Message));
    }

    var detailsFieldsProperty = details.GetType().GetProperty("Fields");
    var fields = ToDictionary(detailsFieldsProperty?.GetValue(details));
    var hostname = ExtractHostname(fields, null);
    var gtin = GetField(fields, "gtin");
    var serial = GetField(fields, "serial");
    var digitalLink = GetField(fields, "digitalLinkURI");
    if (string.IsNullOrWhiteSpace(digitalLink) &&
        !string.IsNullOrWhiteSpace(hostname) &&
        !string.IsNullOrWhiteSpace(gtin) &&
        !string.IsNullOrWhiteSpace(serial))
    {
        digitalLink = BuildDigitalLink(hostname!, gtin!, serial!);
    }

    var response = new DecodeResponse(
        TdsScheme: "sgtin++",
        TagLength: request.TagLength,
        EpcHex: normalizedHex,
        TagUri: GetField(fields, "tagURI"),
        PureIdentityUri: GetField(fields, "pureIdentityURI"),
        DigitalLink: digitalLink,
        Hostname: hostname,
        Gtin: gtin,
        Serial: serial,
        Fields: fields
    );
    return Results.Ok(response);
});

app.Run();

static string BuildParameters(int filter, int? gs1CompanyPrefixLength, int tagLength)
{
    var parts = new List<string>
    {
        $"filter={filter}",
        $"tagLength={tagLength}"
    };
    if (gs1CompanyPrefixLength is not null)
    {
        parts.Add($"gs1companyprefixlength={gs1CompanyPrefixLength.Value}");
    }
    return string.Join(";", parts);
}

static string BuildDigitalLink(string hostname, string gtin, string serial)
{
    return $"https://{hostname.Trim().ToLowerInvariant()}/01/{Uri.EscapeDataString(gtin)}/21/{Uri.EscapeDataString(serial)}";
}

static string? GetField(Dictionary<string, string> fields, string key)
{
    return fields.TryGetValue(key, out var value) ? value : null;
}

static Dictionary<string, string> ToDictionary(object? fieldsObj)
{
    var output = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    if (fieldsObj is null)
    {
        return output;
    }

    if (fieldsObj is IEnumerable<KeyValuePair<string, string>> strPairs)
    {
        foreach (var (key, value) in strPairs)
        {
            output[key] = value;
        }
        return output;
    }

    if (fieldsObj is IEnumerable<KeyValuePair<string, object>> objPairs)
    {
        foreach (var (key, value) in objPairs)
        {
            output[key] = value?.ToString() ?? string.Empty;
        }
        return output;
    }

    var enumerable = fieldsObj as System.Collections.IEnumerable;
    if (enumerable is null)
    {
        return output;
    }
    foreach (var item in enumerable)
    {
        var itemType = item?.GetType();
        if (itemType is null)
        {
            continue;
        }
        var keyProp = itemType.GetProperty("Key");
        var valueProp = itemType.GetProperty("Value");
        var key = keyProp?.GetValue(item)?.ToString();
        if (string.IsNullOrWhiteSpace(key))
        {
            continue;
        }
        var value = valueProp?.GetValue(item)?.ToString() ?? string.Empty;
        output[key] = value;
    }
    return output;
}

static string? ExtractHostname(Dictionary<string, string> fields, string? digitalLink)
{
    var hostname = GetField(fields, "hostname")
                   ?? GetField(fields, "domain")
                   ?? GetField(fields, "host");
    if (!string.IsNullOrWhiteSpace(hostname))
    {
        return hostname.Trim().ToLowerInvariant();
    }

    if (!string.IsNullOrWhiteSpace(digitalLink) &&
        Uri.TryCreate(digitalLink, UriKind.Absolute, out var uri))
    {
        return uri.Host.ToLowerInvariant();
    }

    var fromFields = GetField(fields, "digitalLinkURI");
    if (!string.IsNullOrWhiteSpace(fromFields) &&
        Uri.TryCreate(fromFields, UriKind.Absolute, out var dlUri))
    {
        return dlUri.Host.ToLowerInvariant();
    }

    return null;
}

internal sealed record EncodeRequest(
    string TdsScheme,
    string? DigitalLink,
    string? Hostname,
    string? Gtin,
    string? Serial,
    int TagLength = 96,
    int Filter = 3,
    int? Gs1CompanyPrefixLength = null
);

internal sealed record DecodeRequest(
    string EpcHex,
    int TagLength = 96
);

internal sealed record EncodeResponse(
    string TdsScheme,
    int TagLength,
    string EpcHex,
    string? TagUri,
    string? PureIdentityUri,
    string? DigitalLink,
    string? Hostname,
    string? Gtin,
    string? Serial,
    Dictionary<string, string> Fields
);

internal sealed record DecodeResponse(
    string TdsScheme,
    int TagLength,
    string EpcHex,
    string? TagUri,
    string? PureIdentityUri,
    string? DigitalLink,
    string? Hostname,
    string? Gtin,
    string? Serial,
    Dictionary<string, string> Fields
);

internal sealed record ErrorResponse(string Code, string Message);
