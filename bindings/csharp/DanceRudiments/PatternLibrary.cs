// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
using System.Text.Json;
namespace DanceRudiments;

/// <summary>An owned native bank. Use <c>using</c> or Dispose; SafeHandle also provides finalization.</summary>
public sealed class PatternLibrary : IDisposable
{
    public const int MaxPatterns = 1024;
    public const int MaxSamples = 1048576;
    public const int MaxJsonBytes = 128 * 1024 * 1024;
    private readonly SafeLibraryHandle handle;
    public IReadOnlyList<RudimentInfo> Catalogue { get; }

    public PatternLibrary(params PatternDefinition[] patterns)
    {
        ArgumentNullException.ThrowIfNull(patterns);
        // Snapshot the list before native creation. Individual definitions are immutable.
        handle = NativeMethods.Create((PatternDefinition[])patterns.Clone());
        try
        {
            NativeMethods.Check(NativeMethods.Count(handle, out uint count));
            var info = new RudimentInfo[checked((int)count)];
            for (uint i = 0; i < count; ++i)
            { NativeMethods.Check(NativeMethods.Get(handle, i, out var v)); info[i] = v.Copy(); }
            Catalogue = Array.AsReadOnly(info);
        }
        catch { handle.Dispose(); throw; }
    }
    /// <summary>Samples in C++; concurrent readers are allowed. Disposed calls fail rather than reading freed memory.</summary>
    public Offset3 Sample(string name, int pipCount)
    {
        ObjectDisposedException.ThrowIf(handle.IsClosed, this); NativeMethods.CheckName(name);
        NativeMethods.Check(NativeMethods.Sample(handle, name, pipCount, out var value));
        return value;
    }
    public unsafe void SampleInto(string name, int startPip, Span<Offset3> destination, int stepPips = 1)
    {
        ObjectDisposedException.ThrowIf(handle.IsClosed, this); NativeMethods.CheckName(name);
        if (destination.Length > MaxSamples) throw new ArgumentOutOfRangeException(nameof(destination));
        fixed (Offset3* p = destination)
            NativeMethods.Check(NativeMethods.SampleMany(handle, name, startPip, stepPips, (uint)destination.Length, p));
    }
    public Offset3[] SampleMany(string name, int startPip, int count, int stepPips = 1)
    {
        if (count < 0 || count > MaxSamples) throw new ArgumentOutOfRangeException(nameof(count));
        var values = new Offset3[count]; SampleInto(name, startPip, values, stepPips); return values;
    }
    public void Dispose() => handle.Dispose();

    /// <summary>Load a compiled JSON pack produced by dancerudiments-compile. No Python runtime is used.</summary>
    public static PatternLibrary Load(string path)
    {
        ArgumentException.ThrowIfNullOrEmpty(path);
        using var stream = File.OpenRead(path);
        if (stream.Length > MaxJsonBytes) throw new ArgumentException("JSON pack is too large.", nameof(path));
        byte[] bytes = new byte[checked((int)stream.Length)];
        stream.ReadExactly(bytes);
        if (stream.ReadByte() != -1) throw new ArgumentException("JSON file changed during reading.", nameof(path));
        using var document = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 64 });
        return Parse(document.RootElement);
    }
    public static PatternLibrary FromJson(string json)
    {
        ArgumentNullException.ThrowIfNull(json);
        if (json.Length > MaxJsonBytes / 2) throw new ArgumentException("JSON pack is too large.", nameof(json));
        using var document = JsonDocument.Parse(json, new JsonDocumentOptions { MaxDepth = 64 });
        return Parse(document.RootElement);
    }
    private static void UniqueKeys(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            var keys = new HashSet<string>(StringComparer.Ordinal);
            foreach (var property in value.EnumerateObject())
            {
                if (!keys.Add(property.Name)) throw new ArgumentException("Duplicate JSON key: " + property.Name);
                UniqueKeys(property.Value);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
            foreach (var item in value.EnumerateArray()) UniqueKeys(item);
    }
    private static PatternLibrary Parse(JsonElement root)
    {
        UniqueKeys(root);
        try
        {
            if (root.GetProperty("format").GetString() != "dancerudiments.compiled-pack" ||
                root.GetProperty("schema_version").GetInt32() != 1 || root.GetProperty("pips_per_beat").GetInt32() != 64)
                throw new ArgumentException("Unsupported pack format, version or pip resolution.");
            var patterns = root.GetProperty("patterns");
            if (patterns.ValueKind != JsonValueKind.Array || patterns.GetArrayLength() < 1 || patterns.GetArrayLength() > MaxPatterns)
                throw new ArgumentException("A compiled pack requires 1..1024 patterns.");
            var definitions = new List<PatternDefinition>();
            int total = 0;
            foreach (var pattern in patterns.EnumerateArray())
            {
                string digest = pattern.GetProperty("source_sha256").GetString() ?? "";
                if (digest.Length != 64 || digest.Any(c => !(c is >= '0' and <= '9' or >= 'a' and <= 'f')))
                    throw new ArgumentException("Missing or invalid source_sha256.");
                if (pattern.GetProperty("provenance").ValueKind != JsonValueKind.Object ||
                    pattern.GetProperty("diagnostics").ValueKind != JsonValueKind.Object)
                    throw new ArgumentException("Missing provenance or diagnostics object.");
                int count = pattern.GetProperty("period_pips").GetInt32();
                if (count < 1 || count > 65535) throw new ArgumentException("Invalid pattern period.");
                total = checked(total + count);
                if (total > MaxSamples) throw new ArgumentException("Pattern pack exceeds the total sample limit.");
                var samples = pattern.GetProperty("samples");
                if (samples.ValueKind != JsonValueKind.Array || samples.GetArrayLength() != count)
                    throw new ArgumentException("Sample count does not match period_pips.");
                var values = new Offset3[count]; int i = 0;
                foreach (var xyz in samples.EnumerateArray())
                {
                    if (xyz.ValueKind != JsonValueKind.Array || xyz.GetArrayLength() != 3)
                        throw new ArgumentException("A sample must have three components.");
                    values[i++] = new Offset3(xyz[0].GetDouble(), xyz[1].GetDouble(), xyz[2].GetDouble());
                }
                definitions.Add(new PatternDefinition(pattern.GetProperty("name").GetString()!,
                    pattern.GetProperty("description").GetString()!, values));
            }
            return new PatternLibrary(definitions.ToArray());
        }
        catch (Exception error) when (error is KeyNotFoundException or InvalidOperationException or FormatException or OverflowException)
        { throw new ArgumentException("Malformed compiled movement pack.", nameof(root), error); }
    }
}
