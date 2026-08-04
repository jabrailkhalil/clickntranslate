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
            Process.Start(startInfo);
            return 0;
        }
        catch (Exception error)
        {
            WriteFailureLog(error);
            MessageBox.Show(
                "Click'n'Translate could not be started.\n\n" + error.Message,
                "Click'n'Translate",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
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
