using System;
using System.Drawing;
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
