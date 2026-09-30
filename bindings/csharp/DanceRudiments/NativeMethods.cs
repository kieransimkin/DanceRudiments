// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;
namespace DanceRudiments;

internal sealed class SafeLibraryHandle : SafeHandleZeroOrMinusOneIsInvalid
{
    public SafeLibraryHandle() : base(true) { }
    protected override bool ReleaseHandle() { NativeMethods.Destroy(handle); return true; }
}

internal static unsafe class NativeMethods
{
    private const string Dll = "dancerudiments_native";
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly Lazy<bool> Compatible = new(() =>
    {
        if (AbiVersion() != 1 || PipsPerBeat() != 64)
            throw new NotSupportedException("Incompatible DanceRudiments C ABI. Install matching managed/native package files.");
        return true;
    });

    static NativeMethods()
    {
        // NuGet's runtime probing is the default. This explicit absolute-path
        // override is only for source development; it is not needed by consumers.
        NativeLibrary.SetDllImportResolver(typeof(NativeMethods).Assembly, Resolve);
    }
    private static nint Resolve(string name, Assembly assembly, DllImportSearchPath? paths)
    {
        if (name != Dll) return 0;
        string? path = Environment.GetEnvironmentVariable("DANCERUDIMENTS_NATIVE_LIBRARY");
        if (string.IsNullOrEmpty(path)) return 0;
        if (!Path.IsPathFullyQualified(path))
            throw new ArgumentException("DANCERUDIMENTS_NATIVE_LIBRARY must be an absolute filename.");
        return NativeLibrary.Load(path, assembly, paths);
    }
    internal static void EnsureCompatible() => _ = Compatible.Value;
    internal static void Check(int code)
    {
        if (code == 0) return;
        string text = Marshal.PtrToStringUTF8(LastError()) ?? "Native DanceRudiments error";
        Exception error = code switch
        {
            1 => new ArgumentException(text),
            2 => new ArgumentOutOfRangeException(null, text),
            3 => new OutOfMemoryException(text),
            _ => new InvalidOperationException(text)
        };
        throw error;
    }
    internal static void CheckName(string name)
    {
        ArgumentNullException.ThrowIfNull(name);
        if (name.Length == 0 || name.Contains('\0'))
            throw new ArgumentException("Pattern names must be nonempty and contain no NUL.", nameof(name));
        _ = StrictUtf8.GetByteCount(name);
    }
    internal static void CheckText(string text, string label)
    {
        ArgumentNullException.ThrowIfNull(text, label);
        if (text.Contains('\0')) throw new ArgumentException("Text must not contain NUL.", label);
        _ = StrictUtf8.GetByteCount(text);
    }
    // These fields are assigned by the native out-parameter marshaller.
#pragma warning disable CS0649
    [StructLayout(LayoutKind.Sequential)]
    internal struct Info
    {
        internal nint Name, Description;
        internal uint Period, Dimensions;
        internal readonly RudimentInfo Copy() => new(
            Marshal.PtrToStringUTF8(Name) ?? throw new InvalidOperationException("Missing native name"),
            Marshal.PtrToStringUTF8(Description) ?? throw new InvalidOperationException("Missing native description"),
            checked((int)Period), checked((int)Dimensions));
    }
#pragma warning restore CS0649
    [StructLayout(LayoutKind.Sequential)]
    internal struct Definition { internal nint Name, Description, Samples; internal uint Count; }

    internal static SafeLibraryHandle Create(IReadOnlyList<PatternDefinition> patterns)
    {
        EnsureCompatible();
        if (patterns.Count > PatternLibrary.MaxPatterns) throw new ArgumentException("Too many patterns.", nameof(patterns));
        long total = 0;
        for (int i = 0; i < patterns.Count; ++i)
        {
            ArgumentNullException.ThrowIfNull(patterns[i]);
            total += patterns[i].Values.Length;
        }
        if (total > PatternLibrary.MaxSamples) throw new ArgumentException("Too many samples.", nameof(patterns));
        var definitions = new Definition[patterns.Count];
        var pins = new GCHandle[patterns.Count];
        try
        {
            for (int i = 0; i < patterns.Count; ++i)
            {
                definitions[i].Name = Marshal.StringToCoTaskMemUTF8(patterns[i].Name);
                definitions[i].Description = Marshal.StringToCoTaskMemUTF8(patterns[i].Description);
                pins[i] = GCHandle.Alloc(patterns[i].Values, GCHandleType.Pinned);
                definitions[i].Samples = pins[i].AddrOfPinnedObject();
                definitions[i].Count = (uint)patterns[i].Values.Length;
            }
            fixed (Definition* values = definitions)
            {
                int status = CreateNative(values, (uint)definitions.Length, out SafeLibraryHandle handle);
                try { Check(status); return handle; }
                catch { handle.Dispose(); throw; }
            }
        }
        finally
        {
            for (int i = 0; i < patterns.Count; ++i)
            {
                if (pins[i].IsAllocated) pins[i].Free();
                Marshal.FreeCoTaskMem(definitions[i].Name);
                Marshal.FreeCoTaskMem(definitions[i].Description);
            }
        }
    }

    [DllImport(Dll, EntryPoint="dr_abi_version", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern uint AbiVersion();
    [DllImport(Dll, EntryPoint="dr_pips_per_beat", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern uint PipsPerBeat();
    [DllImport(Dll, EntryPoint="dr_version", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern nint Version();
    [DllImport(Dll, EntryPoint="dr_last_error", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    private static extern nint LastError();
    [DllImport(Dll, EntryPoint="dr_catalogue_count", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int Count(out uint count);
    [DllImport(Dll, EntryPoint="dr_catalogue_get", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int Get(uint index, out Info info);
    [DllImport(Dll, EntryPoint="dr_sample", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int Sample([MarshalAs(UnmanagedType.LPUTF8Str)] string name, int pip, out Offset3 value);
    [DllImport(Dll, EntryPoint="dr_sample_many", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int SampleMany([MarshalAs(UnmanagedType.LPUTF8Str)] string name,
        int start, int step, uint count, Offset3* values);
    [DllImport(Dll, EntryPoint="dr_library_create", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    private static extern int CreateNative(Definition* definitions, uint count, out SafeLibraryHandle library);
    [DllImport(Dll, EntryPoint="dr_library_destroy", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern void Destroy(nint library);
    [DllImport(Dll, EntryPoint="dr_library_count", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int Count(SafeLibraryHandle library, out uint count);
    [DllImport(Dll, EntryPoint="dr_library_get", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int Get(SafeLibraryHandle library, uint index, out Info info);
    [DllImport(Dll, EntryPoint="dr_library_sample", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int Sample(SafeLibraryHandle library,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string name, int pip, out Offset3 value);
    [DllImport(Dll, EntryPoint="dr_library_sample_many", CallingConvention=CallingConvention.Cdecl, ExactSpelling=true)]
    internal static extern int SampleMany(SafeLibraryHandle library,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string name, int start, int step, uint count, Offset3* values);
}
