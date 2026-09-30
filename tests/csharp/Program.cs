// MIT. Kieran Simkin — https://kieransimkin.co.uk/my-songs/
using DanceRudiments;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Buffers.Binary;
using System.Security.Cryptography;

internal static class Program
{
    private static long checks;
    private static void Check(bool condition, string label)
    { ++checks; if (!condition) throw new Exception(label); }
    private static void Throws<T>(Action action) where T : Exception
    {
        ++checks;
        try { action(); } catch (T) { return; }
        throw new Exception("Expected " + typeof(T).Name);
    }
    private static string SampleHash(Offset3[] values)
    {
        using var h = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        Span<byte> row = stackalloc byte[24];
        foreach (var v in values)
        {
            BinaryPrimitives.WriteDoubleLittleEndian(row, v.X == 0 ? 0 : v.X);
            BinaryPrimitives.WriteDoubleLittleEndian(row[8..], v.Y == 0 ? 0 : v.Y);
            BinaryPrimitives.WriteDoubleLittleEndian(row[16..], v.Z == 0 ? 0 : v.Z);
            h.AppendData(row);
        }
        return Convert.ToHexString(h.GetHashAndReset()).ToLowerInvariant();
    }
    public static int Main(string[] args)
    {
        try
        {
            Check(Marshal.SizeOf<Offset3>() == 24, "XYZ ABI layout");
            var items = Rudiments.Catalogue;
            Check(items.Count > 15, "Native catalogue is present");
            Check(Rudiments.NativeVersion == typeof(Rudiments).Assembly.GetName().Version!.ToString(3), "Managed/native version agreement");
            Check(items.DistinctBy(i => i.Name).Count() == items.Count, "Unique names");
            Check(Rudiments.MusicUrl == "https://kieransimkin.co.uk/my-songs/", "Author link");
            foreach (var info in items)
            {
                Check(info.PeriodPips > 0 && info.Dimensions is >= 1 and <= 3, "Native metadata");
                var values = Rudiments.SampleMany(info.Name, 0, info.PeriodPips);
                for (int pip = 0; pip < values.Length; ++pip)
                {
                    Check(values[pip] == Rudiments.Sample(info.Name, pip), "Batch/single parity");
                    var v=values[pip];
                    Check(double.IsFinite(v.X) && double.IsFinite(v.Y) && double.IsFinite(v.Z) &&
                        Math.Abs(v.X)<=1 && Math.Abs(v.Y)<=1 && Math.Abs(v.Z)<=1, "Bounds");
                }
                Check(Rudiments.Sample(info.Name,-1)==values[^1],"Negative wrapping");
                Check(Rudiments.Sample(info.Name,info.PeriodPips)==values[0],"Positive wrapping");
                var edge=Rudiments.SampleMany(info.Name,int.MinValue,9,int.MaxValue);
                for (int i=0;i<edge.Length;++i)
                    Check(edge[i]==Rudiments.Sample(info.Name,(int)(((long)int.MinValue+(long)i*int.MaxValue)%info.PeriodPips)), "Batch overflow wrapping");
            }
            // An independent JSON export from the separately linked C++ core,
            // not a second export through this binding or an assumed waveform.
            if (args.Length > 0)
            {
                using var reference=JsonDocument.Parse(File.ReadAllBytes(args[0]));
                var rows=reference.RootElement.GetProperty("patterns");
                Check(rows.GetArrayLength()==items.Count,"Reference count"); int index=0;
                foreach(var row in rows.EnumerateArray())
                {
                    var info=items[index++];
                    Check(row.GetProperty("name").GetString()==info.Name,"Reference order");
                    Check(row.GetProperty("description").GetString()==info.Description,"UTF-8 description");
                    Check(row.GetProperty("period_pips").GetInt32()==info.PeriodPips,"Reference period");
                    Check(row.GetProperty("samples_f64le_sha256").GetString() ==
                        SampleHash(Rudiments.SampleMany(info.Name,0,info.PeriodPips)), "Direct C++ reference parity");
                }
            }
            var source=new[]{new Offset3(0,0),new Offset3(.2,-.3,.4),new Offset3(-.4,.5,-.6)};
            var definition=new PatternDefinition("dotnet_test","Écho — 日本語 🎵",source);
            source[1]=new Offset3(.99,.99);
            using(var bank=new PatternLibrary(definition))
            {
                Check(bank.Catalogue.Count==items.Count+1,"Bank count");
                Check(bank.Catalogue[^1].Description==definition.Description,"UTF-8 custom metadata");
                Check(bank.Sample("dotnet_test",1)==new Offset3(.2,-.3,.4),"Defensive copy");
                Check(bank.Sample("dotnet_test",-1)==definition.Samples[^1],"Bank reverse");
                Check(bank.Sample("circle",0)==Rudiments.Sample("circle",0),"Bank defaults");
                var result=bank.SampleMany("dotnet_test",-1,5,-1);
                Check(result[1]==definition.Samples[1] && result[4]==definition.Samples[1],"Reverse batch");
                Parallel.For(0,1000,i => { if(bank.Sample("dotnet_test",i)!=definition.Samples[i%3])throw new Exception("Concurrent sample"); });
                bank.Dispose(); bank.Dispose();
                Throws<ObjectDisposedException>(()=>bank.Sample("dotnet_test",0));
            }
            using(var empty=new PatternLibrary())Check(empty.Catalogue.Count==items.Count,"Empty custom bank");
            var circle=items.Single(i=>i.Name=="circle");
            using(var exact=new PatternLibrary(new PatternDefinition("circle",circle.Description,
                Rudiments.SampleMany("circle",0,circle.PeriodPips))))Check(exact.Catalogue.Count==items.Count,"Idempotent reload");
            Throws<ArgumentException>(()=>new PatternLibrary(new PatternDefinition("circle","Wrong metadata",new[]{new Offset3(0,0)})));
            Throws<ArgumentException>(()=>new PatternLibrary(definition,definition));
            Throws<ArgumentException>(()=>Rudiments.Sample("does_not_exist",0));
            Throws<ArgumentException>(()=>Rudiments.Sample("circle\0wrong",0));
            Throws<ArgumentNullException>(()=>Rudiments.Sample(null!,0));
            Throws<ArgumentException>(()=>new PatternDefinition("invalid name","",source));
            Throws<ArgumentException>(()=>new PatternDefinition("invalid","bad\0description",source));
            Throws<ArgumentException>(()=>new PatternDefinition("invalid","",new[]{new Offset3(double.NaN,0)}));
            Throws<ArgumentException>(()=>new PatternDefinition("invalid","",new[]{new Offset3(1.001,0)}));
            Throws<ArgumentOutOfRangeException>(()=>Rudiments.SampleMany("circle",0,-1));
            Check(Rudiments.SampleMany("circle",0,0).Length==0,"Empty batch");
            Check(Rudiments.PipAtTime(-.001,120,256)==255,"Floor negative time");
            Check(Rudiments.PipAtTime(1,120,256)==128,"Tempo conversion");
            Check(Rudiments.PipAtTime(1,120,256,1)==0,"Beat-zero offset");
            Throws<ArgumentOutOfRangeException>(()=>Rudiments.PipAtTime(1,0,256));
            Throws<ArgumentOutOfRangeException>(()=>Rudiments.PipAtTime(double.NaN,120,256));
            Throws<ArgumentOutOfRangeException>(()=>Rudiments.PipAtTime(double.MaxValue,120,256));
            var pack=new {format="dancerudiments.compiled-pack",schema_version=1,pips_per_beat=64,
                patterns=new[]{new{name="json_test",description="Écho JSON",period_pips=2,
                    samples=new[]{new[]{0.0,0.0,0.0},new[]{.5,-.5,.25}},source_sha256=new string('a',64),
                    provenance=new{},diagnostics=new{}}}};
            string json=JsonSerializer.Serialize(pack);
            using(var bank=PatternLibrary.FromJson(json))Check(bank.Sample("json_test",-1)==new Offset3(.5,-.5,.25),"JSON interchange");
            Throws<ArgumentException>(()=>PatternLibrary.FromJson(json.Replace("\"pips_per_beat\":64","\"pips_per_beat\":16")));
            Throws<ArgumentException>(()=>PatternLibrary.FromJson(json.Replace("\"schema_version\":1","\"schema_version\":1,\"schema_version\":1")));
            Throws<ArgumentException>(()=>PatternLibrary.FromJson(json.Replace("\"period_pips\":2","\"period_pips\":3")));
            // A read racing Dispose may finish or throw ObjectDisposedException,
            // but SafeHandle must keep its native pointer alive during P/Invoke.
            var racing=new PatternLibrary(definition);
            var worker=Task.Run(()=>{for(int i=0;i<10000;++i){try{_ = racing.Sample("dotnet_test",i);}catch(ObjectDisposedException){break;}}});
            racing.Dispose(); worker.GetAwaiter().GetResult();
            Console.WriteLine($"C# contracts passed: {items.Count} movements, {checks} checks, {RuntimeInformation.FrameworkDescription}, {RuntimeInformation.RuntimeIdentifier}");
            return 0;
        }
        catch(Exception e){Console.Error.WriteLine(e);return 1;}
    }
}
