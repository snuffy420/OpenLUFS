#ifndef BuildVersion
#define BuildVersion "1.3.0"
#endif
#ifndef PayloadDir
#error PayloadDir must point to the verified portable payload.
#endif
#define SourceRoot AddBackslash(SourcePath) + ".."
[Setup]
AppId={{6AD6510C-6D8E-4320-B936-82DE68D63130}
AppName=OpenLUFS
AppVersion={#BuildVersion}
AppVerName=OpenLUFS {#BuildVersion}
AppPublisher=zerØ software / snuffy420
AppPublisherURL=https://github.com/snuffy420
AppSupportURL=https://github.com/snuffy420/OpenLUFS/issues
AppUpdatesURL=https://github.com/snuffy420/OpenLUFS/releases
DefaultDirName={autopf}\OpenLUFS
DefaultGroupName=OpenLUFS
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
SetupArchitecture=x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern dark includetitlebar
WizardSizePercent=110
DisableWelcomePage=no
DisableDirPage=no
SetupIconFile={#SourceRoot}\assets\openlufs.ico
UninstallDisplayIcon={app}\OpenLUFS.exe
WizardImageFile={#SourceRoot}\assets\installer-side.bmp
WizardImageStretch=yes
WizardImageBackColor=$00161410
WizardSmallImageFile={#SourceRoot}\assets\installer-small.bmp
WizardSmallImageBackColor=$00161410
LicenseFile={#SourceRoot}\LICENSE
OutputBaseFilename=OpenLUFS-{#BuildVersion}-windows-x64-setup
Compression=lzma2/fast
SolidCompression=yes
LZMANumBlockThreads=2
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
UninstallDisplayName=OpenLUFS {#BuildVersion}
VersionInfoVersion={#BuildVersion}.0
VersionInfoCompany=zerØ software
VersionInfoDescription=OpenLUFS x64 Setup
VersionInfoCopyright=Copyright (C) 2026 zerØ software. GPL-3.0-or-later.
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\installer\OpenLUFS.install.json"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\OpenLUFS"; Filename: "{app}\OpenLUFS.exe"; WorkingDir: "{app}"; IconFilename: "{app}\OpenLUFS.exe"; AppUserModelID: "OpenLUFS.Desktop.1"
Name: "{group}\Uninstall OpenLUFS"; Filename: "{uninstallexe}"
Name: "{autodesktop}\OpenLUFS"; Filename: "{app}\OpenLUFS.exe"; WorkingDir: "{app}"; IconFilename: "{app}\OpenLUFS.exe"; Tasks: desktopicon; AppUserModelID: "OpenLUFS.Desktop.1"
[Run]
Filename: "{app}\OpenLUFS.exe"; Description: "Open OpenLUFS"; Flags: nowait postinstall skipifsilent runasoriginaluser
[Messages]
WelcomeLabel1=Install OpenLUFS
WelcomeLabel2=Setup will install OpenLUFS on your computer.%n%nChoose whether to create a desktop shortcut. You can uninstall OpenLUFS later from Windows Settings.%n%nCreated by snuffy420 / zerØ software.
