; Inno Setup 6 Script for Ghostline
; Offline AI Question Recognition & Voice Assistance

#define MyAppName "Ghostline"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Ghostline Open Source Project"
#define MyAppURL "https://github.com/Mohammed-Ayyan/GhostLine"
#define MyAppExeName "Ghostline.exe"

[Setup]
AppId={{D37E88BC-3FA8-4E0E-8521-1D0A3C9A8B62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release_dist
OutputBaseFilename=Ghostline-Setup
SetupIconFile=ghostline.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter=Ghostline.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: none
Name: "startupicon"; Description: "Start Ghostline automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\Ghostline\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ghostline.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\ghostline.ico"; Comment: "Ghostline — 100% Offline AI Desktop Assistant"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\ghostline.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
