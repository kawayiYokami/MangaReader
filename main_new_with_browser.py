import sys
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from qfluentwidgets import (NavigationInterface, NavigationItemPosition, 
                           FluentWindow, SplashScreen, InfoBar, InfoBarPosition,
                           setTheme, Theme)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import NavigationItemPosition, FluentWindow, SubtitleLabel, setFont
from views.manga_browser_interface import MangaBrowserInterface


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
       
        # 创建并设置导航栏
        self.initWindow()
        
        # 添加新的漫画浏览器页面
        self.manga_browser_interface = MangaBrowserInterface(self)
        self.manga_browser_interface.setObjectName("mangaBrowserInterface")
        self.addSubInterface(self.manga_browser_interface, FIF.LIBRARY, '新版漫画浏览器', isTransparent=True)
    
    def init_navigation(self):
        # 设置导航栏的属性
        self.navigationInterface.setExpandWidth(200)
        self.navigationInterface.setMinimumWidth(48)
        
        # 添加分隔线
        self.navigationInterface.addSeparator()

    def initWindow(self):
        self.setWindowTitle('漫画阅读器 2.0')
        self.resize(1200, 800)


if __name__ == '__main__':
    # 设置高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
   
    app = QApplication(sys.argv)
    
    # 设置应用主题为亮色主题
    setTheme(Theme.DARK)
    
    # 创建并显示主窗口
    w = MainWindow()
    w.show()
    
    sys.exit(app.exec_())