#define MyAppName "Click'n'Translate"
#ifndef MyAppVersion
  #define MyAppVersion "1.6.1"
#endif
#ifndef SourceDir
  #define SourceDir "..\releases\ClicknTranslate-v" + MyAppVersion + "-win64-stage\ClicknTranslate"
#endif
#ifndef ReleaseDir
  #define ReleaseDir "..\releases"
#endif
#ifndef MyAppId
  #define MyAppId "{{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName}
AppPublisher=Jabrail Digital
AppPublisherURL=https://github.com/jabrailkhalil/clickntranslate
AppSupportURL=https://github.com/jabrailkhalil/clickntranslate/issues
AppUpdatesURL=https://github.com/jabrailkhalil/clickntranslate/releases/latest
DefaultDirName={localappdata}\Programs\ClicknTranslate
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=ClicknTranslate-Setup-v{#MyAppVersion}-win64
SetupIconFile=..\icons\icon.ico
UninstallDisplayIcon={app}\ClicknTranslate.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
CloseApplicationsFilter=*.*
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany=Jabrail Digital
VersionInfoDescription=Click'n'Translate Windows installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
english.MainExecutableMissing=The main application file was blocked or removed while it was being installed.%n%nCheck the antivirus quarantine, allow the ClicknTranslate folder, and run this installer again.
russian.MainExecutableMissing=Основной файл программы был заблокирован или удалён во время установки.%n%nПроверьте карантин антивируса, добавьте папку ClicknTranslate в исключения и запустите установщик ещё раз.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "data\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\ClicknTranslate.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\ClicknTranslate.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ClicknTranslate.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and
     (not FileExists(ExpandConstant('{app}\app\ClicknTranslateApp.exe'))) then
  begin
    Log('ClicknTranslateApp.exe is missing after file installation. Antivirus quarantine is likely.');
    RaiseException(CustomMessage('MainExecutableMissing'));
  end;
end;
