using System;
using System.IO;
using System.Threading.Tasks;
using Windows.Media.Ocr;
using Windows.Graphics.Imaging;
using Windows.Storage;

namespace GhostlineOcr {
    class Program {
        static void Main(string[] args) {
            try {
                Console.OutputEncoding = new System.Text.UTF8Encoding(false);
                int code = RunAsync(args).GetAwaiter().GetResult();
                Environment.Exit(code);
            } catch (Exception ex) {
                Console.Error.WriteLine("Fatal Error: " + ex.ToString());
                Environment.Exit(5);
            }
        }

        static async Task<int> RunAsync(string[] args) {
            if (args.Length == 0) {
                Console.Error.WriteLine("Usage: win_ocr.exe <image_path>");
                return 1;
            }
            string path = Path.GetFullPath(args[0]);
            if (!File.Exists(path)) {
                Console.Error.WriteLine("Error: File not found: " + path);
                return 2;
            }

            var fileOp = StorageFile.GetFileFromPathAsync(path);
            var file = await WindowsRuntimeSystemExtensions.AsTask(fileOp);

            var streamOp = file.OpenAsync(FileAccessMode.Read);
            using (var stream = await WindowsRuntimeSystemExtensions.AsTask(streamOp)) {
                var decoderOp = BitmapDecoder.CreateAsync(stream);
                var decoder = await WindowsRuntimeSystemExtensions.AsTask(decoderOp);

                var bitmapOp = decoder.GetSoftwareBitmapAsync();
                var bitmap = await WindowsRuntimeSystemExtensions.AsTask(bitmapOp);
                
                var engine = OcrEngine.TryCreateFromUserProfileLanguages();
                if (engine == null) {
                    engine = OcrEngine.TryCreateFromLanguage(new Windows.Globalization.Language("en-US"));
                }
                if (engine == null) {
                    Console.Error.WriteLine("Error: Could not initialize Windows OCR engine.");
                    return 3;
                }

                var ocrOp = engine.RecognizeAsync(bitmap);
                var result = await WindowsRuntimeSystemExtensions.AsTask(ocrOp);
                
                double textAngle = 0.0;
                if (result.TextAngle.HasValue) {
                    textAngle = result.TextAngle.Value;
                }

                Console.WriteLine("{");
                Console.WriteLine("  \"text\": " + EscapeJson(result.Text) + ",");
                Console.WriteLine("  \"text_angle\": " + textAngle.ToString(System.Globalization.CultureInfo.InvariantCulture) + ",");
                
                // Backward-compatible string lines array
                Console.WriteLine("  \"lines\": [");
                for (int i = 0; i < result.Lines.Count; i++) {
                    string line = result.Lines[i].Text;
                    string comma = (i < result.Lines.Count - 1) ? "," : "";
                    Console.WriteLine("    " + EscapeJson(line) + comma);
                }
                Console.WriteLine("  ],");

                // Detailed spatial line_boxes with bounding rectangles
                Console.WriteLine("  \"line_boxes\": [");
                for (int i = 0; i < result.Lines.Count; i++) {
                    var ocrLine = result.Lines[i];
                    double minX = double.MaxValue, minY = double.MaxValue;
                    double maxX = double.MinValue, maxY = double.MinValue;
                    
                    if (ocrLine.Words.Count > 0) {
                        for (int w = 0; w < ocrLine.Words.Count; w++) {
                            var rect = ocrLine.Words[w].BoundingRect;
                            if (rect.X < minX) minX = rect.X;
                            if (rect.Y < minY) minY = rect.Y;
                            if (rect.X + rect.Width > maxX) maxX = rect.X + rect.Width;
                            if (rect.Y + rect.Height > maxY) maxY = rect.Y + rect.Height;
                        }
                    } else {
                        minX = 0; minY = 0; maxX = 0; maxY = 0;
                    }

                    double lineW = Math.Max(0, maxX - minX);
                    double lineH = Math.Max(0, maxY - minY);
                    var culture = System.Globalization.CultureInfo.InvariantCulture;

                    Console.WriteLine("    {");
                    Console.WriteLine("      \"text\": " + EscapeJson(ocrLine.Text) + ",");
                    Console.WriteLine("      \"x\": " + minX.ToString(culture) + ",");
                    Console.WriteLine("      \"y\": " + minY.ToString(culture) + ",");
                    Console.WriteLine("      \"width\": " + lineW.ToString(culture) + ",");
                    Console.WriteLine("      \"height\": " + lineH.ToString(culture) + ",");
                    Console.WriteLine("      \"words\": [");
                    for (int w = 0; w < ocrLine.Words.Count; w++) {
                        var word = ocrLine.Words[w];
                        var wRect = word.BoundingRect;
                        string wComma = (w < ocrLine.Words.Count - 1) ? "," : "";
                        Console.WriteLine("        {\"text\": " + EscapeJson(word.Text) + 
                            ", \"x\": " + wRect.X.ToString(culture) + 
                            ", \"y\": " + wRect.Y.ToString(culture) + 
                            ", \"width\": " + wRect.Width.ToString(culture) + 
                            ", \"height\": " + wRect.Height.ToString(culture) + "}" + wComma);
                    }
                    Console.WriteLine("      ]");
                    string lineComma = (i < result.Lines.Count - 1) ? "," : "";
                    Console.WriteLine("    }" + lineComma);
                }
                Console.WriteLine("  ]");
                Console.WriteLine("}");
                return 0;
            }
        }

        static string EscapeJson(string s) {
            if (s == null) return "null";
            var sb = new System.Text.StringBuilder(s.Length + 16);
            sb.Append('"');
            foreach (char c in s) {
                switch (c) {
                    case '\\': sb.Append("\\\\"); break;
                    case '"': sb.Append("\\\""); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 32) {
                            Console.Error.WriteLine(string.Format("[DEBUG FOUND C < 32] int={0}", (int)c));
                            sb.Append(string.Format("\\u{0:x4}", (int)c));
                        } else {
                            sb.Append(c);
                        }
                        break;
                }
            }
            sb.Append('"');
            return sb.ToString();
        }
    }
}
