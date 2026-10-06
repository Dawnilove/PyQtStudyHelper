; Inno Setup script. Build with:  python tools/build_installer.py   (it passes AppVersion, StageDir, IconFile, OutDir)
#define AppName "PyQt 학습 도우미"
#define AppId "PyQtStudyHelper"

[Setup]
AppId={{B7C0E3A4-6D1F-4F57-9A53-6E5B1C2D7A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Dawnilove
AppPublisherURL=https://github.com/Dawnilove/PyQtStudyHelper
DefaultDirName={localappdata}\Programs\{#AppId}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir={#OutDir}
OutputBaseFilename={#AppId}-Setup-{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\app.ico
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
LicenseFile={#StageDir}\LICENSE

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; GroupDescription: "추가 작업:"
Name: "filemenu"; Description: "탐색기 우클릭 메뉴에 'PyQt 학습 도우미로 열기' 추가 (.py, .ui)"; GroupDescription: "추가 작업:"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#IconFile}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Registry]
; Only ADDS menu entries (HKCU, no admin). The default program for .py/.ui is never changed.
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.py\shell\{#AppId}"; ValueType: string; ValueData: "PyQt 학습 도우미로 열기"; Flags: uninsdeletekey; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.py\shell\{#AppId}"; ValueName: "Icon"; ValueType: string; ValueData: "{app}\app.ico"; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.py\shell\{#AppId}\command"; ValueType: string; ValueData: """{app}\python\pythonw.exe"" ""{app}\run.py"" ""%1"""; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ui\shell\{#AppId}"; ValueType: string; ValueData: "PyQt 학습 도우미로 열기"; Flags: uninsdeletekey; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ui\shell\{#AppId}"; ValueName: "Icon"; ValueType: string; ValueData: "{app}\app.ico"; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ui\shell\{#AppId}\command"; ValueType: string; ValueData: """{app}\python\pythonw.exe"" ""{app}\run.py"" ""%1"""; Tasks: filemenu
; "연결 프로그램" list
Root: HKCU; Subkey: "Software\Classes\{#AppId}.File"; ValueType: string; ValueData: "PyQt 학습 도우미"; Flags: uninsdeletekey; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\{#AppId}.File\DefaultIcon"; ValueType: string; ValueData: "{app}\app.ico"; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\{#AppId}.File\shell\open\command"; ValueType: string; ValueData: """{app}\python\pythonw.exe"" ""{app}\run.py"" ""%1"""; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\.py\OpenWithProgids"; ValueName: "{#AppId}.File"; ValueType: none; Flags: uninsdeletevalue; Tasks: filemenu
Root: HKCU; Subkey: "Software\Classes\.ui\OpenWithProgids"; ValueName: "{#AppId}.File"; ValueType: none; Flags: uninsdeletevalue; Tasks: filemenu

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run.py"""; WorkingDir: "{app}"; Description: "{#AppName} 지금 실행"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\error.log"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\studyhelper"
