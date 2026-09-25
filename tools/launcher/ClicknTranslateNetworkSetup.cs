using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Threading;
using System.Windows.Forms;

internal static class ClicknTranslateNetworkSetup
{
    [STAThread]
    private static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        ServicePointManager.SecurityProtocol |= (SecurityProtocolType)3072;
        using (DownloadWindow window = new DownloadWindow(args))
        {
            Application.Run(window);
            return window.ExitCode;
        }
    }

    private sealed class DownloadWindow : Form
    {
        private readonly string[] setupArguments;
        private readonly Label status;
        private readonly Label detail;
        private readonly ProgressBar progress;
        private readonly Button closeButton;
        internal int ExitCode { get; private set; }
        private bool completed;

        internal DownloadWindow(string[] setupArguments)
        {
            this.setupArguments = setupArguments ?? new string[0];
            ExitCode = 1;
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

            Controls.Add(new Label
            {
                Text = "Downloading Click'n'Translate " + SetupBootstrapInfo.Version,
                Location = new Point(24, 22),
                Size = new Size(522, 30),
                Font = new Font("Segoe UI Semibold", 13F, FontStyle.Bold),
                ForeColor = Color.FromArgb(197, 179, 233),
            });
            status = new Label { Location = new Point(24, 64), Size = new Size(522, 35), Text = "Connecting to GitHub…" };
            Controls.Add(status);
            progress = new ProgressBar { Location = new Point(24, 108), Size = new Size(522, 23), Minimum = 0, Maximum = 100 };
            Controls.Add(progress);
            detail = new Label
            {
                Location = new Point(24, 143),
                Size = new Size(522, 35),
                ForeColor = Color.FromArgb(184, 184, 194),
                Text = "The download is verified before installation and automatically retried if interrupted.",
            };
            Controls.Add(detail);
            closeButton = new Button
            {
                Text = "Close", Enabled = false, Location = new Point(434, 184), Size = new Size(112, 34),
                FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(33, 31, 40), ForeColor = Color.White,
            };
            closeButton.FlatAppearance.BorderColor = Color.FromArgb(128, 96, 168);
            closeButton.Click += delegate { Close(); };
            Controls.Add(closeButton);
            FormClosing += delegate(object sender, FormClosingEventArgs eventArgs)
            {
                if (!completed) eventArgs.Cancel = true;
            };
            Shown += delegate
            {
                BackgroundWorker worker = new BackgroundWorker();
                worker.DoWork += delegate { DownloadAndInstall(); };
                worker.RunWorkerCompleted += Finished;
                worker.RunWorkerAsync();
            };
        }

        private void Report(string text, int percent)
        {
            if (InvokeRequired) { BeginInvoke(new Action<string, int>(Report), text, percent); return; }
            status.Text = text;
            progress.Style = ProgressBarStyle.Continuous;
            progress.Value = Math.Max(0, Math.Min(100, percent));
        }

        private void DownloadAndInstall()
        {
            string root = Path.Combine(Path.GetTempPath(), "ClicknTranslateSetup_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            string setup = Path.Combine(root, "Click-n-Translate-" + SetupBootstrapInfo.Version + "-windows-x64-installer.exe");
            try
            {
                DownloadWithResume(SetupBootstrapInfo.Url, setup, Report);
                Report("Verifying the downloaded installer…", 100);
                string hash = ComputeSha256(setup);
                if (!hash.Equals(SetupBootstrapInfo.Sha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("The downloaded installer did not pass verification.");
                Report("Installing Click'n'Translate…", 100);
                using (Process process = Process.Start(new ProcessStartInfo
                {
                    FileName = setup,
                    Arguments = string.Join(" ", setupArguments.Select(QuoteArgument)),
                    WorkingDirectory = root,
                    UseShellExecute = false,
                }))
                {
                    if (process == null) throw new InvalidOperationException("Windows did not start the installer.");
                    process.WaitForExit();
                    if (process.ExitCode != 0) throw new InvalidOperationException("The installer did not finish successfully.");
                }
                ExitCode = 0;
            }
            finally
            {
                try { Directory.Delete(root, true); } catch { }
            }
        }

        private void Finished(object sender, RunWorkerCompletedEventArgs args)
        {
            completed = true;
            if (args.Error == null)
            {
                progress.Value = 100;
                status.Text = "Update installed";
                detail.Text = "Click'n'Translate will open automatically.";
                System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer { Interval = 900 };
                timer.Tick += delegate { timer.Stop(); Close(); };
                timer.Start();
                return;
            }
            WriteLog(args.Error.ToString());
            status.Text = "The update download failed";
            status.ForeColor = Color.FromArgb(239, 93, 101);
            detail.Text = "Your current version was not changed. Check the connection and click Update again.";
            closeButton.Enabled = true;
        }
    }

    private static void DownloadWithResume(string url, string destination, Action<string, int> progress)
    {
        string partial = destination + ".part";
        Exception last = null;
        for (int attempt = 1; attempt <= 6; attempt++)
        {
            long existing = File.Exists(partial) ? new FileInfo(partial).Length : 0;
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
                request.UserAgent = "ClicknTranslate-Updater/" + SetupBootstrapInfo.Version;
                request.AllowAutoRedirect = true;
                request.Timeout = 30000;
                request.ReadWriteTimeout = 120000;
                if (existing > 0) request.AddRange(existing);
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                {
                    bool resumed = existing > 0 && response.StatusCode == HttpStatusCode.PartialContent;
                    if (existing > 0 && !resumed) { existing = 0; File.Delete(partial); }
                    long total = response.ContentLength > 0 ? existing + response.ContentLength : 0;
                    using (Stream input = response.GetResponseStream())
                    using (FileStream output = new FileStream(partial, resumed ? FileMode.Append : FileMode.Create, FileAccess.Write, FileShare.None))
                    {
                        byte[] buffer = new byte[1024 * 1024];
                        long received = existing;
                        int read;
                        while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
                        {
                            output.Write(buffer, 0, read);
                            received += read;
                            int percent = total > 0 ? (int)Math.Min(99, received * 100 / total) : 0;
                            progress("Downloading update… " + (received / 1048576.0).ToString("0.0") + (total > 0 ? "/" + (total / 1048576.0).ToString("0.0") + " MB" : " MB"), percent);
                        }
                        output.Flush(true);
                        if (total > 0 && received != total) throw new IOException("The connection ended before the file was complete.");
                    }
                }
                if (File.Exists(destination)) File.Delete(destination);
                File.Move(partial, destination);
                return;
            }
            catch (Exception error)
            {
                last = error;
                WriteLog("Download attempt " + attempt + " failed: " + error);
                if (attempt < 6) { progress("Connection interrupted. Retrying " + attempt + "/6…", 0); Thread.Sleep(attempt * 1000); }
            }
        }
        throw new IOException("The update download was interrupted repeatedly.", last);
    }

    private static string ComputeSha256(string path)
    {
        using (SHA256 sha = SHA256.Create())
        using (FileStream stream = File.OpenRead(path))
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", string.Empty);
    }

    private static string QuoteArgument(string value)
    {
        if (!value.Any(character => char.IsWhiteSpace(character) || character == '"')) return value;
        return "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }

    private static void WriteLog(string value)
    {
        try { File.AppendAllText(Path.Combine(Path.GetTempPath(), "clickntranslate_update.log"), DateTime.Now.ToString("O") + " " + value + Environment.NewLine); } catch { }
    }
}
