#define AppId "openopm"
#define AppName "OpenOPM Editor"
#define AppVersion "0.0.4"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher="OpenOPM"
DefaultDirName={autopf}\OpenOPM
DefaultGroupName=OpenOPM
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=OpenOPM-setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\OpenOPM.exe

[Files]
Source: "dist\OpenOPM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OpenOPM"; Filename: "{app}\OpenOPM.exe"
Name: "{userdesktop}\OpenOPM"; Filename: "{app}\OpenOPM.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Přidat zástupce na ploše"; Flags: unchecked

[Run]
Filename: "{app}\OpenOPM.exe"; Description: "Spustit OpenOPM"; Flags: nowait postinstall skipifsilent

