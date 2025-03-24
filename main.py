import sys
import os
from manga_viewer import MangaViewer
from PyQt5.QtWidgets import QApplication
import manga_logger as log

def main():
    app = QApplication(sys.argv)
    viewer = MangaViewer()
    
    # 记录启动信息
    log.info("漫画阅读器启动")
    log.info(f"当前工作目录: {os.getcwd()}")
    
    # 记录命令行参数
    if len(sys.argv) > 1:
        log.info(f"启动参数: {sys.argv[1:]}")
    
    viewer.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()