// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
using System.Runtime.InteropServices;
namespace DanceRudiments;

/// <summary>A dimensionless, double-precision XYZ offset. Scale it in your renderer.</summary>
[StructLayout(LayoutKind.Sequential)]
public readonly struct Offset3 : IEquatable<Offset3>
{
    public readonly double X;
    public readonly double Y;
    public readonly double Z;
    public Offset3(double x, double y, double z = 0) { X = x; Y = y; Z = z; }
    public bool Equals(Offset3 other) => X.Equals(other.X) && Y.Equals(other.Y) && Z.Equals(other.Z);
    public override bool Equals(object? value) => value is Offset3 other && Equals(other);
    public override int GetHashCode() => HashCode.Combine(X, Y, Z);
    public static bool operator ==(Offset3 a, Offset3 b) => a.Equals(b);
    public static bool operator !=(Offset3 a, Offset3 b) => !a.Equals(b);
    public void Deconstruct(out double x, out double y, out double z) { x = X; y = Y; z = Z; }
    public override string ToString() => FormattableString.Invariant($"({X:R}, {Y:R}, {Z:R})");
}

/// <summary>Copied native metadata. Catalogue order matches C++, with no generated C# mirror.</summary>
public sealed record RudimentInfo(string Name, string Description, int PeriodPips, int Dimensions)
{
    public double PeriodBeats => PeriodPips / (double)Rudiments.PipsPerBeat;
}
