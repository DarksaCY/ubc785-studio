"""Build a single-file Windows executable: python tools/build.py -> dist/UBC785Studio.exe"""
import os
import sys

import PyInstaller.__main__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from u785 import __version__  # noqa: E402

VERSION_INFO = f"""
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({__version__.replace('.', ', ')}, 0), prodvers=({__version__.replace('.', ', ')}, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('ProductName', 'UBC785 Studio'),
    StringStruct('FileDescription', 'UBC785 Studio - Uniden UBC785XLT control and programming'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('ProductVersion', '{__version__}'),
    StringStruct('OriginalFilename', 'UBC785Studio.exe')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"""


def main():
    os.chdir(ROOT)
    os.makedirs("build", exist_ok=True)
    version_file = os.path.join("build", "version_info.txt")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO)
    PyInstaller.__main__.run([
        "ubc785studio.py",
        "--name", "UBC785Studio",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", os.path.join("u785", "assets", "icon.ico"),
        "--add-data", f"{os.path.join('u785', 'assets')}{os.pathsep}{os.path.join('u785', 'assets')}",
        "--version-file", version_file,
        # Qt parts the app never uses — keeps the exe smaller.
        "--exclude-module", "PyQt5.QtWebEngineWidgets",
        "--exclude-module", "PyQt5.QtWebEngineCore",
        "--exclude-module", "PyQt5.QtMultimedia",
        "--exclude-module", "PyQt5.QtQml",
        "--exclude-module", "PyQt5.QtQuick",
        "--exclude-module", "PyQt5.QtNetwork",
        "--exclude-module", "tkinter",
    ])
    print(f"\nBuilt dist/UBC785Studio.exe (v{__version__})")


if __name__ == "__main__":
    main()
