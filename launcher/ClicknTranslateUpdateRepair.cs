using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class ClicknTranslateUpdateRepair
{
    private const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}_is1";

    [STAThread]
    private static int Main(string[] args)
    {
        bool silent = args.Any(value => value.Equals("/silent", StringComparison.OrdinalIgnoreCase));
        try
        {
            string installRoot = FindInstallRoot();
            if (installRoot == null)
            {
                throw new InvalidOperationException(
                    "Click'n'Translate 1.4.6 or 1.4.7 was not found. Place this repair tool in the application folder and run it again."
                );
            }

            if (!silent)
            {
                DialogResult result = MessageBox.Show(
                    "This one-time repair fixes the updater in Click'n'Translate 1.4.6/1.4.7.\n\n" +
                    "Only the small application launcher will be replaced. Settings, histories, OCR packages and translation models will be kept.\n\n" +
                    "Continue?",
                    "Click'n'Translate update repair",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Information
                );
                if (result != DialogResult.Yes)
                {
                    return 2;
                }
            }

            StopInstalledApplication(installRoot);
            ReplaceLauncher(installRoot);
            StartApplication(installRoot);

            if (!silent)
            {
                MessageBox.Show(
                    "The updater launcher is repaired.\n\nOpen Settings and click Update to install the latest version.",
                    "Click'n'Translate update repair",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information
                );
            }
            return 0;
        }
        catch (Exception error)
        {
            WriteFailureLog(error);
            if (!silent)
            {
                MessageBox.Show(
                    "The updater could not be repaired.\n\n" + error.Message,
                    "Click'n'Translate update repair",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
            return 1;
        }
    }

    private static string FindInstallRoot()
    {
        string ownDirectory = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        if (IsInstallRoot(ownDirectory))
        {
            return Path.GetFullPath(ownDirectory);
        }

        using (RegistryKey key = Registry.CurrentUser.OpenSubKey(UninstallKey))
        {
            string registered = key == null ? null : key.GetValue("InstallLocation") as string;
            if (IsInstallRoot(registered))
            {
                return Path.GetFullPath(registered);
            }
        }

        string[] candidates =
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "ClicknTranslate"),
            @"C:\Soft\ClicknTranslate",
        };
        return candidates.FirstOrDefault(IsInstallRoot);
    }

    private static bool IsInstallRoot(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return false;
        }
        try
        {
            string fullPath = Path.GetFullPath(path);
            return File.Exists(Path.Combine(fullPath, "ClicknTranslate.exe")) &&
                   File.Exists(Path.Combine(fullPath, "app", "ClicknTranslateApp.exe"));
        }
        catch
        {
            return false;
        }
    }

    private static void StopInstalledApplication(string installRoot)
    {
        string expectedPrefix = Path.GetFullPath(Path.Combine(installRoot, "app"))
            .TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;

        foreach (Process process in Process.GetProcessesByName("ClicknTranslateApp"))
        {
            try
            {
                string processPath = process.MainModule.FileName;
                if (!processPath.StartsWith(expectedPrefix, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (process.CloseMainWindow() && process.WaitForExit(3000))
                {
                    continue;
                }
                process.Kill();
                process.WaitForExit(5000);
            }
            catch (InvalidOperationException)
            {
                // The process exited between enumeration and inspection.
            }
        }
    }

    private static void ReplaceLauncher(string installRoot)
    {
        string launcher = Path.Combine(installRoot, "ClicknTranslate.exe");
        string replacement = Path.Combine(installRoot, "ClicknTranslate.exe.repair-new");
        string backup = Path.Combine(installRoot, "ClicknTranslate.exe.update-backup");

        using (Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("FixedLauncher"))
        {
            if (resource == null)
            {
                throw new InvalidOperationException("The repaired launcher payload is missing.");
            }
            using (FileStream output = new FileStream(replacement, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                resource.CopyTo(output);
                output.Flush(true);
            }
        }

        if (new FileInfo(replacement).Length < 32768)
        {
            throw new InvalidDataException("The repaired launcher payload is incomplete.");
        }

        if (File.Exists(backup))
        {
            File.Delete(backup);
        }

        try
        {
            File.Replace(replacement, launcher, backup, true);
        }
        catch
        {
            if (!File.Exists(launcher) && File.Exists(backup))
            {
                File.Move(backup, launcher);
            }
            if (File.Exists(replacement))
            {
                File.Delete(replacement);
            }
            throw;
        }
    }

    private static void StartApplication(string installRoot)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = Path.Combine(installRoot, "ClicknTranslate.exe"),
            WorkingDirectory = installRoot,
            UseShellExecute = false,
        });
    }

    private static void WriteFailureLog(Exception error)
    {
        try
        {
            string path = Path.Combine(Path.GetTempPath(), "clickntranslate_update_repair.log");
            File.AppendAllText(path, DateTime.Now.ToString("O") + " " + error + Environment.NewLine);
        }
        catch
        {
        }
    }
}
