using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class ClicknTranslateUpdateBootstrap
{
    private const string ApplyArgument = "--apply";

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length >= 4 && args[0].Equals(ApplyArgument, StringComparison.OrdinalIgnoreCase))
            {
                return ApplyUpdate(
                    Decode(args[1]),
                    Decode(args[2]),
                    int.Parse(args[3])
                );
            }

            return StartDetachedHelper();
        }
        catch (Exception error)
        {
            ShowFailure(error.Message);
            return 1;
        }
    }

    private static int StartDetachedHelper()
    {
        string executablePath = typeof(ClicknTranslateUpdateBootstrap).Assembly.Location;
        string appDirectory = Path.GetDirectoryName(executablePath) ?? AppDomain.CurrentDomain.BaseDirectory;
        string setupPath = Directory
            .GetFiles(appDirectory, "ClicknTranslate-Setup-v*-win64.exe", SearchOption.TopDirectoryOnly)
            .OrderByDescending(File.GetLastWriteTimeUtc)
            .FirstOrDefault();

        if (string.IsNullOrWhiteSpace(setupPath) || !File.Exists(setupPath))
        {
            throw new FileNotFoundException(
                "The update installer is missing. Run the Click'n'Translate installer manually.",
                setupPath
            );
        }

        string helperDirectory = Path.Combine(
            Path.GetTempPath(),
            "ClicknTranslateUpdate_" + Guid.NewGuid().ToString("N")
        );
        Directory.CreateDirectory(helperDirectory);
        string helperPath = Path.Combine(helperDirectory, "ClicknTranslateUpdateBootstrap.exe");
        string helperSetupPath = Path.Combine(helperDirectory, Path.GetFileName(setupPath));
        File.Copy(executablePath, helperPath, true);
        File.Copy(setupPath, helperSetupPath, true);

        ProcessStartInfo startInfo = new ProcessStartInfo
        {
            FileName = helperPath,
            WorkingDirectory = helperDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            Arguments = string.Join(" ", new[]
            {
                ApplyArgument,
                Encode(appDirectory),
                Encode(helperSetupPath),
                Process.GetCurrentProcess().Id.ToString()
            })
        };
        Process.Start(startInfo);
        return 0;
    }

    private static int ApplyUpdate(string appDirectory, string setupPath, int parentProcessId)
    {
        WaitForProcessExit(parentProcessId, TimeSpan.FromSeconds(30));
        StopInstallProcesses(appDirectory);

        string setupLog = Path.Combine(Path.GetTempPath(), "clickntranslate_setup_update.log");
        ProcessStartInfo setupInfo = new ProcessStartInfo
        {
            FileName = setupPath,
            WorkingDirectory = Path.GetDirectoryName(setupPath) ?? Path.GetTempPath(),
            UseShellExecute = false,
            Arguments = string.Join(" ", new[]
            {
                "/SILENT",
                "/SUPPRESSMSGBOXES",
                "/NOCANCEL",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
                "/FORCECLOSEAPPLICATIONS",
                "/NORESTARTAPPLICATIONS",
                "/LOGCLOSEAPPLICATIONS",
                "/DIR=" + Quote(appDirectory),
                "/LOG=" + Quote(setupLog)
            })
        };

        using (Process setup = Process.Start(setupInfo))
        {
            if (setup == null)
            {
                throw new InvalidOperationException("Windows did not start the update installer.");
            }
            setup.WaitForExit();
            if (setup.ExitCode != 0)
            {
                throw new InvalidOperationException(
                    "The update installer exited with code " + setup.ExitCode + ". Log: " + setupLog
                );
            }
        }

        string bundledSetup = Path.Combine(appDirectory, Path.GetFileName(setupPath));
        try
        {
            if (File.Exists(bundledSetup))
            {
                File.Delete(bundledSetup);
            }
        }
        catch
        {
        }

        string launcherPath = Path.Combine(appDirectory, "ClicknTranslate.exe");
        if (!File.Exists(launcherPath))
        {
            throw new FileNotFoundException("The updated application launcher was not installed.", launcherPath);
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = launcherPath,
            WorkingDirectory = appDirectory,
            UseShellExecute = false
        });
        ScheduleCleanup(Path.GetDirectoryName(setupPath));
        return 0;
    }

    private static void StopInstallProcesses(string appDirectory)
    {
        string installPrefix = Path.GetFullPath(appDirectory)
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        DirectoryInfo parent = Directory.GetParent(installPrefix.TrimEnd(Path.DirectorySeparatorChar));
        string parentDirectory = parent == null ? string.Empty : parent.FullName;
        string backupPrefix = string.IsNullOrWhiteSpace(parentDirectory)
            ? string.Empty
            : Path.Combine(parentDirectory, ".clickntranslate_backup_");

        foreach (Process process in Process.GetProcesses())
        {
            using (process)
            {
                if (process.Id == Process.GetCurrentProcess().Id)
                {
                    continue;
                }

                string executablePath;
                try
                {
                    ProcessModule module = process.MainModule;
                    executablePath = module == null ? string.Empty : module.FileName;
                }
                catch
                {
                    continue;
                }

                bool belongsToInstall = executablePath.StartsWith(
                    installPrefix,
                    StringComparison.OrdinalIgnoreCase
                );
                bool belongsToOldBackup = !string.IsNullOrWhiteSpace(backupPrefix)
                    && executablePath.StartsWith(backupPrefix, StringComparison.OrdinalIgnoreCase);
                if (!belongsToInstall && !belongsToOldBackup)
                {
                    continue;
                }

                try
                {
                    Process taskKill = Process.Start(new ProcessStartInfo
                    {
                        FileName = "taskkill.exe",
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        Arguments = "/PID " + process.Id + " /T /F"
                    });
                    if (taskKill != null)
                    {
                        using (taskKill)
                        {
                            taskKill.WaitForExit(10000);
                        }
                    }
                }
                catch
                {
                    try
                    {
                        process.Kill();
                        process.WaitForExit(10000);
                    }
                    catch
                    {
                    }
                }
            }
        }
    }

    private static void WaitForProcessExit(int processId, TimeSpan timeout)
    {
        try
        {
            using (Process process = Process.GetProcessById(processId))
            {
                process.WaitForExit((int)timeout.TotalMilliseconds);
            }
        }
        catch (ArgumentException)
        {
        }
    }

    private static void ScheduleCleanup(string directory)
    {
        if (string.IsNullOrWhiteSpace(directory) || !Directory.Exists(directory))
        {
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe",
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                Arguments = "/d /c ping.exe 127.0.0.1 -n 3 >nul & rmdir /s /q " + Quote(directory)
            });
        }
        catch
        {
        }
    }

    private static string Encode(string value)
    {
        return Convert.ToBase64String(Encoding.UTF8.GetBytes(value ?? string.Empty));
    }

    private static string Decode(string value)
    {
        return Encoding.UTF8.GetString(Convert.FromBase64String(value ?? string.Empty));
    }

    private static string Quote(string value)
    {
        return "\"" + (value ?? string.Empty).Replace("\"", "\\\"") + "\"";
    }

    private static void ShowFailure(string message)
    {
        MessageBox.Show(
            "The update could not be installed.\n\n" + message,
            "Click'n'Translate update",
            MessageBoxButtons.OK,
            MessageBoxIcon.Error
        );
    }
}
