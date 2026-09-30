// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
using System.Runtime.InteropServices;
namespace DanceRudiments;

/// <summary>All default movements, sampled by the original C++ library.</summary>
public static class Rudiments
{
    public const int PipsPerBeat = 64;
    public const string MusicUrl = "https://kieransimkin.co.uk/my-songs/";
    private static readonly Lazy<IReadOnlyList<RudimentInfo>> Items = new(ReadCatalogue);
    public static string NativeVersion
    {
        get { NativeMethods.EnsureCompatible(); return Marshal.PtrToStringUTF8(NativeMethods.Version())!; }
    }
    public static IReadOnlyList<RudimentInfo> Catalogue => Items.Value;
    private static IReadOnlyList<RudimentInfo> ReadCatalogue()
    {
        NativeMethods.EnsureCompatible();
        NativeMethods.Check(NativeMethods.Count(out uint count));
        var items = new RudimentInfo[checked((int)count)];
        for (uint i = 0; i < count; ++i)
        { NativeMethods.Check(NativeMethods.Get(i, out var info)); items[i] = info.Copy(); }
        return Array.AsReadOnly(items);
    }
    /// <summary>Sample at an integer pip. Negative positions wrap to this movement's loop.</summary>
    public static Offset3 Sample(string name, int pipCount)
    {
        NativeMethods.EnsureCompatible(); NativeMethods.CheckName(name);
        NativeMethods.Check(NativeMethods.Sample(name, pipCount, out var result));
        return result;
    }
    /// <summary>Fill a span in one P/Invoke call, with overflow-safe native wrapping.</summary>
    public static unsafe void SampleInto(string name, int startPip, Span<Offset3> destination, int stepPips = 1)
    {
        NativeMethods.EnsureCompatible(); NativeMethods.CheckName(name);
        if (destination.Length > PatternLibrary.MaxSamples) throw new ArgumentOutOfRangeException(nameof(destination));
        fixed (Offset3* values = destination)
            NativeMethods.Check(NativeMethods.SampleMany(name, startPip, stepPips, (uint)destination.Length, values));
    }
    public static Offset3[] SampleMany(string name, int startPip, int count, int stepPips = 1)
    {
        if (count < 0 || count > PatternLibrary.MaxSamples) throw new ArgumentOutOfRangeException(nameof(count));
        var result = new Offset3[count]; SampleInto(name, startPip, result, stepPips); return result;
    }
    /// <summary>Convert absolute fixed-tempo time to a pip, floored and wrapped before int32 conversion.</summary>
    /// <remarks>For a tempo map, integrate musical beats instead. No animation is evaluated here.</remarks>
    public static int PipAtTime(double seconds, double bpm, int periodPips, double beatZeroSeconds = 0)
    {
        if (!double.IsFinite(seconds)) throw new ArgumentOutOfRangeException(nameof(seconds));
        if (!double.IsFinite(beatZeroSeconds)) throw new ArgumentOutOfRangeException(nameof(beatZeroSeconds));
        if (!double.IsFinite(bpm) || bpm <= 0) throw new ArgumentOutOfRangeException(nameof(bpm));
        if (periodPips <= 0 || periodPips > 65535) throw new ArgumentOutOfRangeException(nameof(periodPips));
        double absolute = (seconds - beatZeroSeconds) * (bpm / 60) * PipsPerBeat;
        if (!double.IsFinite(absolute) || Math.Abs(absolute) > 9007199254740991d)
            throw new ArgumentOutOfRangeException(nameof(seconds), "Time exceeds exact integer-pip precision.");
        double pip = Math.Floor(absolute) % periodPips;
        return (int)(pip < 0 ? pip + periodPips : pip);
    }
}
