// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
namespace DanceRudiments;

/// <summary>An immutable copy of an authored one-sample-per-pip table. It contains no C# motion evaluator.</summary>
public sealed class PatternDefinition
{
    public string Name { get; }
    public string Description { get; }
    public IReadOnlyList<Offset3> Samples { get; }
    internal Offset3[] Values { get; }
    public PatternDefinition(string name, string description, IReadOnlyList<Offset3> samples)
    {
        NativeMethods.CheckName(name); NativeMethods.CheckText(description, nameof(description));
        ArgumentNullException.ThrowIfNull(samples);
        if (samples.Count < 1 || samples.Count > 65535) throw new ArgumentOutOfRangeException(nameof(samples));
        if (name.Length > 128 || name[0] < 'a' || name[0] > 'z' ||
            name.Any(c => !(c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_')))
            throw new ArgumentException("Names must match [a-z][a-z0-9_]{0,127}.", nameof(name));
        Name = name; Description = description;
        Values = new Offset3[samples.Count];
        for (int i = 0; i < Values.Length; ++i)
        {
            var v = samples[i];
            if (!double.IsFinite(v.X) || !double.IsFinite(v.Y) || !double.IsFinite(v.Z) ||
                Math.Abs(v.X) > 1 || Math.Abs(v.Y) > 1 || Math.Abs(v.Z) > 1)
                throw new ArgumentException("Samples must be finite XYZ triples within [-1,1].", nameof(samples));
            Values[i] = v;
        }
        Samples = Array.AsReadOnly(Values);
    }
}
