// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
using DanceRudiments;

Console.WriteLine($"DanceRudiments {Rudiments.NativeVersion} · {Rudiments.Catalogue.Count} movements");
Console.WriteLine(Rudiments.MusicUrl);
var amen = Rudiments.Catalogue.Single(p => p.Name == "beat_amen_four_bar_bounce");
int pip = Rudiments.PipAtTime(seconds: 1.25, bpm: 140, periodPips: amen.PeriodPips);
Offset3 position = Rudiments.Sample(amen.Name, pip);
Console.WriteLine($"Amen at pip {pip}: {position}");
Console.WriteLine($"Previous pip: {Rudiments.Sample(amen.Name, -1)}");
Offset3[] loop = Rudiments.SampleMany(amen.Name, 0, amen.PeriodPips);
Console.WriteLine($"Full loop: {loop.Length} pips / {amen.PeriodBeats} beats");

// This demonstrates table ownership, not a new C# movement implementation.
using var bank = new PatternLibrary(new PatternDefinition("my_offset", "Authored table", new[]
{
    new Offset3(0, 0), new Offset3(.2, -.3), new Offset3(0, 0)
}));
Console.WriteLine($"Custom table sampled by C++: {bank.Sample("my_offset", 1)}");
if (args.Length > 0)
{
    using var compiled = PatternLibrary.Load(args[0]);
    Console.WriteLine($"Loaded bank: {compiled.Catalogue.Count} entries");
}
