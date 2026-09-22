"""Entry point for the frozen Windows build (PyInstaller cannot run `-m u785` directly)."""
from u785.__main__ import main

if __name__ == "__main__":
    main()
