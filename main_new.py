import sys
from PyQt5.QtWidgets import QApplication
from ui.manga_viewer_new import MangaViewer
from utils import manga_logger as log

def main():
    log.info("启动漫画查看器应用程序")
    app = QApplication(sys.argv)
    viewer = MangaViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()