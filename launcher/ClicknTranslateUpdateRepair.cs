using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class ClicknTranslateUpdateRepair
{
    private const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}_is1";
    private const string ProductExecutable = "ClicknTranslate.exe";
    private const string InnerExecutable = "ClicknTranslateApp.exe";
    private static readonly string LogPath = Path.Combine(Path.GetTempPath(), "clickntranslate_update_repair.log");

    [STAThread]
    private static int Main(string[] args)
    {
        bool silent = args.Any(value => value.Equals("/silent", StringComparison.OrdinalIgnoreCase));
        try
        {
            // Never keep the installed application directory locked while its contents are replaced.
            Environment.CurrentDirectory = Path.GetTempPath();
            ServicePointManager.SecurityProtocol |= (SecurityProtocolType)3072; // TLS 1.2 on .NET Framework 4.x.

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
                    "This one-time repair will download and install Click'n'Translate " + RepairBuildInfo.DisplayVersion + ".\n\n" +
                    "Settings, histories, OCR packages, translation models and uninstall information will be kept.\n\n" +
                    "The download is about 200 MB. Continue?",
                    "Click'n'Translate update repair",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Information
                );
                if (result != DialogResult.Yes)
                {
                    return 2;
                }
            }

            if (silent)
            {
                ApplyFullUpdate(installRoot, delegate { });
            }
            else
            {
                using (RepairProgressDialog progress = new RepairProgressDialog(installRoot))
                {
                    progress.ShowDialog();
                    if (progress.Failure != null)
                    {
                        throw progress.Failure;
                    }
                }
            }

            if (!silent)
            {
                MessageBox.Show(
                    "Click'n'Translate " + RepairBuildInfo.DisplayVersion + " is installed and has been started.",
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
                    "The update could not be installed. The previous version was restored.\n\n" + error.Message,
                    "Click'n'Translate update repair",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
            return 1;
        }
    }

    private static void ApplyFullUpdate(string installRoot, Action<int, string> report)
    {
        string temporaryRoot = Path.Combine(
            Path.GetTempPath(),
            "clickntranslate_repair_" + Guid.NewGuid().ToString("N")
        );
        string packagePath = Path.Combine(temporaryRoot, "ClicknTranslate-" + RepairBuildInfo.DisplayVersion + ".zip");
        string extractRoot = Path.Combine(temporaryRoot, "extract");
        string backupRoot = null;
        bool payloadCopyStarted = false;

        Directory.CreateDirectory(temporaryRoot);
        try
        {
            report(1, "Downloading Click'n'Translate " + RepairBuildInfo.DisplayVersion + "...");
            DownloadPackage(RepairBuildInfo.PackageUrl, packagePath, report);

            report(66, "Verifying the downloaded package...");
            VerifySha256(packagePath, RepairBuildInfo.PackageSha256);

            report(70, "Extracting the update...");
            Directory.CreateDirectory(extractRoot);
            ZipFile.ExtractToDirectory(packagePath, extractRoot);
            string payloadRoot = FindPayloadRoot(extractRoot);

            report(82, "Closing the old version...");
            StopInstalledApplication(installRoot);

            string installParent = Path.GetDirectoryName(installRoot.TrimEnd(Path.DirectorySeparatorChar));
            backupRoot = Path.Combine(
                installParent,
                ".clickntranslate_repair_backup_" + Guid.NewGuid().ToString("N")
            );
            Directory.CreateDirectory(backupRoot);

            report(86, "Backing up the previous program files...");
            MoveProgramItemsToBackup(installRoot, backupRoot);

            report(90, "Installing the repaired version...");
            payloadCopyStarted = true;
            CopyPayload(payloadRoot, installRoot);
            ValidateInstalledPayload(installRoot);

            report(97, "Starting Click'n'Translate...");
            StartApplication(installRoot);

            TryDeleteDirectory(backupRoot);
            backupRoot = null;
            report(100, "Click'n'Translate " + RepairBuildInfo.DisplayVersion + " is ready.");
        }
        catch
        {
            if (backupRoot != null && Directory.Exists(backupRoot))
            {
                try
                {
                    if (payloadCopyStarted)
                    {
                        RemoveProgramItems(installRoot);
                    }
                    RestoreBackup(backupRoot, installRoot);
                    TryDeleteDirectory(backupRoot);
                }
                catch (Exception rollbackError)
                {
                    WriteFailureLog(new InvalidOperationException("Rollback failed.", rollbackError));
                }
            }
            throw;
        }
        finally
        {
            TryDeleteDirectory(temporaryRoot);
        }
    }

    private static void DownloadPackage(string url, string destination, Action<int, string> report)
    {
        WebRequest request = WebRequest.Create(url);
        request.Timeout = 60000;
        HttpWebRequest httpRequest = request as HttpWebRequest;
        if (httpRequest != null)
        {
            httpRequest.AllowAutoRedirect = true;
            httpRequest.ReadWriteTimeout = 60000;
            httpRequest.UserAgent = "ClicknTranslate-Update-Repair/" + RepairBuildInfo.DisplayVersion;
        }

        using (WebResponse response = request.GetResponse())
        using (Stream input = response.GetResponseStream())
        using (FileStream output = new FileStream(destination, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            if (input == null)
            {
                throw new IOException("The update server returned an empty response.");
            }

            long total = response.ContentLength;
            long received = 0;
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
            {
                output.Write(buffer, 0, read);
                received += read;
                int percent = total > 0 ? 1 + (int)Math.Min(64, received * 64 / total) : 20;
                string size = total > 0
                    ? string.Format("Downloading update... {0:0.0} / {1:0.0} MB", received / 1048576.0, total / 1048576.0)
                    : string.Format("Downloading update... {0:0.0} MB", received / 1048576.0);
                report(percent, size);
            }
            output.Flush(true);
        }

        if (!File.Exists(destination) || new FileInfo(destination).Length < 1024)
        {
            throw new InvalidDataException("The downloaded update package is incomplete.");
        }
    }

    private static void VerifySha256(string path, string expected)
    {
        string normalized = (expected ?? "").Trim().Replace(" ", "").ToUpperInvariant();
        if (normalized.Length != 64)
        {
            throw new InvalidDataException("The update package checksum is not configured correctly.");
        }

        string actual;
        using (SHA256 algorithm = SHA256.Create())
        using (FileStream stream = File.OpenRead(path))
        {
            actual = BitConverter.ToString(algorithm.ComputeHash(stream)).Replace("-", "");
        }
        if (!actual.Equals(normalized, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException("The downloaded update failed SHA-256 verification.");
        }
    }

    private static string FindPayloadRoot(string extractRoot)
    {
        if (IsPayloadRoot(extractRoot))
        {
            return extractRoot;
        }

        string preferred = Path.Combine(extractRoot, "ClicknTranslate");
        if (IsPayloadRoot(preferred))
        {
            return preferred;
        }

        string found = Directory.GetDirectories(extractRoot).FirstOrDefault(IsPayloadRoot);
        if (found == null)
        {
            throw new InvalidDataException("The update archive does not contain a valid Click'n'Translate package.");
        }
        return found;
    }

    private static bool IsPayloadRoot(string path)
    {
        return Directory.Exists(path) &&
               File.Exists(Path.Combine(path, ProductExecutable)) &&
               File.Exists(Path.Combine(path, "app", InnerExecutable));
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
            return File.Exists(Path.Combine(fullPath, ProductExecutable)) &&
                   File.Exists(Path.Combine(fullPath, "app", InnerExecutable));
        }
        catch
        {
            return false;
        }
    }

    private static void StopInstalledApplication(string installRoot)
    {
        string root = Path.GetFullPath(installRoot).TrimEnd(Path.DirectorySeparatorChar);
        string appPrefix = Path.Combine(root, "app").TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        foreach (string processName in new[] { "ClicknTranslateApp", "ClicknTranslate" })
        {
            foreach (Process process in Process.GetProcessesByName(processName))
            {
                try
                {
                    string processPath = process.MainModule.FileName;
                    bool belongsToInstall = processPath.Equals(
                        Path.Combine(root, ProductExecutable),
                        StringComparison.OrdinalIgnoreCase
                    ) || processPath.StartsWith(appPrefix, StringComparison.OrdinalIgnoreCase);
                    if (!belongsToInstall)
                    {
                        continue;
                    }

                    if (process.CloseMainWindow() && process.WaitForExit(4000))
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
    }

    private static bool IsPreservedItem(FileSystemInfo item, string installRoot)
    {
        string name = item.Name;
        if (name.Equals("data", StringComparison.OrdinalIgnoreCase) ||
            name.Equals("ocr", StringComparison.OrdinalIgnoreCase) ||
            name.Equals("translators", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        string extension = Path.GetExtension(name);
        if (name.StartsWith("unins", StringComparison.OrdinalIgnoreCase) &&
            (extension.Equals(".exe", StringComparison.OrdinalIgnoreCase) ||
             extension.Equals(".dat", StringComparison.OrdinalIgnoreCase) ||
             extension.Equals(".msg", StringComparison.OrdinalIgnoreCase)))
        {
            return true;
        }

        string ownPath = Path.GetFullPath(Assembly.GetExecutingAssembly().Location);
        return Path.GetFullPath(item.FullName).Equals(ownPath, StringComparison.OrdinalIgnoreCase);
    }

    private static void MoveProgramItemsToBackup(string installRoot, string backupRoot)
    {
        foreach (FileSystemInfo item in new DirectoryInfo(installRoot).GetFileSystemInfos())
        {
            if (IsPreservedItem(item, installRoot))
            {
                continue;
            }
            MoveWithRetry(item.FullName, Path.Combine(backupRoot, item.Name));
        }
    }

    private static void MoveWithRetry(string source, string destination)
    {
        Exception lastError = null;
        for (int attempt = 0; attempt < 40; attempt++)
        {
            try
            {
                if (Directory.Exists(source))
                {
                    Directory.Move(source, destination);
                }
                else
                {
                    File.Move(source, destination);
                }
                return;
            }
            catch (IOException error)
            {
                lastError = error;
                Thread.Sleep(250);
            }
            catch (UnauthorizedAccessException error)
            {
                lastError = error;
                Thread.Sleep(250);
            }
        }
        throw new IOException("Could not replace " + Path.GetFileName(source) + ".", lastError);
    }

    private static void CopyPayload(string payloadRoot, string installRoot)
    {
        foreach (FileSystemInfo item in new DirectoryInfo(payloadRoot).GetFileSystemInfos())
        {
            if (item.Name.Equals("data", StringComparison.OrdinalIgnoreCase) ||
                item.Name.Equals("ocr", StringComparison.OrdinalIgnoreCase) ||
                item.Name.Equals("translators", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            string destination = Path.Combine(installRoot, item.Name);
            DirectoryInfo directory = item as DirectoryInfo;
            if (directory != null)
            {
                CopyDirectory(directory.FullName, destination);
            }
            else
            {
                File.Copy(item.FullName, destination, true);
            }
        }
    }

    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (string file in Directory.GetFiles(source))
        {
            File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), true);
        }
        foreach (string directory in Directory.GetDirectories(source))
        {
            CopyDirectory(directory, Path.Combine(destination, Path.GetFileName(directory)));
        }
    }

    private static void ValidateInstalledPayload(string installRoot)
    {
        if (!File.Exists(Path.Combine(installRoot, ProductExecutable)) ||
            !File.Exists(Path.Combine(installRoot, "app", InnerExecutable)))
        {
            throw new InvalidDataException("The repaired application payload is incomplete.");
        }
    }

    private static void RemoveProgramItems(string installRoot)
    {
        foreach (FileSystemInfo item in new DirectoryInfo(installRoot).GetFileSystemInfos())
        {
            if (IsPreservedItem(item, installRoot))
            {
                continue;
            }
            if (item is DirectoryInfo)
            {
                TryDeleteDirectory(item.FullName);
            }
            else
            {
                File.Delete(item.FullName);
            }
        }
    }

    private static void RestoreBackup(string backupRoot, string installRoot)
    {
        foreach (FileSystemInfo item in new DirectoryInfo(backupRoot).GetFileSystemInfos())
        {
            string destination = Path.Combine(installRoot, item.Name);
            if (Directory.Exists(destination))
            {
                Directory.Delete(destination, true);
            }
            else if (File.Exists(destination))
            {
                File.Delete(destination);
            }
            MoveWithRetry(item.FullName, destination);
        }
    }

    private static void StartApplication(string installRoot)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = Path.Combine(installRoot, ProductExecutable),
            WorkingDirectory = installRoot,
            UseShellExecute = false,
        });
    }

    private static void TryDeleteDirectory(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !Directory.Exists(path))
        {
            return;
        }
        for (int attempt = 0; attempt < 10; attempt++)
        {
            try
            {
                Directory.Delete(path, true);
                return;
            }
            catch
            {
                Thread.Sleep(200);
            }
        }
    }

    private static void WriteFailureLog(Exception error)
    {
        try
        {
            File.AppendAllText(LogPath, DateTime.Now.ToString("O") + " " + error + Environment.NewLine);
        }
        catch
        {
        }
    }

    private sealed class RepairProgressDialog : Form
    {
        private readonly BackgroundWorker worker = new BackgroundWorker { WorkerReportsProgress = true };
        private readonly Label status = new Label();
        private readonly ProgressBar progress = new ProgressBar();
        private readonly string installRoot;

        internal Exception Failure { get; private set; }

        internal RepairProgressDialog(string root)
        {
            installRoot = root;
            Text = "Click'n'Translate update repair";
            ClientSize = new Size(500, 142);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Color.FromArgb(17, 17, 20);
            ForeColor = Color.White;
            Font = new Font("Segoe UI", 10F);

            status.SetBounds(24, 24, 452, 42);
            status.Text = "Preparing the update...";
            status.AutoEllipsis = true;
            progress.SetBounds(24, 82, 452, 26);
            progress.Minimum = 0;
            progress.Maximum = 100;
            progress.Style = ProgressBarStyle.Continuous;
            Controls.Add(status);
            Controls.Add(progress);

            worker.DoWork += delegate
            {
                ApplyFullUpdate(installRoot, delegate(int value, string text)
                {
                    worker.ReportProgress(Math.Max(0, Math.Min(100, value)), text);
                });
            };
            worker.ProgressChanged += delegate(object sender, ProgressChangedEventArgs eventArgs)
            {
                progress.Value = eventArgs.ProgressPercentage;
                status.Text = eventArgs.UserState as string ?? status.Text;
            };
            worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs eventArgs)
            {
                Failure = eventArgs.Error;
                DialogResult = Failure == null ? DialogResult.OK : DialogResult.Abort;
                Close();
            };
            Shown += delegate { worker.RunWorkerAsync(); };
            FormClosing += delegate(object sender, FormClosingEventArgs eventArgs)
            {
                if (worker.IsBusy)
                {
                    eventArgs.Cancel = true;
                }
            };
        }
    }
}
