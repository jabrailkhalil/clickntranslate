using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class ClicknTranslateLauncher
{
    private const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}_is1";

    [STAThread]
    private static int Main(string[] args)
    {
        string executablePath = Assembly.GetExecutingAssembly().Location;
        string root = Path.GetDirectoryName(executablePath) ?? AppDomain.CurrentDomain.BaseDirectory;
        string innerExecutable = Path.Combine(root, "app", "ClicknTranslateApp.exe");

        try
        {
            RestoreInstallerMetadata(root);
            SyncInstalledVersion(root);

            string updateMarker = Path.Combine(root, "data", ".update-in-progress");
            if (File.Exists(updateMarker))
            {
                DateTime markerTime = File.GetLastWriteTimeUtc(updateMarker);
                if (DateTime.UtcNow - markerTime < TimeSpan.FromHours(2))
                {
                    SilentWinFormsDialog.Show(
                        "Click'n'Translate is finishing an update. The updated window will open automatically.",
                        "Click'n'Translate update",
                        MessageBoxButtons.OK
                    );
                    return 0;
                }
                try { File.Delete(updateMarker); } catch { }
            }

            if (!File.Exists(innerExecutable))
            {
                throw new FileNotFoundException("The application executable was not found.", innerExecutable);
            }

            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = innerExecutable,
                WorkingDirectory = root,
                UseShellExecute = false,
                Arguments = JoinArguments(args),
            };
            Process started = Process.Start(startInfo);
            if (started == null)
            {
                throw new InvalidOperationException("Windows did not start the application process.");
            }
            WriteUpdateAcknowledgement(args);
            return 0;
        }
        catch (Exception error)
        {
            WriteFailureLog(error);
            SilentWinFormsDialog.Show(
                "Click'n'Translate could not be started.\n\n" + error.Message,
                "Click'n'Translate",
                MessageBoxButtons.OK
            );
            return 1;
        }
    }

    private static void SyncInstalledVersion(string root)
    {
        try
        {
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(UninstallKey, true))
            {
                if (key == null)
                {
                    return;
                }

                string registered = key.GetValue("InstallLocation") as string;
                if (string.IsNullOrWhiteSpace(registered))
                {
                    return;
                }

                string registeredRoot = Path.GetFullPath(registered).TrimEnd('\\', '/');
                string launcherRoot = Path.GetFullPath(root).TrimEnd('\\', '/');
                if (!registeredRoot.Equals(launcherRoot, StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }

                Version assemblyVersion = Assembly.GetExecutingAssembly().GetName().Version;
                string version = string.Format(
                    "{0}.{1}.{2}",
                    assemblyVersion.Major,
                    assemblyVersion.Minor,
                    assemblyVersion.Build
                );
                key.SetValue("DisplayVersion", version, RegistryValueKind.String);
                key.SetValue("DisplayName", "Click'n'Translate", RegistryValueKind.String);
            }
        }
        catch (Exception error)
        {
            WriteFailureLog(new InvalidOperationException("Could not synchronize the installed version.", error));
        }
    }

    private static void RestoreInstallerMetadata(string root)
    {
        DirectoryInfo rootDirectory = new DirectoryInfo(root);
        DirectoryInfo parent = rootDirectory.Parent;
        if (parent == null)
        {
            return;
        }

        DirectoryInfo[] backups = parent
            .GetDirectories(".clickntranslate_backup_*")
            .OrderByDescending(directory => directory.LastWriteTimeUtc)
            .ToArray();

        foreach (DirectoryInfo backup in backups)
        {
            foreach (FileInfo source in backup.GetFiles("unins*.*"))
            {
                string extension = source.Extension.ToLowerInvariant();
                if (extension != ".exe" && extension != ".dat" && extension != ".msg")
                {
                    continue;
                }

                string destination = Path.Combine(root, source.Name);
                if (!File.Exists(destination))
                {
                    File.Copy(source.FullName, destination, false);
                }
            }
        }
    }

    private static string JoinArguments(string[] args)
    {
        return string.Join(" ", args.Select(QuoteArgument));
    }

    private static void WriteUpdateAcknowledgement(string[] args)
    {
        string prefix = "--update-ack=";
        string argument = args.FirstOrDefault(value => value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(argument))
        {
            return;
        }
        string path = argument.Substring(prefix.Length).Trim().Trim('"');
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }
        try
        {
            string directory = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }
            Version version = Assembly.GetExecutingAssembly().GetName().Version;
            File.WriteAllText(path, string.Format("{0}.{1}.{2}", version.Major, version.Minor, version.Build));
        }
        catch (Exception error)
        {
            WriteFailureLog(new InvalidOperationException("Could not write the update acknowledgement.", error));
        }
    }

    private static string QuoteArgument(string value)
    {
        if (value.Length > 0 && value.All(character => !char.IsWhiteSpace(character) && character != '"'))
        {
            return value;
        }

        StringBuilder result = new StringBuilder();
        result.Append('"');
        int backslashes = 0;
        foreach (char character in value)
        {
            if (character == '\\')
            {
                backslashes++;
                continue;
            }

            if (character == '"')
            {
                result.Append('\\', backslashes * 2 + 1);
                result.Append('"');
                backslashes = 0;
                continue;
            }

            result.Append('\\', backslashes);
            backslashes = 0;
            result.Append(character);
        }
        result.Append('\\', backslashes * 2);
        result.Append('"');
        return result.ToString();
    }

    private static void WriteFailureLog(Exception error)
    {
        try
        {
            string path = Path.Combine(Path.GetTempPath(), "clickntranslate_launcher.log");
            File.AppendAllText(path, DateTime.Now.ToString("O") + " " + error + Environment.NewLine);
        }
        catch
        {
        }
    }
}
