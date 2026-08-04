using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class ClicknTranslateApplyUpdate
{
    [STAThread]
    private static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            UpdateRequest request = UpdateRequest.Parse(args);
            using (UpdateWindow window = new UpdateWindow(request))
            {
                Application.Run(window);
                return window.Succeeded ? 0 : 1;
            }
        }
        catch (Exception error)
        {
            WriteLog("Updater startup failed: " + error);
            SilentWinFormsDialog.Show(
                "The update could not be started. Your current version was not changed.\n\nPlease run Update again.",
                "Click'n'Translate update",
                MessageBoxButtons.OK
            );
            return 1;
        }
    }

    internal sealed class UpdateRequest
    {
        internal string Mode;
        internal string AppDirectory;
        internal string PackagePath;
        internal string ExecutableName;
        internal string ExpectedVersion;
        internal int TargetProcessId;

        internal static UpdateRequest Parse(string[] args)
        {
            Dictionary<string, string> values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            for (int index = 0; index + 1 < args.Length; index += 2)
            {
                values[args[index]] = args[index + 1];
            }
            UpdateRequest request = new UpdateRequest
            {
                Mode = Required(values, "--mode"),
                AppDirectory = Decode(Required(values, "--app-dir")),
                PackagePath = Decode(Required(values, "--package")),
                ExecutableName = Decode(Required(values, "--exe")),
                ExpectedVersion = Required(values, "--version"),
                TargetProcessId = int.Parse(Required(values, "--pid")),
            };
            request.AppDirectory = Path.GetFullPath(request.AppDirectory);
            request.PackagePath = Path.GetFullPath(request.PackagePath);
            if (request.Mode != "zip" && request.Mode != "setup")
            {
                throw new ArgumentException("Unsupported update mode.");
            }
            if (!Directory.Exists(request.AppDirectory) || !File.Exists(request.PackagePath))
            {
                throw new FileNotFoundException("The prepared update package is missing.", request.PackagePath);
            }
            return request;
        }

        private static string Required(Dictionary<string, string> values, string key)
        {
            string value;
            if (!values.TryGetValue(key, out value) || string.IsNullOrWhiteSpace(value))
            {
                throw new ArgumentException("Missing updater argument: " + key);
            }
            return value;
        }
    }

    internal sealed class UpdateWindow : Form
    {
        private readonly UpdateRequest request;
        private readonly Label status;
        private readonly Label detail;
        private readonly ProgressBar progress;
        private readonly Button closeButton;
        internal bool Succeeded { get; private set; }

        internal UpdateWindow(UpdateRequest request)
        {
            this.request = request;
            Text = "Click'n'Translate update";
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MinimizeBox = true;
            MaximizeBox = false;
            ShowInTaskbar = true;
            BackColor = Color.FromArgb(16, 17, 20);
            ForeColor = Color.FromArgb(245, 245, 247);
            ClientSize = new Size(570, 230);
            Font = new Font("Segoe UI", 10F, FontStyle.Regular, GraphicsUnit.Point);
            Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);

            Label title = new Label
            {
                Text = "Updating Click'n'Translate",
                AutoSize = false,
                Location = new Point(24, 22),
                Size = new Size(522, 28),
                Font = new Font("Segoe UI Semibold", 13F, FontStyle.Bold, GraphicsUnit.Point),
                ForeColor = Color.FromArgb(197, 179, 233),
            };
            Controls.Add(title);

            status = new Label
            {
                Text = "Preparing the verified update…",
                AutoSize = false,
                Location = new Point(24, 64),
                Size = new Size(522, 42),
                TextAlign = ContentAlignment.MiddleLeft,
            };
            Controls.Add(status);

            progress = new ProgressBar
            {
                Location = new Point(24, 112),
                Size = new Size(522, 22),
                Style = ProgressBarStyle.Marquee,
                MarqueeAnimationSpeed = 28,
            };
            Controls.Add(progress);

            detail = new Label
            {
                Text = "Keep this window open. The app will restart automatically.",
                AutoSize = false,
                Location = new Point(24, 145),
                Size = new Size(522, 34),
                ForeColor = Color.FromArgb(184, 184, 194),
            };
            Controls.Add(detail);

            closeButton = new Button
            {
                Text = "Close",
                Enabled = false,
                Location = new Point(434, 184),
                Size = new Size(112, 34),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(33, 31, 40),
                ForeColor = Color.White,
                UseVisualStyleBackColor = false,
            };
            closeButton.FlatAppearance.BorderColor = Color.FromArgb(128, 96, 168);
            closeButton.Click += delegate { Close(); };
            Controls.Add(closeButton);

            FormClosing += OnFormClosing;
            Shown += delegate
            {
                BackgroundWorker worker = new BackgroundWorker();
                worker.DoWork += delegate { ApplyUpdate(); };
                worker.RunWorkerCompleted += OnCompleted;
                worker.RunWorkerAsync();
            };
        }

        private void SetStatus(string value, string detailValue)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<string, string>(SetStatus), value, detailValue);
                return;
            }
            status.Text = value;
            if (!string.IsNullOrWhiteSpace(detailValue))
            {
                detail.Text = detailValue;
            }
        }

        private void OnCompleted(object sender, RunWorkerCompletedEventArgs eventArgs)
        {
            if (eventArgs.Error == null)
            {
                Succeeded = true;
                progress.Style = ProgressBarStyle.Continuous;
                progress.Value = 100;
                status.Text = "Update complete";
                detail.Text = "The updated application is open.";
                System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer { Interval = 1200 };
                timer.Tick += delegate { timer.Stop(); Close(); };
                timer.Start();
                return;
            }

            WriteLog("Updater failed: " + eventArgs.Error);
            progress.Style = ProgressBarStyle.Continuous;
            progress.Value = 0;
            status.Text = "The update could not be installed";
            status.ForeColor = Color.FromArgb(239, 93, 101);
            detail.Text = "The previous version was restored. Close other copies of the app and run Update again.";
            closeButton.Enabled = true;
        }

        private void OnFormClosing(object sender, FormClosingEventArgs eventArgs)
        {
            if (!Succeeded && !closeButton.Enabled)
            {
                eventArgs.Cancel = true;
                SetStatus(
                    "The update is still running",
                    "Wait until the updated app opens. Closing now could damage the installation."
                );
            }
        }

        private void ApplyUpdate()
        {
            string marker = Path.Combine(request.AppDirectory, "data", ".update-in-progress");
            string backup = null;
            bool backupComplete = false;
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(marker));
                File.WriteAllText(marker, DateTime.UtcNow.ToString("O"), new UTF8Encoding(false));

                SetStatus("Waiting for Click'n'Translate to close…", "Do not start the app manually; it will reopen automatically.");
                WaitForProcessExit(request.TargetProcessId, TimeSpan.FromSeconds(35));
                StopInstallProcesses(request.AppDirectory);

                string parent = Directory.GetParent(request.AppDirectory).FullName;
                backup = Path.Combine(parent, ".clickntranslate_backup_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(backup);
                SetStatus("Creating a safe backup…", "Your settings, histories and language packages are kept.");
                MoveProgramToBackup(request.AppDirectory, backup);
                backupComplete = true;

                if (request.Mode == "zip")
                {
                    InstallZip(request.PackagePath, request.AppDirectory);
                }
                else
                {
                    InstallSetup(request.PackagePath, request.AppDirectory);
                }

                VerifyInstalledFiles(request.AppDirectory, request.ExecutableName, request.ExpectedVersion);
                TryDelete(marker);
                StartAndVerify(request.AppDirectory, request.ExecutableName, request.ExpectedVersion);
                SetStatus("Cleaning the backup…", "The new version started successfully.");
                TryDeleteDirectory(backup);
                backup = null;
                TryDelete(request.PackagePath);
            }
            catch
            {
                WriteLog("Apply failed; starting rollback.");
                try
                {
                    StopInstallProcesses(request.AppDirectory);
                    if (backupComplete && !string.IsNullOrWhiteSpace(backup) && Directory.Exists(backup))
                    {
                        RemoveProgramItems(request.AppDirectory);
                        RestoreBackup(backup, request.AppDirectory);
                        backup = null;
                    }
                    TryDelete(marker);
                    StartApplication(request.AppDirectory, request.ExecutableName, "--show-after-update");
                }
                catch (Exception rollbackError)
                {
                    WriteLog("Rollback failed: " + rollbackError);
                }
                throw;
            }
            finally
            {
                TryDelete(marker);
                if (!string.IsNullOrWhiteSpace(backup) && Directory.Exists(backup))
                {
                    WriteLog("Preserving recovery backup at " + backup);
                }
            }
        }

        private void InstallZip(string packagePath, string appDirectory)
        {
            SetStatus("Unpacking the portable update…", "This normally takes less than a minute.");
            string extract = Path.Combine(Path.GetTempPath(), "clickntranslate_extract_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(extract);
            try
            {
                ExtractZipSafely(packagePath, extract);
                string launcher = Directory.GetFiles(extract, request.ExecutableName, SearchOption.AllDirectories).FirstOrDefault();
                if (string.IsNullOrWhiteSpace(launcher))
                {
                    throw new InvalidDataException("The update archive does not contain the launcher.");
                }
                string payloadRoot = Path.GetDirectoryName(launcher);
                if (!File.Exists(Path.Combine(payloadRoot, "app", "ClicknTranslateApp.exe")))
                {
                    throw new InvalidDataException("The update archive is incomplete.");
                }
                CopyDirectoryContents(payloadRoot, appDirectory);
            }
            finally
            {
                TryDeleteDirectory(extract);
            }
        }

        private void InstallSetup(string setupPath, string appDirectory)
        {
            SetStatus("Installing the verified update…", "Windows may need a moment to replace the program files.");
            string setupLog = Path.Combine(Path.GetTempPath(), "clickntranslate_setup_update.log");
            string arguments = string.Join(" ", new[]
            {
                "/SILENT", "/SUPPRESSMSGBOXES", "/NOCANCEL", "/NORESTART",
                "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS",
                "/DIR=" + Quote(appDirectory), "/LOG=" + Quote(setupLog),
            });
            using (Process process = Process.Start(new ProcessStartInfo
            {
                FileName = setupPath,
                Arguments = arguments,
                WorkingDirectory = Path.GetDirectoryName(setupPath),
                UseShellExecute = false,
            }))
            {
                if (process == null) throw new InvalidOperationException("Windows did not start the installer.");
                process.WaitForExit();
                if (process.ExitCode != 0)
                {
                    throw new InvalidOperationException("The installer did not finish successfully.");
                }
            }
        }

        private void StartAndVerify(string appDirectory, string executableName, string version)
        {
            SetStatus("Starting the updated version…", "The main window will appear automatically.");
            string ack = Path.Combine(Path.GetTempPath(), "clickntranslate_update_ack_" + Guid.NewGuid().ToString("N") + ".txt");
            Process process = StartApplication(
                appDirectory,
                executableName,
                "--show-after-update --update-ack=" + Quote(ack)
            );
            DateTime deadline = DateTime.UtcNow.AddSeconds(45);
            while (DateTime.UtcNow < deadline)
            {
                if (File.Exists(ack))
                {
                    string reported = File.ReadAllText(ack).Trim();
                    TryDelete(ack);
                    if (reported == version)
                    {
                        Thread.Sleep(8000);
                        if (HasRunningProcessInAppDirectory(appDirectory)) return;
                        throw new InvalidOperationException("The updated application process did not remain running.");
                    }
                    throw new InvalidOperationException("The application reported a different version.");
                }
                // The public launcher intentionally exits immediately after
                // handing control to app\ClicknTranslateApp.exe.  Only the
                // acknowledgement written by the real main window proves a
                // successful start; launcher lifetime is not meaningful.
                Thread.Sleep(250);
            }
            throw new TimeoutException("The updated application did not confirm startup.");
        }

        private static bool HasRunningProcessInAppDirectory(string appDirectory)
        {
            string prefix = Path.GetFullPath(appDirectory).TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
            foreach (Process candidate in Process.GetProcesses())
            {
                using (candidate)
                {
                    try
                    {
                        string executable = candidate.MainModule == null ? string.Empty : candidate.MainModule.FileName;
                        if (executable.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return true;
                    }
                    catch { }
                }
            }
            return false;
        }
    }

    private static void ExtractZipSafely(string archivePath, string destination)
    {
        string prefix = Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        using (ZipArchive archive = ZipFile.OpenRead(archivePath))
        {
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                string target = Path.GetFullPath(Path.Combine(destination, entry.FullName));
                if (!target.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Unsafe path in update archive.");
                if (string.IsNullOrEmpty(entry.Name))
                {
                    Directory.CreateDirectory(target);
                    continue;
                }
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                entry.ExtractToFile(target, true);
            }
        }
    }

    private static void VerifyInstalledFiles(string appDirectory, string executableName, string version)
    {
        string launcher = Path.Combine(appDirectory, executableName);
        string inner = Path.Combine(appDirectory, "app", "ClicknTranslateApp.exe");
        if (!File.Exists(launcher) || !File.Exists(inner))
            throw new InvalidDataException("The installed application files are incomplete.");
        string fileVersion = FileVersionInfo.GetVersionInfo(launcher).FileVersion ?? string.Empty;
        if (!fileVersion.StartsWith(version + ".", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("The installed launcher has the wrong version.");
    }

    private static void WaitForProcessExit(int processId, TimeSpan timeout)
    {
        try
        {
            using (Process process = Process.GetProcessById(processId))
            {
                if (!process.WaitForExit((int)timeout.TotalMilliseconds))
                {
                    try { process.Kill(); process.WaitForExit(10000); } catch { }
                }
            }
        }
        catch (ArgumentException) { }
    }

    private static void StopInstallProcesses(string appDirectory)
    {
        string prefix = Path.GetFullPath(appDirectory).TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
        foreach (Process process in Process.GetProcesses())
        {
            using (process)
            {
                if (process.Id == Process.GetCurrentProcess().Id) continue;
                string path;
                try { path = process.MainModule == null ? string.Empty : process.MainModule.FileName; }
                catch { continue; }
                if (!path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) continue;
                try { process.Kill(); process.WaitForExit(10000); } catch { }
            }
        }
    }

    private static bool IsPreserved(FileSystemInfo item)
    {
        if (item.Name.Equals("data", StringComparison.OrdinalIgnoreCase) ||
            item.Name.Equals("ocr", StringComparison.OrdinalIgnoreCase) ||
            item.Name.Equals("translators", StringComparison.OrdinalIgnoreCase)) return true;
        return item is FileInfo && item.Name.StartsWith("unins", StringComparison.OrdinalIgnoreCase) &&
            new[] { ".exe", ".dat", ".msg" }.Contains(item.Extension.ToLowerInvariant());
    }

    private static void MoveProgramToBackup(string appDirectory, string backup)
    {
        foreach (FileSystemInfo item in new DirectoryInfo(appDirectory).GetFileSystemInfos())
        {
            if (IsPreserved(item)) continue;
            MoveWithRetry(item.FullName, Path.Combine(backup, item.Name));
        }
    }

    private static void RemoveProgramItems(string appDirectory)
    {
        foreach (FileSystemInfo item in new DirectoryInfo(appDirectory).GetFileSystemInfos())
        {
            if (IsPreserved(item)) continue;
            if (item is DirectoryInfo) TryDeleteDirectory(item.FullName); else TryDelete(item.FullName);
        }
    }

    private static void RestoreBackup(string backup, string appDirectory)
    {
        foreach (FileSystemInfo item in new DirectoryInfo(backup).GetFileSystemInfos())
            MoveWithRetry(item.FullName, Path.Combine(appDirectory, item.Name));
        TryDeleteDirectory(backup);
    }

    private static void MoveWithRetry(string source, string destination)
    {
        for (int attempt = 1; attempt <= 120; attempt++)
        {
            try
            {
                if (Directory.Exists(source)) Directory.Move(source, destination);
                else File.Move(source, destination);
                return;
            }
            catch
            {
                if (attempt == 120) throw;
                Thread.Sleep(250);
            }
        }
    }

    private static void CopyDirectoryContents(string source, string destination)
    {
        foreach (string directory in Directory.GetDirectories(source, "*", SearchOption.AllDirectories))
        {
            string relative = directory.Substring(source.Length).TrimStart('\\', '/');
            Directory.CreateDirectory(Path.Combine(destination, relative));
        }
        foreach (string file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            string relative = file.Substring(source.Length).TrimStart('\\', '/');
            string target = Path.Combine(destination, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(target));
            File.Copy(file, target, true);
        }
    }

    private static Process StartApplication(string appDirectory, string executableName, string arguments)
    {
        string executable = Path.Combine(appDirectory, executableName);
        if (!File.Exists(executable)) return null;
        return Process.Start(new ProcessStartInfo
        {
            FileName = executable,
            WorkingDirectory = appDirectory,
            Arguments = arguments,
            UseShellExecute = false,
        });
    }

    private static string Decode(string value)
    {
        return Encoding.UTF8.GetString(Convert.FromBase64String(value));
    }

    private static string Quote(string value)
    {
        return "\"" + (value ?? string.Empty).Replace("\"", "\\\"") + "\"";
    }

    private static void TryDelete(string path)
    {
        try { if (!string.IsNullOrWhiteSpace(path) && File.Exists(path)) File.Delete(path); } catch { }
    }

    private static void TryDeleteDirectory(string path)
    {
        try { if (!string.IsNullOrWhiteSpace(path) && Directory.Exists(path)) Directory.Delete(path, true); } catch { }
    }

    private static readonly string LogPath = Path.Combine(Path.GetTempPath(), "clickntranslate_update.log");
    private static void WriteLog(string message)
    {
        try { File.AppendAllText(LogPath, DateTime.Now.ToString("O") + " " + message + Environment.NewLine); } catch { }
    }
}
