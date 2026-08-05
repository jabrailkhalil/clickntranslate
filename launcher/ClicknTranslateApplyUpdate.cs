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

    /// <summary>
    /// The application's shared palette.  Windows Forms draws its stock chrome
    /// with the system theme, which clashes badly with the dark app, so every
    /// surface in this window is painted from these values instead.
    /// </summary>
    internal static class Palette
    {
        internal static readonly Color Background = Color.FromArgb(16, 17, 20);      // #101114
        internal static readonly Color TitleBar = Color.FromArgb(21, 21, 21);        // #151515
        internal static readonly Color TitleBarLine = Color.FromArgb(41, 41, 45);    // #29292d
        internal static readonly Color Border = Color.FromArgb(51, 49, 60);          // #33313c
        internal static readonly Color Text = Color.FromArgb(245, 245, 247);         // #f5f5f7
        internal static readonly Color Muted = Color.FromArgb(184, 184, 194);        // #b8b8c2
        internal static readonly Color Accent = Color.FromArgb(121, 89, 160);        // #7959a0
        internal static readonly Color AccentLight = Color.FromArgb(169, 133, 210);  // #a985d2
        internal static readonly Color AccentText = Color.FromArgb(197, 179, 233);   // #c5b3e9
        internal static readonly Color Track = Color.FromArgb(33, 31, 40);           // #211f28
        internal static readonly Color ButtonHover = Color.FromArgb(50, 45, 61);     // #322d3d
        internal static readonly Color Danger = Color.FromArgb(196, 43, 28);         // #c42b1c
        internal static readonly Color DangerText = Color.FromArgb(217, 74, 74);     // #d94a4a
    }

    /// <summary>
    /// Progress bar drawn in the app's accent colour.  The stock WinForms
    /// ProgressBar ignores BackColor/ForeColor on themed Windows and renders a
    /// green system bar on the dark panel, which is what made the old updater
    /// window look out of place.
    /// </summary>
    internal sealed class AccentProgressBar : Control
    {
        private readonly System.Windows.Forms.Timer animation;
        private int marqueeOffset;
        private bool indeterminate = true;
        private int currentValue;

        internal AccentProgressBar()
        {
            SetStyle(
                ControlStyles.AllPaintingInWmPaint |
                ControlStyles.OptimizedDoubleBuffer |
                ControlStyles.UserPaint |
                ControlStyles.ResizeRedraw,
                true
            );
            animation = new System.Windows.Forms.Timer();
            animation.Interval = 33;
            animation.Tick += delegate
            {
                marqueeOffset = (marqueeOffset + 6) % Math.Max(1, Width + 220);
                Invalidate();
            };
            animation.Start();
        }

        internal bool Indeterminate
        {
            get { return indeterminate; }
            set
            {
                if (indeterminate == value)
                {
                    return;
                }
                indeterminate = value;
                if (indeterminate)
                {
                    animation.Start();
                }
                else
                {
                    animation.Stop();
                }
                Invalidate();
            }
        }

        internal int Value
        {
            get { return currentValue; }
            set
            {
                int clamped = Math.Max(0, Math.Min(100, value));
                if (currentValue == clamped)
                {
                    return;
                }
                currentValue = clamped;
                Invalidate();
            }
        }

        internal Color FillColor = Palette.Accent;
        internal Color FillHighlight = Palette.AccentLight;

        protected override void OnPaint(PaintEventArgs e)
        {
            System.Drawing.Drawing2D.GraphicsState state = e.Graphics.Save();
            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;

            Rectangle bounds = new Rectangle(0, 0, Width, Height);
            using (System.Drawing.Drawing2D.GraphicsPath track = RoundedRect(bounds, Height / 2))
            using (SolidBrush trackBrush = new SolidBrush(Palette.Track))
            using (Pen trackPen = new Pen(Palette.Border))
            {
                e.Graphics.FillPath(trackBrush, track);
                e.Graphics.DrawPath(trackPen, track);
                e.Graphics.SetClip(track);
            }

            if (indeterminate)
            {
                int sweepWidth = 180;
                int x = marqueeOffset - sweepWidth;
                Rectangle sweep = new Rectangle(x, 0, sweepWidth, Height);
                if (sweep.Width > 0)
                {
                    using (System.Drawing.Drawing2D.LinearGradientBrush brush =
                        new System.Drawing.Drawing2D.LinearGradientBrush(
                            sweep, Color.FromArgb(0, FillColor), FillHighlight,
                            System.Drawing.Drawing2D.LinearGradientMode.Horizontal))
                    {
                        System.Drawing.Drawing2D.ColorBlend blend = new System.Drawing.Drawing2D.ColorBlend();
                        blend.Colors = new Color[] { Color.FromArgb(0, FillColor), FillHighlight, Color.FromArgb(0, FillColor) };
                        blend.Positions = new float[] { 0f, 0.5f, 1f };
                        brush.InterpolationColors = blend;
                        e.Graphics.FillRectangle(brush, sweep);
                    }
                }
            }
            else if (currentValue > 0)
            {
                int fillWidth = Math.Max(Height, (int)Math.Round(Width * (currentValue / 100.0)));
                Rectangle fill = new Rectangle(0, 0, fillWidth, Height);
                using (System.Drawing.Drawing2D.LinearGradientBrush brush =
                    new System.Drawing.Drawing2D.LinearGradientBrush(
                        fill, FillColor, FillHighlight,
                        System.Drawing.Drawing2D.LinearGradientMode.Horizontal))
                {
                    e.Graphics.FillRectangle(brush, fill);
                }
            }

            e.Graphics.Restore(state);
        }

        internal static System.Drawing.Drawing2D.GraphicsPath RoundedRect(Rectangle bounds, int radius)
        {
            System.Drawing.Drawing2D.GraphicsPath path = new System.Drawing.Drawing2D.GraphicsPath();
            int diameter = Math.Max(1, radius * 2);
            if (diameter >= bounds.Width || diameter >= bounds.Height)
            {
                path.AddRectangle(bounds);
                return path;
            }
            Rectangle arc = new Rectangle(bounds.Location, new Size(diameter, diameter));
            path.AddArc(arc, 180, 90);
            arc.X = bounds.Right - diameter - 1;
            path.AddArc(arc, 270, 90);
            arc.Y = bounds.Bottom - diameter - 1;
            path.AddArc(arc, 0, 90);
            arc.X = bounds.Left;
            path.AddArc(arc, 90, 90);
            path.CloseFigure();
            return path;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                animation.Stop();
                animation.Dispose();
            }
            base.Dispose(disposing);
        }
    }

    /// <summary>Flat, app-styled button; WinForms' FlatStyle still draws a system border.</summary>
    internal sealed class AccentButton : Button
    {
        private bool hovered;

        internal AccentButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true);
            FlatStyle = FlatStyle.Flat;
            FlatAppearance.BorderSize = 0;
            BackColor = Palette.Track;
            ForeColor = Palette.Text;
            Cursor = Cursors.Hand;
        }

        protected override void OnMouseEnter(EventArgs e)
        {
            hovered = true;
            Invalidate();
            base.OnMouseEnter(e);
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            hovered = false;
            Invalidate();
            base.OnMouseLeave(e);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            e.Graphics.Clear(Palette.Background);
            Rectangle bounds = new Rectangle(0, 0, Width - 1, Height - 1);
            Color face = Enabled ? (hovered ? Palette.ButtonHover : Palette.Track) : Palette.Background;
            Color edge = Enabled ? (hovered ? Palette.AccentLight : Palette.Accent) : Palette.Border;
            Color label = Enabled ? Palette.Text : Color.FromArgb(108, 108, 120);
            using (System.Drawing.Drawing2D.GraphicsPath path = AccentProgressBar.RoundedRect(bounds, 6))
            using (SolidBrush brush = new SolidBrush(face))
            using (Pen pen = new Pen(edge))
            {
                e.Graphics.FillPath(brush, path);
                e.Graphics.DrawPath(pen, path);
            }
            TextRenderer.DrawText(
                e.Graphics, Text, Font, bounds, label,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter
            );
        }
    }

    internal sealed class UpdateWindow : Form
    {
        private const int TitleBarHeight = 40;

        private readonly UpdateRequest request;
        private readonly Label status;
        private readonly Label detail;
        private readonly AccentProgressBar progress;
        private readonly AccentButton closeButton;
        internal bool Succeeded { get; private set; }

        internal UpdateWindow(UpdateRequest request)
        {
            this.request = request;
            Text = "Click'n'Translate update";
            StartPosition = FormStartPosition.CenterScreen;
            // The system title bar is drawn with the OS theme and cannot be
            // tinted, so the window is frameless and every part of the chrome
            // is drawn here with the app's own palette.
            FormBorderStyle = FormBorderStyle.None;
            MaximizeBox = false;
            ShowInTaskbar = true;
            BackColor = Palette.Background;
            ForeColor = Palette.Text;
            ClientSize = new Size(580, 268);
            Font = new Font("Segoe UI", 9.75F, FontStyle.Regular, GraphicsUnit.Point);
            DoubleBuffered = true;
            try
            {
                Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
            }
            catch
            {
                // A missing icon must never stop an update from installing.
            }

            // The manifest declares PerMonitorV2, so Windows hands this process
            // real pixels and .NET Framework WinForms does not rescale for us.
            // Every fixed dimension therefore goes through S(), and text lives
            // in auto-sizing labels so nothing can ever be clipped.
            scale = GetDpiScale();
            ClientSize = new Size(S(580), S(292));

            // Body first, then the title bar: docked controls stack in reverse
            // z-order, and the bar has to end up above the content.
            TableLayoutPanel body = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                BackColor = Palette.Background,
                ColumnCount = 1,
                RowCount = 5,
                Padding = new Padding(S(26), S(22), S(26), S(18)),
            };
            body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            for (int row = 0; row < 5; row++)
            {
                body.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            }
            Controls.Add(body);

            int textWidth = S(580) - S(52);

            Label title = new Label
            {
                Text = "Updating Click'n'Translate",
                AutoSize = true,
                MaximumSize = new Size(textWidth, 0),
                Font = new Font("Segoe UI Semibold", 14F, FontStyle.Regular, GraphicsUnit.Point),
                ForeColor = Palette.AccentText,
                BackColor = Color.Transparent,
                Margin = new Padding(0, 0, 0, S(12)),
            };
            body.Controls.Add(title, 0, 0);

            status = new Label
            {
                Text = "Preparing the verified update…",
                AutoSize = true,
                MaximumSize = new Size(textWidth, 0),
                // Reserve two lines so the bar and the button keep their place
                // as the phase messages change length.
                MinimumSize = new Size(textWidth, S(38)),
                ForeColor = Palette.Text,
                BackColor = Color.Transparent,
                Margin = new Padding(0, 0, 0, S(14)),
            };
            body.Controls.Add(status, 0, 1);

            progress = new AccentProgressBar
            {
                Height = S(10),
                Dock = DockStyle.Fill,
                Margin = new Padding(0, 0, 0, S(14)),
            };
            body.Controls.Add(progress, 0, 2);

            detail = new Label
            {
                Text = "Keep this window open. The app will restart automatically.",
                AutoSize = true,
                MaximumSize = new Size(textWidth, 0),
                MinimumSize = new Size(textWidth, S(34)),
                ForeColor = Palette.Muted,
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 9F, FontStyle.Regular, GraphicsUnit.Point),
                Margin = new Padding(0, 0, 0, S(18)),
            };
            body.Controls.Add(detail, 0, 3);

            closeButton = new AccentButton
            {
                Text = "Close",
                Enabled = false,
                Size = new Size(S(114), S(34)),
                Anchor = AnchorStyles.Right,
                Margin = new Padding(0),
            };
            closeButton.Click += delegate { Close(); };
            body.Controls.Add(closeButton, 0, 4);

            BuildTitleBar();

            FormClosing += OnFormClosing;
            Shown += delegate
            {
                ApplyRoundedCorners();
                BackgroundWorker worker = new BackgroundWorker();
                worker.DoWork += delegate { ApplyUpdate(); };
                worker.RunWorkerCompleted += OnCompleted;
                worker.RunWorkerAsync();
            };
        }

        private float scale = 1F;

        private static float GetDpiScale()
        {
            try
            {
                using (Graphics graphics = Graphics.FromHwnd(IntPtr.Zero))
                {
                    return graphics.DpiX / 96F;
                }
            }
            catch
            {
                return 1F;
            }
        }

        private int S(int value)
        {
            return (int)Math.Round(value * scale);
        }

        private void BuildTitleBar()
        {
            int barHeight = S(TitleBarHeight);
            Panel bar = new Panel
            {
                Dock = DockStyle.Top,
                Height = barHeight,
                BackColor = Palette.TitleBar,
            };
            bar.Paint += delegate(object sender, PaintEventArgs e)
            {
                using (Pen pen = new Pen(Palette.TitleBarLine))
                {
                    e.Graphics.DrawLine(pen, 0, bar.Height - 1, bar.Width, bar.Height - 1);
                }
                if (Icon != null)
                {
                    int glyph = S(16);
                    using (Icon small = new Icon(Icon, glyph, glyph))
                    {
                        e.Graphics.DrawIcon(small, new Rectangle(S(12), (barHeight - glyph) / 2, glyph, glyph));
                    }
                }
            };
            bar.MouseDown += delegate(object sender, MouseEventArgs e)
            {
                if (e.Button == MouseButtons.Left)
                {
                    DragWindow();
                }
            };
            Controls.Add(bar);

            int buttonWidth = S(46);

            Label caption = new Label
            {
                Text = "Click'n'Translate update",
                AutoSize = false,
                Location = new Point(S(38), 0),
                Size = new Size(ClientSize.Width - S(38) - buttonWidth * 2, barHeight - 1),
                TextAlign = ContentAlignment.MiddleLeft,
                ForeColor = Color.FromArgb(247, 247, 247),
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 9.75F, FontStyle.Regular, GraphicsUnit.Point),
            };
            caption.MouseDown += delegate(object sender, MouseEventArgs e)
            {
                if (e.Button == MouseButtons.Left)
                {
                    DragWindow();
                }
            };
            bar.Controls.Add(caption);

            minimizeButton = new CaptionButton("–", Palette.ButtonHover);
            minimizeButton.Location = new Point(ClientSize.Width - buttonWidth * 2, 0);
            minimizeButton.Size = new Size(buttonWidth, barHeight - 1);
            minimizeButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            minimizeButton.Click += delegate { WindowState = FormWindowState.Minimized; };
            bar.Controls.Add(minimizeButton);

            titleCloseButton = new CaptionButton("✕", Palette.Danger);
            titleCloseButton.Location = new Point(ClientSize.Width - buttonWidth, 0);
            titleCloseButton.Size = new Size(buttonWidth, barHeight - 1);
            titleCloseButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            titleCloseButton.Click += delegate { Close(); };
            bar.Controls.Add(titleCloseButton);
        }

        private CaptionButton minimizeButton;
        private CaptionButton titleCloseButton;

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool ReleaseCapture();

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr SendMessage(IntPtr handle, int message, int wparam, int lparam);

        [System.Runtime.InteropServices.DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr handle, int attribute, ref int value, int size);

        private void DragWindow()
        {
            // Hand the drag to Windows so snapping and multi-monitor behaviour
            // stay exactly as users expect from a normal title bar.
            ReleaseCapture();
            SendMessage(Handle, 0xA1 /* WM_NCLBUTTONDOWN */, 2 /* HTCAPTION */, 0);
        }

        private void ApplyRoundedCorners()
        {
            try
            {
                // DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2.
                // Silently ignored before Windows 11.
                int preference = 2;
                DwmSetWindowAttribute(Handle, 33, ref preference, sizeof(int));
            }
            catch
            {
                // Cosmetic only.
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            using (Pen pen = new Pen(Palette.Border))
            {
                e.Graphics.DrawRectangle(pen, 0, 0, Width - 1, Height - 1);
            }
        }

        /// <summary>Minimise/close glyph button matching the app's dialog chrome.</summary>
        internal sealed class CaptionButton : Control
        {
            private readonly string glyph;
            private readonly Color hoverColor;
            private bool hovered;

            internal CaptionButton(string glyph, Color hoverColor)
            {
                this.glyph = glyph;
                this.hoverColor = hoverColor;
                SetStyle(
                    ControlStyles.AllPaintingInWmPaint |
                    ControlStyles.OptimizedDoubleBuffer |
                    ControlStyles.UserPaint,
                    true
                );
                BackColor = Palette.TitleBar;
                ForeColor = Color.FromArgb(238, 238, 238);
                Font = new Font("Segoe UI", 10F, FontStyle.Regular, GraphicsUnit.Point);
            }

            protected override void OnMouseEnter(EventArgs e)
            {
                hovered = true;
                Invalidate();
                base.OnMouseEnter(e);
            }

            protected override void OnMouseLeave(EventArgs e)
            {
                hovered = false;
                Invalidate();
                base.OnMouseLeave(e);
            }

            protected override void OnPaint(PaintEventArgs e)
            {
                e.Graphics.Clear(hovered ? hoverColor : Palette.TitleBar);
                TextRenderer.DrawText(
                    e.Graphics, glyph, Font, ClientRectangle,
                    hovered ? Color.White : ForeColor,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter
                );
            }
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
                progress.Indeterminate = false;
                progress.Value = 100;
                status.Text = "Update complete";
                detail.Text = "The updated application is open.";
                System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer { Interval = 1200 };
                timer.Tick += delegate { timer.Stop(); Close(); };
                timer.Start();
                return;
            }

            WriteLog("Updater failed: " + eventArgs.Error);
            progress.Indeterminate = false;
            progress.Value = 100;
            progress.FillColor = Palette.Danger;
            progress.FillHighlight = Palette.DangerText;
            progress.Invalidate();
            status.Text = "The update could not be installed";
            status.ForeColor = Palette.DangerText;
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
