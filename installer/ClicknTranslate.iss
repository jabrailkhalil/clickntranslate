#define MyAppName "Click'n'Translate"
#ifndef MyAppVersion
  #define MyAppVersion "1.4.6"
#endif
#ifndef SourceDir
  #define SourceDir "..\releases\ClicknTranslate-v" + MyAppVersion + "-win64-stage\ClicknTranslate"
#endif
#ifndef ReleaseDir
  #define ReleaseDir "..\releases"
#endif

[Setup]
AppId={{70f13ecd-bf6d-4c9d-bba6-3fb112272e36}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
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
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany=Jabrail Digital
VersionInfoDescription=Click'n'Translate Windows installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "data\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\ClicknTranslate.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\ClicknTranslate.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ClicknTranslate.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
