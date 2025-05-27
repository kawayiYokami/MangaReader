import sys
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from qfluentwidgets import (
    NavigationInterface,
    NavigationItemPosition,
    FluentWindow,
    SplashScreen,
    InfoBar,
    InfoBarPosition,
    setTheme,
    Theme,
    SplitFluentWindow,
    isDarkTheme,
)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import NavigationItemPosition, FluentWindow, SubtitleLabel, setFont
from views.manga_browser_interface import MangaBrowserInterface
from views.settings_interface import SettingsInterface
import sys
from core.config import config


class MainWindow(SplitFluentWindow):
    def __init__(self):
        super().__init__()

        # 创建并设置导航栏
        self.initWindow()

        theme = config.themeMode.value

        # 为什么这个setTheme这么反人类？
        if theme == Theme.LIGHT:
            setTheme(Theme.DARK)
            setTheme(Theme.LIGHT)
        elif theme == Theme.DARK:
            setTheme(Theme.LIGHT)
            setTheme(Theme.DARK)
        elif theme == Theme.AUTO:
            setTheme(Theme.LIGHT)
            setTheme(Theme.DARK)
            setTheme(Theme.AUTO)

        # 统一实例化MangaManager
        from core.manga_manager import MangaManager
        self.manga_manager = MangaManager()
        
        # 添加漫画浏览器页面
        self.manga_browser_interface = MangaBrowserInterface(self, self.manga_manager)
        self.manga_browser_interface.setObjectName("mangaBrowserInterface")
        self.addSubInterface(
            self.manga_browser_interface, FIF.LIBRARY, "漫画", isTransparent=True
        )

        # 添加设置页面
        self.settings_interface = SettingsInterface(self, self.manga_manager)
        self.settings_interface.setObjectName("settingsInterface")
        self.addSubInterface(
            self.settings_interface,
            icon=FIF.SETTING,
            text="设置",
            position=NavigationItemPosition.BOTTOM,
            isTransparent=True,
        )

    def init_navigation(self):
        # 设置导航栏的属性
        self.navigationInterface.setExpandWidth(200)
        self.navigationInterface.setMinimumWidth(48)

        # 添加分隔线
        self.navigationInterface.addSeparator()

        # 添加底部分隔线
        self.navigationInterface.addSeparator(NavigationItemPosition.BOTTOM)

    def initWindow(self):
        self.resize(1200, 800)
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)


if __name__ == "__main__":
    # 循环设置主题直到匹配

    # 设置高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 创建并显示主窗口
    w = MainWindow()
    w.show()

    sys.exit(app.exec_())
