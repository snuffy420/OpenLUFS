# OpenLUFS installation

## Download and install

Choose the option for your computer:

| Platform / package | What you get | How to start |
| --- | --- | --- |
| **Windows x64 — installer** | The complete app, an uninstaller, Start menu entries and an optional desktop shortcut | [Download Setup](https://github.com/snuffy420/OpenLUFS/releases/download/v1.3.0/OpenLUFS-1.3.0-windows-x64-setup.exe), open it, and follow the steps below |
| **Windows x64 — portable** | The complete app in a folder; no installation or Python required | [Download Portable](https://github.com/snuffy420/OpenLUFS/releases/download/v1.3.0/OpenLUFS-1.3.0-windows-x64-portable.7z), extract it, then run `OpenLUFS.exe` |
| **Windows — Python source** | The application source and Windows audio tools | [Download Source](https://github.com/snuffy420/OpenLUFS/releases/download/v1.3.0/OpenLUFS-1.3.0-source.7z), then follow [Windows source setup](#windows-source-setup) |
| **macOS — Python source** | Source setup for Intel and Apple silicon Macs, with or without a venv | [Download Source ZIP](https://github.com/snuffy420/OpenLUFS/archive/refs/heads/main.zip), then follow [macOS setup](#macos-source-setup) |
| **Linux — Python source** | Source setup for supported 64-bit Linux systems, with or without a venv | [Download Source ZIP](https://github.com/snuffy420/OpenLUFS/archive/refs/heads/main.zip), then follow [Linux setup](#linux-source-setup) |

**Windows 10/11 x64 builds are tested.** macOS and Linux use native Python, Qt and audio tools; their setup paths are provided, but native GUI/audio testing on those operating systems is still pending. There is no packaged Mac app or Linux executable in this release.

### Windows installer

1. Download `OpenLUFS-1.3.0-windows-x64-setup.exe` from [Releases](https://github.com/snuffy420/OpenLUFS/releases).
2. Double-click the downloaded file. Accept the Windows administrator prompt to install under **Program Files**.
3. Follow the setup pages. Leave the installation folder at its default unless you have a reason to change it.
4. Tick **Create a desktop shortcut** if you want one. It is optional.
5. Select **Install**, then **Finish**. Open OpenLUFS from the Start menu or your chosen shortcut.

Python, Qt, FFmpeg and the gain tool are included. No separate audio-tool installation is required. To remove it later, use **Windows Settings → Apps → Installed apps / Apps & features → OpenLUFS → Uninstall**, or the Start menu uninstaller. Installed copies save preferences under `%LOCALAPPDATA%\OpenLUFS`, so the app does not need administrator rights when you use it. Uninstalling keeps your preferences and does not remove your music or exports.

### Windows portable

1. Download `OpenLUFS-1.3.0-windows-x64-portable.7z`.
2. Extract the **entire archive** with a compatible archive extractor, such as [7-Zip](https://www.7-zip.org/).
3. Open the extracted **OpenLUFS** folder and double-click **OpenLUFS.exe**.

Keep the folder somewhere you can write to, such as Documents. Run the extracted executable rather than opening it inside the archive. The portable app remembers settings beside the executable and does not create an Add/Remove Programs entry. Python and the audio tools are included; 7-Zip is only needed to extract the download, not to run OpenLUFS.

### macOS source setup

Use a current 64-bit Intel or Apple silicon Mac. These steps use Python 3.12 and Homebrew.

**1. Install the prerequisites once.** Open **Terminal** from Applications → Utilities. If Homebrew is not installed, follow the instructions at [brew.sh](https://brew.sh/) and its printed **Next steps**, then open a new Terminal window. Run:

```bash
brew install python@3.12 ffmpeg
python3.12 --version
ffmpeg -version
```

Homebrew may ask for your Mac password or Apple's command-line tools. Let it finish; passwords typed into Terminal are not displayed.

**2. Download and open the source folder.** Download the [Source ZIP](https://github.com/snuffy420/OpenLUFS/archive/refs/heads/main.zip), then double-click it in Downloads to extract it. In Terminal, enter:

```bash
cd ~/Downloads/OpenLUFS-main
```

If your folder has another name, type `cd ` with a space after it, drag the extracted folder from Finder into Terminal, and press Return. The folder should contain `norm.py`, `setup.sh` and `run.sh`.

**3. Choose one setup method.** A venv is a private Python environment for this app. It is recommended, and the scripts handle activation for you:

```bash
bash setup.sh
bash run.sh
```

**Without a venv**, use this instead:

```bash
bash setup.sh --no-venv
bash run.sh
```

The no-venv method keeps dependencies in `.python-deps` inside the source folder. It uses your normal Python interpreter without installing packages into macOS's or Homebrew's shared Python environment. Both methods download the checksum-verified native `mp3rgain` helper automatically.

**Next time:** open Terminal, return to the same source folder, and run `bash run.sh`. Setup is only needed again when installing or updating dependencies. Keep the extracted source folder; it contains the app. Preferences are stored in `~/Library/Application Support/OpenLUFS`.

### Linux source setup

These commands target **Ubuntu 24.04 or later** with a desktop session. Other distributions need equivalent Python, FFmpeg and Qt/X11 libraries. Use a supported x64 or ARM64 system with Python wheels available for the supplied dependencies.

**1. Install the prerequisites once.** Open Terminal, usually with **Ctrl+Alt+T**, then run:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg libegl1 libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0 fonts-dejavu-core
python3 --version
ffmpeg -version
```

Enter your login password if asked. Terminal does not display password characters. Python must be **3.11 or later**; these scripts prefer Python 3.12 when available and currently select Python 3.11–3.14.

**2. Download and open the source folder.** Download the [Source ZIP](https://github.com/snuffy420/OpenLUFS/archive/refs/heads/main.zip), extract it in Downloads, then run:

```bash
cd ~/Downloads/OpenLUFS-main
```

If the folder name differs, use your file manager's **Open in Terminal** command inside the extracted folder, or type `cd ` and drag the folder into Terminal. Check that it contains `setup.sh` and `norm.py`.

**3. Choose one setup method.** With a venv, recommended:

```bash
bash setup.sh
bash run.sh
```

Without a venv:

```bash
bash setup.sh --no-venv
bash run.sh
```

The no-venv method installs into the source folder's `.python-deps` directory, not the operating system's Python packages. Neither method needs `sudo` for Python dependencies, and neither uses `--break-system-packages`. Both download the verified native gain tool for the detected CPU.

**Next time:** return to the same folder and run `bash run.sh`. Preferences are saved in `~/.config/openlufs`, or under `XDG_CONFIG_HOME` when configured.

### Windows source setup

Install **Python 3.12** from [python.org](https://www.python.org/downloads/windows/), selecting **Add Python to PATH** if offered. Download and extract the source archive, then open Terminal / PowerShell in the extracted folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/fetch_ffmpeg.py
.\.venv\Scripts\python.exe tools/fetch_mp3rgain.py
.\.venv\Scripts\python.exe norm.py
```

Later, launch **Run OpenLUFS.cmd**, or repeat the last command from this folder. The source release already includes the Windows audio executables; the fetch commands verify/download them for a GitHub checkout.

### Source setup troubleshooting

- **`brew`, `python3.12` or `ffmpeg` not found:** complete the prerequisite installation, follow Homebrew's PATH instructions where applicable, and open a new Terminal window.
- **`setup.sh` / `norm.py` not found:** Terminal is in the wrong folder. Open the extracted OpenLUFS folder in Terminal and try again.
- **`externally-managed-environment`:** use the supplied `bash setup.sh` or `bash setup.sh --no-venv` commands. Both avoid installing into system-managed Python.
- **`No matching distribution found`:** your Python, OS or CPU may not have a compatible wheel. Try Python 3.12 on a current supported operating system; do not force an incompatible package.
- **Linux Qt platform-plugin error:** confirm the listed desktop libraries are installed. This is a desktop application; a headless server needs an appropriate display setup.
- **Missing gain tool:** rerun setup, or run `python3 tools/fetch_mp3rgain.py` from the source folder. The app also checks `mp3rgain` on PATH and supports `OPENLUFS_MP3RGAIN` / `OPENLUFS_FFMPEG` for custom native tool paths.

The CLI uses the same engine. From a configured Mac/Linux source folder, use `bash run.sh normalize --help`; on Windows use `.\.venv\Scripts\python.exe -m openlufs normalize --help`.

