using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

internal static class ClicknTranslateLauncher
{
    [STAThread]
    private static int Main(string[] args)
    {
        string executablePath = Assembly.GetExecutingAssembly().Location;
        string root = Path.GetDirectoryName(executablePath) ?? AppDomain.CurrentDomain.BaseDirectory;
        string innerExecutable = Path.Combine(root, "app", "ClicknTranslateApp.exe");

        try
        {
            RestoreInstallerMetadata(root);

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
