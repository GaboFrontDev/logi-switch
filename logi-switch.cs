// logi-switch: cambia el canal Easy-Switch de un mouse/teclado Logitech via HID++ 2.0
// (feature 0x1814 Change Host) sin Logi Options+.
//
// Uso:
//   logi-switch info        -> muestra dispositivos, numero de hosts y host actual
//   logi-switch 1|2|3       -> cambia al canal indicado
//   logi-switch next        -> cambia al siguiente canal
//   Opcional: --match <texto>  filtra por texto en la ruta del dispositivo (ej. b042)

using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using Microsoft.Win32.SafeHandles;

static class Native
{
    [StructLayout(LayoutKind.Sequential)]
    public struct SP_DEVICE_INTERFACE_DATA { public int cbSize; public Guid InterfaceClassGuid; public int Flags; public IntPtr Reserved; }

    [StructLayout(LayoutKind.Sequential)]
    public struct HIDP_CAPS
    {
        public ushort Usage, UsagePage, InputReportByteLength, OutputReportByteLength, FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)] public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes, NumberInputButtonCaps, NumberInputValueCaps, NumberInputDataIndices,
            NumberOutputButtonCaps, NumberOutputValueCaps, NumberOutputDataIndices,
            NumberFeatureButtonCaps, NumberFeatureValueCaps, NumberFeatureDataIndices;
    }

    [DllImport("hid.dll")] public static extern void HidD_GetHidGuid(out Guid g);
    [DllImport("hid.dll")] public static extern bool HidD_GetPreparsedData(SafeFileHandle h, out IntPtr pd);
    [DllImport("hid.dll")] public static extern bool HidD_FreePreparsedData(IntPtr pd);
    [DllImport("hid.dll")] public static extern int HidP_GetCaps(IntPtr pd, out HIDP_CAPS caps);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr SetupDiGetClassDevs(ref Guid g, IntPtr enumr, IntPtr hwnd, int flags);
    [DllImport("setupapi.dll", SetLastError = true)]
    public static extern bool SetupDiEnumDeviceInterfaces(IntPtr set, IntPtr devInfo, ref Guid g, int idx, ref SP_DEVICE_INTERFACE_DATA d);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr set, ref SP_DEVICE_INTERFACE_DATA d, IntPtr detail, int size, out int req, IntPtr devInfo);
    [DllImport("setupapi.dll")] public static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr sec, uint disp, uint flags, IntPtr tmpl);
}

class HidppDevice : IDisposable
{
    public string Path;
    public int OutLen, InLen;
    FileStream fs;
    const byte DEV = 0xFF;   // indice para conexion directa (Bluetooth)
    const byte SWID = 0x0A;

    public static List<HidppDevice> Find(string match)
    {
        var list = new List<HidppDevice>();
        Guid g; Native.HidD_GetHidGuid(out g);
        IntPtr set = Native.SetupDiGetClassDevs(ref g, IntPtr.Zero, IntPtr.Zero, 0x12); // PRESENT | DEVICEINTERFACE
        try
        {
            for (int i = 0; ; i++)
            {
                var d = new Native.SP_DEVICE_INTERFACE_DATA(); d.cbSize = Marshal.SizeOf(d);
                if (!Native.SetupDiEnumDeviceInterfaces(set, IntPtr.Zero, ref g, i, ref d)) break;
                int req; Native.SetupDiGetDeviceInterfaceDetail(set, ref d, IntPtr.Zero, 0, out req, IntPtr.Zero);
                IntPtr buf = Marshal.AllocHGlobal(req);
                try
                {
                    Marshal.WriteInt32(buf, IntPtr.Size == 8 ? 8 : 6);
                    if (!Native.SetupDiGetDeviceInterfaceDetail(set, ref d, buf, req, out req, IntPtr.Zero)) continue;
                    string path = Marshal.PtrToStringUni(buf + 4);
                    string lp = path.ToLowerInvariant();
                    if (!(lp.Contains("vid&02046d") || lp.Contains("vid_046d"))) continue;
                    if (match != null && !lp.Contains(match.ToLowerInvariant())) continue;
                    var dev = TryOpen(path);
                    if (dev != null) list.Add(dev);
                }
                finally { Marshal.FreeHGlobal(buf); }
            }
        }
        finally { Native.SetupDiDestroyDeviceInfoList(set); }
        return list;
    }

