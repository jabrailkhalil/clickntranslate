using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

internal static class SilentWinFormsDialog
{
    internal static DialogResult Show(string text, string title, MessageBoxButtons buttons)
    {
        using (Form form = new Form())
        {
            form.Text = title ?? "Click'n'Translate";
            form.StartPosition = FormStartPosition.CenterScreen;
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.MinimizeBox = false;
            form.MaximizeBox = false;
            form.ShowInTaskbar = true;
            form.BackColor = Color.FromArgb(16, 17, 20);
            form.ForeColor = Color.FromArgb(245, 245, 247);
            form.ClientSize = new Size(540, 215);
            form.Font = new Font("Segoe UI", 10F, FontStyle.Regular, GraphicsUnit.Point);

            Label message = new Label
            {
                AutoSize = false,
                Text = text ?? string.Empty,
                ForeColor = form.ForeColor,
                BackColor = form.BackColor,
                Location = new Point(24, 24),
                Size = new Size(492, 125),
                TextAlign = ContentAlignment.MiddleLeft,
            };
            form.Controls.Add(message);

            FlowLayoutPanel actions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.RightToLeft,
                WrapContents = false,
                Location = new Point(24, 159),
                Size = new Size(492, 40),
                BackColor = form.BackColor,
            };
            form.Controls.Add(actions);

            if (buttons == MessageBoxButtons.YesNo)
            {
                Button no = CreateButton("No", DialogResult.No, false);
                Button yes = CreateButton("Yes", DialogResult.Yes, true);
                actions.Controls.Add(no);
                actions.Controls.Add(yes);
                form.AcceptButton = yes;
                form.CancelButton = no;
            }
            else
            {
                Button ok = CreateButton("OK", DialogResult.OK, true);
                actions.Controls.Add(ok);
                form.AcceptButton = ok;
                form.CancelButton = ok;
            }

            return form.ShowDialog();
        }
    }

    internal static DialogResult ShowStartupFailure(
        string text,
        string title,
        string reportButtonText,
        string closeButtonText,
        string reportReadyText,
        string reportFailedText,
        Func<string> createReport)
    {
        using (Form form = new Form())
        {
            form.Text = title ?? "Click'n'Translate";
            form.StartPosition = FormStartPosition.CenterScreen;
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.MinimizeBox = false;
            form.MaximizeBox = false;
            form.ShowInTaskbar = true;
            form.BackColor = Color.FromArgb(16, 17, 20);
            form.ForeColor = Color.FromArgb(245, 245, 247);
            form.ClientSize = new Size(620, 285);
            form.Font = new Font("Segoe UI", 10F, FontStyle.Regular, GraphicsUnit.Point);

            Label message = new Label
            {
                AutoSize = false,
                Text = text ?? string.Empty,
                ForeColor = form.ForeColor,
                BackColor = form.BackColor,
                Location = new Point(24, 20),
                Size = new Size(572, 190),
                TextAlign = ContentAlignment.MiddleLeft,
            };
            form.Controls.Add(message);

            FlowLayoutPanel actions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.RightToLeft,
                WrapContents = false,
                Location = new Point(24, 225),
                Size = new Size(572, 40),
                BackColor = form.BackColor,
            };
            form.Controls.Add(actions);

            Button close = CreateButton(closeButtonText, DialogResult.Cancel, false);
            Button report = CreateButton(reportButtonText, DialogResult.None, true);
            report.Size = new Size(178, 34);
            report.Click += delegate
            {
                report.Enabled = false;
                try
                {
                    string path = createReport == null ? null : createReport();
                    message.Text = reportReadyText + Environment.NewLine + Environment.NewLine + path;
                    if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
                    {
                        Process.Start("explorer.exe", "/select,\"" + path + "\"");
                    }
                }
                catch (Exception error)
                {
                    message.Text = reportFailedText + Environment.NewLine + Environment.NewLine + error.Message;
                    report.Enabled = true;
                }
            };
            actions.Controls.Add(close);
            actions.Controls.Add(report);
            form.AcceptButton = report;
            form.CancelButton = close;
            return form.ShowDialog();
        }
    }

    private static Button CreateButton(string text, DialogResult result, bool primary)
    {
        Button button = new Button
        {
            Text = text,
            DialogResult = result,
            Size = new Size(112, 34),
            Margin = new Padding(8, 0, 0, 0),
            FlatStyle = FlatStyle.Flat,
            BackColor = primary ? Color.FromArgb(121, 89, 160) : Color.FromArgb(33, 31, 40),
            ForeColor = Color.White,
            UseVisualStyleBackColor = false,
        };
        button.FlatAppearance.BorderColor = Color.FromArgb(128, 96, 168);
        button.FlatAppearance.MouseOverBackColor = Color.FromArgb(115, 83, 151);
        return button;
    }
}
