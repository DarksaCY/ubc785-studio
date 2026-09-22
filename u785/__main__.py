import sys

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import QApplication


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("UBC785 Studio")

    # The language must be set before UI modules are imported: some labels are module-level.
    from . import i18n
    i18n.set_language(QSettings("u785", "studio").value("language", "en"))

    from .ui import theme
    theme.apply(app)
    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