    static HidppDevice TryOpen(string path)
    {
        // GENERIC_READ|GENERIC_WRITE, share RW, OPEN_EXISTING, FILE_FLAG_OVERLAPPED
        var h = Native.CreateFile(path, 0xC0000000, 3, IntPtr.Zero, 3, 0x40000000, IntPtr.Zero);
        if (h.IsInvalid) return null;
        IntPtr pd;
        if (!Native.HidD_GetPreparsedData(h, out pd)) { h.Dispose(); return null; }
        Native.HIDP_CAPS caps; Native.HidP_GetCaps(pd, out caps); Native.HidD_FreePreparsedData(pd);
        // Coleccion HID++ larga: usage page vendor (0xFF00 / 0xFF43), reportes de 20 bytes
        if (caps.UsagePage < 0xFF00 || caps.OutputReportByteLength != 20) { h.Dispose(); return null; }
        return new HidppDevice { Path = path, OutLen = caps.OutputReportByteLength, InLen = caps.InputReportByteLength,
                                 fs = new FileStream(h, FileAccess.ReadWrite, 64, true) };
    }

    byte[] Request(byte feat, byte func, params byte[] args)
    {
        var msg = new byte[OutLen];
        msg[0] = 0x11; msg[1] = DEV; msg[2] = feat; msg[3] = (byte)((func << 4) | SWID);
        Array.Copy(args, 0, msg, 4, args.Length);
        fs.Write(msg, 0, msg.Length);
        var deadline = DateTime.UtcNow.AddMilliseconds(1500);
        while (DateTime.UtcNow < deadline)
        {
            var buf = new byte[Math.Max(InLen, 20)];
            var ar = fs.BeginRead(buf, 0, buf.Length, null, null);
            if (!ar.AsyncWaitHandle.WaitOne(deadline - DateTime.UtcNow)) return null;
            int n = fs.EndRead(ar);
            if (n < 4) continue;
            if (buf[2] == 0xFF && buf[3] == feat) throw new Exception("HID++ error 0x" + buf[5].ToString("X2"));
            if (buf[2] == feat && buf[3] == msg[3]) return buf;
        }
        return null;
    }

    public void Send(byte feat, byte func, params byte[] args)
    {
        var msg = new byte[OutLen];
        msg[0] = 0x11; msg[1] = DEV; msg[2] = feat; msg[3] = (byte)((func << 4) | SWID);
        Array.Copy(args, 0, msg, 4, args.Length);
        fs.Write(msg, 0, msg.Length);
    }

    public byte FeatureIndex(ushort featureId)
    {
        var r = Request(0x00, 0, (byte)(featureId >> 8), (byte)featureId);
        return r == null ? (byte)0 : r[4];
    }

    // devuelve (numHosts, hostActual 0-based)
    public bool HostInfo(byte idx, out int count, out int current)
    {
        count = current = -1;
        var r = Request(idx, 0);
        if (r == null) return false;
        count = r[4]; current = r[5];
        return true;
    }

    public void Dispose() { if (fs != null) fs.Dispose(); }
}

static class Program
{
    static int Main(string[] args)
    {
        string cmd = args.Length > 0 ? args[0].ToLowerInvariant() : "info";
        string match = null;
        for (int i = 1; i < args.Length - 1; i++) if (args[i] == "--match") match = args[i + 1];

        var devs = HidppDevice.Find(match);
        if (devs.Count == 0) { Console.Error.WriteLine("No encontre ningun dispositivo Logitech HID++."); return 2; }

        foreach (var dev in devs)
        {
            using (dev)
            {
                try
                {
                    byte idx = dev.FeatureIndex(0x1814);
                    if (idx == 0) { if (cmd == "info") Console.WriteLine("[sin Change Host] " + dev.Path); continue; }
                    int count, cur;
                    if (!dev.HostInfo(idx, out count, out cur)) { Console.Error.WriteLine("Sin respuesta: " + dev.Path); continue; }

                    if (cmd == "info")
                    {
                        Console.WriteLine(dev.Path);
                        Console.WriteLine("  hosts: " + count + "  actual: " + (cur + 1));
                        continue;
                    }

                    int target;
                    if (cmd == "next") target = (cur + 1) % count;
                    else if (int.TryParse(cmd, out target) && target >= 1 && target <= count) target -= 1;
                    else { Console.Error.WriteLine("Canal invalido: " + cmd + " (1-" + count + ")"); return 1; }

                    if (target == cur) { Console.WriteLine("Ya esta en el canal " + (cur + 1)); return 0; }
                    dev.Send(idx, 1, (byte)target);
                    Console.WriteLine("Cambiando al canal " + (target + 1));
                    return 0;
                }
                catch (Exception e) { Console.Error.WriteLine(e.Message + " (" + dev.Path + ")"); }
            }
        }
        return cmd == "info" ? 0 : 3;
    }
}
