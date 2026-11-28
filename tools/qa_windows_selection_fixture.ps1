param([Parameter(Mandatory)][string]$Exchange)

$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'This fixture requires a disposable GitHub-hosted desktop.'
}
Add-Type -AssemblyName PresentationFramework
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="ClicknTranslate Windows acceptance fixture" Width="510" Height="260"
        Left="24" Top="32" WindowStartupLocation="Manual">
  <StackPanel Margin="12">
    <TextBlock Text="First editor"/>
    <TextBox x:Name="First" Text="First: identical selection."/>
    <TextBlock Text="Second editor"/>
    <TextBox x:Name="Second" Text="Second: identical selection."/>
    <DataGrid x:Name="Grid" Margin="0,12,0,0" Height="84" IsReadOnly="True"
              AutoGenerateColumns="False" CanUserAddRows="False" SelectionUnit="FullRow">
      <DataGrid.Columns><DataGridTextColumn Header="Row" Width="*" Binding="{Binding Label}"/></DataGrid.Columns>
    </DataGrid>
  </StackPanel>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Parse($xaml)
$first = $window.FindName('First')
$second = $window.FindName('Second')
$grid = $window.FindName('Grid')
$row = [PSCustomObject]@{ Label = 'Table row without a text range' }
$grid.Items.Add($row) | Out-Null
$events = [Collections.Generic.List[object]]::new()
foreach ($routedEvent in @([Windows.Input.Keyboard]::PreviewKeyDownEvent, [Windows.Input.Keyboard]::PreviewKeyUpEvent)) {
    $window.AddHandler($routedEvent, [Windows.Input.KeyEventHandler]{
        param($sender, $eventArgs)
        $key = if ($eventArgs.Key -eq 'System') { $eventArgs.SystemKey } else { $eventArgs.Key }
        $events.Add(@{ event = $eventArgs.RoutedEvent.Name; key = [string]$key
                       focus = $eventArgs.OriginalSource.Name; modifiers = [string]$eventArgs.KeyboardDevice.Modifiers })
    }, $true)
}

$script:sequence = 0
$timer = [Windows.Threading.DispatcherTimer]::new()
$timer.Interval = [TimeSpan]::FromMilliseconds(15)
$timer.Add_Tick({
    $request = Join-Path $Exchange "request-$script:sequence.json"
    if (-not [IO.File]::Exists($request)) { return }
    $reply = Join-Path $Exchange "reply-$script:sequence.json"
    $script:sequence++
    try {
        $op = [IO.File]::ReadAllText($request) | ConvertFrom-Json
        if ($op -eq 'reset-first') { $first.Text = 'First: identical selection.' }
        if ($op -in @('first', 'second')) {
            $editor = if ($op -eq 'first') { $first } else { $second }
            $window.Activate() | Out-Null
            $editor.Focus() | Out-Null
            [Windows.Input.Keyboard]::Focus($editor) | Out-Null
            $editor.Select($editor.Text.IndexOf('identical selection'), 'identical selection'.Length)
        }
        if ($op -eq 'clear-events') { $events.Clear() }
        $grid.ScrollIntoView($row)
        $grid.UpdateLayout()
        $cellText = $grid.Columns[0].GetCellContent($row)
        $point = $cellText.PointToScreen([Windows.Point]::new(6, 6))
        $handle = [Windows.Interop.WindowInteropHelper]::new($window).Handle
        $focused = [Windows.Input.Keyboard]::FocusedElement
        $state = @{
            pid = $PID; hwnd = $handle.ToInt64(); active = $window.IsActive
            first = $first.Text; second = $second.Text
            selected = @($first.SelectedText, $second.SelectedText)
            focus = if ($focused) { $focused.GetType().Name } else { '' }
            firstFocused = $first.IsKeyboardFocused; secondFocused = $second.IsKeyboardFocused
            gridFocused = $grid.IsKeyboardFocusWithin; selectedRow = $grid.SelectedIndex
            gridPoint = @([int]$point.X, [int]$point.Y); keys = $events.ToArray()
        }
    } catch {
        $state = @{ error = $_.Exception.ToString() }
    }
    [IO.File]::WriteAllText("$reply.tmp", (ConvertTo-Json -InputObject $state -Depth 5 -Compress))
    [IO.File]::Move("$reply.tmp", $reply)
    if ($op -eq 'quit') {
        $timer.Stop()
        $window.Close()
    }
})
$timer.Start()
$window.ShowDialog() | Out-Null
