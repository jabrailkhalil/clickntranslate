using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
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

        try
        {
            string diagnosticPath = PrefixedArgument(args, "--create-bug-report=");
            if (!string.IsNullOrWhiteSpace(diagnosticPath))
            {
                CreateDiagnosticReport(root, null, diagnosticPath.Trim().Trim('"'));
                return 0;
            }

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

            string innerExecutable = FindApplicationExecutable(root);
            if (string.IsNullOrWhiteSpace(innerExecutable))
            {
                throw new FileNotFoundException(
                    "The main application file is missing. An antivirus may have quarantined it, or the installation did not finish.",
                    Path.Combine(root, "app", "ClicknTranslateApp.exe")
                );
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
            bool russian = string.Equals(
                System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName,
                "ru",
                StringComparison.OrdinalIgnoreCase
            );
            string message = russian
                ? "Click'n'Translate не удалось запустить.\n\n"
                  + "Основной файл программы отсутствует или заблокирован. Проверьте карантин антивируса, "
                  + "восстановите ClicknTranslateApp.exe и добавьте папку ClicknTranslate в исключения. "
                  + "Если файла нет — запустите установщик ещё раз.\n\n"
                  + "Кнопка ниже создаст безопасный отчёт без буфера обмена, истории и текста документов."
                : "Click'n'Translate could not be started.\n\n"
                  + "The main application file is missing or blocked. Check your antivirus quarantine, "
                  + "restore ClicknTranslateApp.exe and allow the ClicknTranslate folder. "
                  + "If the file is not there, run the installer again.\n\n"
                  + "The button below creates a safe report without clipboard, history or document text.";
            SilentWinFormsDialog.ShowStartupFailure(
                message,
                "Click'n'Translate",
                russian ? "Создать отчёт" : "Create bug report",
                russian ? "Закрыть" : "Close",
                russian ? "Отчёт создан. Прикрепите файл в GitHub или Telegram:" : "Report created. Attach this file on GitHub or Telegram:",
                russian ? "Не удалось создать отчёт:" : "Could not create the report:",
                delegate { return CreateDiagnosticReport(root, error, null); }
            );
            return 1;
        }
    }

    private static string FindApplicationExecutable(string root)
    {
        string[] relativeCandidates = new[]
        {
            Path.Combine("app", "ClicknTranslateApp.exe"),
            Path.Combine("app", "ClicknTranslate.exe"),
            "ClicknTranslateApp.exe",
        };
        string launcher = Path.GetFullPath(Assembly.GetExecutingAssembly().Location);
        foreach (string relative in relativeCandidates)
        {
            string candidate = Path.GetFullPath(Path.Combine(root, relative));
            if (candidate.Equals(launcher, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }
        return null;
    }

    private static string PrefixedArgument(string[] args, string prefix)
    {
        string argument = args.FirstOrDefault(
            value => value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
        );
        return string.IsNullOrWhiteSpace(argument) ? null : argument.Substring(prefix.Length);
    }

    private static string CreateDiagnosticReport(string root, Exception error, string requestedPath)
    {
        string path = requestedPath;
        if (string.IsNullOrWhiteSpace(path))
        {
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            if (string.IsNullOrWhiteSpace(desktop) || !Directory.Exists(desktop))
            {
                desktop = Path.GetTempPath();
            }
            path = Path.Combine(
                desktop,
                "ClicknTranslate-startup-report-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".txt"
            );
        }
        path = Path.GetFullPath(path);
        string directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        Version version = Assembly.GetExecutingAssembly().GetName().Version;
        StringBuilder report = new StringBuilder();
        report.AppendLine("Click'n'Translate startup diagnostics");
        report.AppendLine("Private text, clipboard contents, histories and configuration values are excluded.");
        report.AppendLine();
        report.AppendLine("generated_local: " + DateTime.Now.ToString("O"));
        report.AppendLine("launcher_version: " + version);
        report.AppendLine("windows: " + Environment.OSVersion);
        report.AppendLine("framework: " + Environment.Version);
        report.AppendLine("64_bit_os: " + Environment.Is64BitOperatingSystem);
        report.AppendLine("64_bit_process: " + Environment.Is64BitProcess);
        report.AppendLine("ui_language: " + System.Globalization.CultureInfo.CurrentUICulture.Name);
        report.AppendLine("install_root: " + RedactPath(root));
        report.AppendLine();
        AppendFileStatus(report, "public_launcher", Assembly.GetExecutingAssembly().Location);
        AppendFileStatus(report, "application", Path.Combine(root, "app", "ClicknTranslateApp.exe"));
        AppendFileStatus(report, "legacy_application", Path.Combine(root, "app", "ClicknTranslate.exe"));
        AppendFileStatus(report, "updater", Path.Combine(root, "app", "_internal", "ClicknTranslateUpdater.exe"));
        AppendFileStatus(report, "ocr_worker", Path.Combine(root, "app", "_internal", "OcrWorker.exe"));
        AppendFileStatus(report, "argos_worker", Path.Combine(root, "app", "_internal", "ArgosWorker.exe"));
        if (error != null)
        {
            report.AppendLine();
            report.AppendLine("startup_error:");
            report.AppendLine(RedactPath(error.ToString()));
        }

        string[] logs = new[]
        {
            Path.Combine(Path.GetTempPath(), "clickntranslate_launcher.log"),
            Path.Combine(Path.GetTempPath(), "clickntranslate_update.log"),
            Path.Combine(Path.GetTempPath(), "clickntranslate_setup_update.log"),
        };
        foreach (string log in logs)
        {
            if (!File.Exists(log))
            {
                continue;
            }
            report.AppendLine();
            report.AppendLine("log: " + Path.GetFileName(log));
            report.AppendLine(RedactPath(ReadTail(log, 256 * 1024)));
        }
        File.WriteAllText(path, report.ToString(), new UTF8Encoding(false));
        return path;
    }

    private static void AppendFileStatus(StringBuilder report, string label, string path)
    {
        if (!File.Exists(path))
        {
            report.AppendLine(label + ": missing, path=" + RedactPath(path));
            return;
        }
        try
        {
            FileInfo info = new FileInfo(path);
            report.AppendLine(
                label + ": present, bytes=" + info.Length + ", sha256=" + Sha256(path)
                + ", path=" + RedactPath(path)
            );
        }
        catch (Exception statusError)
        {
            report.AppendLine(label + ": unreadable, error=" + statusError.Message);
        }
    }

    private static string Sha256(string path)
    {
        using (SHA256 sha = SHA256.Create())
        using (FileStream stream = File.OpenRead(path))
        {
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }
    }

    private static string ReadTail(string path, int limit)
    {
        using (FileStream stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        {
            long offset = Math.Max(0, stream.Length - limit);
            stream.Seek(offset, SeekOrigin.Begin);
            int count = (int)Math.Min(limit, stream.Length - offset);
            byte[] bytes = new byte[count];
            int read = stream.Read(bytes, 0, bytes.Length);
            return Encoding.UTF8.GetString(bytes, 0, read);
        }
    }

    private static string RedactPath(string value)
    {
        string text = value ?? string.Empty;
        string profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        if (!string.IsNullOrWhiteSpace(profile))
        {
            text = text.Replace(profile, "<user-path>");
        }
        string username = Environment.UserName;
        if (!string.IsNullOrWhiteSpace(username))
        {
            text = text.Replace(username, "<user>");
        }
        return text;
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
