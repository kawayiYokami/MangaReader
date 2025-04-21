from PyQt5.QtCore import Qt, QSize  # 导入Qt核心模块和尺寸类
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QGridLayout
from qfluentwidgets import CardWidget, PushButton, InfoBar, InfoBarPosition, BodyLabel
from ui.new_interface.control_panel import ControlPanel
from core.manga_manager import MangaManager  # 导入漫画管理模块
from core.manga_model import MangaLoader  # 导入漫画加载模块
from qfluentwidgets import ImageLabel
from PyQt5.QtGui import QPixmap, QImage  # 导入图像处理相关类
import time, os
import cv2  # 导入OpenCV库
from qfluentwidgets import SmoothScrollArea  # 导入平滑滚动区域组件

class MangaViewer(CardWidget):
    """
    漫画查看器主类，继承自CardWidget
    功能：负责漫画图片的显示、缩放、翻页等核心功能
    """
    def __init__(self, parent=None, manga_manager=None):
        """
        初始化漫画查看器
        :param parent: 父组件
        :param manga_manager: 漫画管理器实例，可选
        """
        super().__init__(parent)
        self.parent = parent
        # 使用传入的管理器或新建实例
        self.manga_manager = manga_manager or MangaManager()  
        self.display_mode = 'single'  # 默认单页模式
        self.reading_order = 'right_to_left'  # 添加阅读顺序变量，默认从右到左
        self.manga_loader = MangaLoader()  # 创建漫画加载器实例
        
        # 连接信号槽
        self.manga_manager.current_manga_changed.connect(self.on_current_manga_changed)
        self.manga_manager.page_changed.connect(self.on_page_changed)
        
        # 初始化控制面板显示状态
        self.control_panel_visible = False
        
        self.setup_ui()  # 初始化UI
        
        # 重写窗口大小变化事件处理
        self.resizeEvent = self.on_resize
        
        # 启用键盘和滚轮事件
        self.setFocusPolicy(Qt.StrongFocus)
        self.grabKeyboard()
        
    def setup_ui(self):
        """
        初始化用户界面布局，实现图像区域覆盖整个窗口，控制面板悬浮底部的效果。
        """
        # *** 使用 QGridLayout 作为主布局，这是实现组件重叠的关键 ***
        self.layout = QGridLayout(self) # <-- 将主布局改为 QGridLayout
        # 移除主布局的内边距和单元格间距，让内容充满窗口
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0) # 移除单元格之间的间距
        
        # 设置鼠标追踪，以便接收鼠标移动事件
        self.setMouseTracking(True)

        # --- 1. 图像显示区域 (SmoothScrollArea 包含 BodyLabel) ---
        # 我们保留 scroll_area 和 scroll_container + image_area 的结构
        # 因为 scroll_area 负责滚动，而 scroll_container 的 QVBoxLayout
        # 负责让 image_area 在滚动区域内水平居中显示。

        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setStyleSheet("border: none; background: transparent;")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # 确保滚动区域可以伸展
        self.scroll_area.setAttribute(Qt.WA_TransparentForMouseEvents) # 允许鼠标事件穿透
        
        # 创建滚动区域内部的容器和图像标签
        scroll_container = QWidget()
        scroll_container.setLayout(QVBoxLayout())
        scroll_container.layout().setContentsMargins(0, 0, 0, 0)
        scroll_container.layout().setSpacing(0) # 移除容器内部布局的间距

        self.image_area = ImageLabel("请选择一本漫画开始阅读")
        self.image_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # 图像标签可以伸展
        # 根据之前的调试，为了保持纵横比并实现高质量缩放，建议手动缩放 QPixmap
        # 因此在这里禁用 QLabel (BodyLabel) 的自动缩放
        self.image_area.setScaledContents(False) # <-- 禁用自动拉伸内容
        self.image_area.setAlignment(Qt.AlignCenter) # 设置图像在标签内部居中 (当图片小于标签时)

        # 将图像标签添加到容器的布局中，并确保在 QVBoxLayout 中水平居中
        scroll_container.layout().addWidget(self.image_area, 0, Qt.AlignCenter)

        # 将容器设置为滚动区域的 widget
        self.scroll_area.setWidget(scroll_container)
        # self.scroll_area.setWidgetResizable(True) # 已经设置过一次，可以省略

        # --- 2. 控制面板 ---
        self.control_panel = ControlPanel(self)
        # 控制面板的尺寸策略：水平伸展以适应窗口宽度，垂直固定或首选，不应伸展并挤压背景
        self.control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # <-- 垂直策略 Fixed 或 Preferred

        # --- 将组件添加到 QGridLayout 的同一个单元格中实现重叠 ---
        # 将 scroll_area (作为背景) 添加到网格布局的 (0, 0) 单元格，跨 1 行 1 列
        # 它应该伸展以填充整个单元格 (整个窗口)
        self.layout.addWidget(self.scroll_area, 0, 0, 1, 1) # row 0, col 0, row span 1, col span 1

        # 将 control_panel (作为前景覆盖层) 也添加到网格布局的 **同一个** (0, 0) 单元格
        # 使用对齐标志将其放在单元格的底部中央
        self.layout.addWidget(self.control_panel, 0, 0, 1, 1, Qt.AlignBottom | Qt.AlignHCenter)
        # Qt.AlignBottom: 贴近单元格底部
        # Qt.AlignHCenter: 在单元格中水平居中

        # --- 配置网格布局的伸展因子 ---
        # 让 (0, 0) 单元格所在的行和列可以伸展，这样 scroll_area 会填充整个窗口
        self.layout.setRowStretch(0, 1) # 第 0 行可伸展
        self.layout.setColumnStretch(0, 1) # 第 0 列可伸展

        self.control_panel.raise_() # <-- 添加这一行
        
        # 初始化时隐藏控制面板
        self.control_panel.hide()

        # 移除之前 QVBoxLayout 中添加 image_container 和 overlay 的代码，
        # 因为组件现在直接添加到 QGridLayout 中了。
        # 也不再需要 image_container 和 overlay 这两个额外的 QWidget 容器。

    def on_current_manga_changed(self, manga):
        """
        当前漫画变更时的处理函数
        :param manga: 当前选中的漫画对象
        """
        if manga:
            self.current_manga = manga
            self.update_display()  # 更新显示
        else:
            self.image_area.setText("请选择一本漫画开始阅读")
    
    def on_page_changed(self, page):
        """
        页码变更时的处理函数
        :param page: 当前页码
        """
        if hasattr(self, 'current_manga'):
            self.update_display()
            
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Left:
            self.prev_page()
        elif event.key() == Qt.Key_Right:
            self.next_page()
        else:
            super().keyPressEvent(event)
            
    def wheelEvent(self, event):
        """滚轮事件处理"""
        if event.angleDelta().y() > 0:
            self.prev_page()
        else:
            self.next_page()
            
    def prev_page(self):
        """上一页"""
        if self.manga_manager and hasattr(self.manga_manager, 'current_manga') and self.manga_manager.current_manga:
            current_page = self.manga_manager.current_page
            step = 2 if self.display_mode == 'double' else 1
            if self.reading_order == 'right_to_left':
                if current_page >= step:
                    self.manga_manager.change_page(current_page - step)
            else:
                if current_page < self.manga_manager.current_manga.total_pages - step:
                    self.manga_manager.change_page(current_page + step)

    def next_page(self):
        """下一页"""
        if self.manga_manager and hasattr(self.manga_manager, 'current_manga') and self.manga_manager.current_manga:
            current_page = self.manga_manager.current_page
            step = 2 if self.display_mode == 'double' else 1
            if self.reading_order == 'right_to_left':
                if current_page < self.manga_manager.current_manga.total_pages - step:
                    self.manga_manager.change_page(current_page + step)
            else:
                if current_page >= step:
                    self.manga_manager.change_page(current_page - step)
                    
    def on_resize(self, event):
        super().resizeEvent(event)
        self.update_display()

    def convert_image_to_pixmap(self, image):
        """
        将OpenCV图像转换为QPixmap
        :param image: OpenCV图像对象(numpy数组)
        :return: QPixmap对象
        """
        if image is not None:
            # 将numpy数组转换为QImage
            height, width = image.shape[:2]
            bytes_per_line = 3 * width
            qim = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qim)
            return pixmap
        return QImage()
     
    def get_page_image(self, current_page):
        """
        获取指定页面的图像
        :param current_page: 当前页码
        :return: OpenCV图像对象(numpy数组)
        """
        if not hasattr(self, 'current_manga') or not self.current_manga:
            return None
        if current_page < 0 or current_page >= self.current_manga.total_pages:
            return None
            
        # 记录开始时间
        start_time = time.time()
        
        # 获取原始图片
        image = self.manga_loader.get_page_image(self.current_manga, current_page)
        load_time = time.time()

        return image

    def scale_pixmap(self, pixmap):
        """缩放图片到合适大小"""
        if not pixmap or pixmap.isNull():
            return None
        
        # 获取容器尺寸作为缩放基准，并减去10像素留出滚动条空间
        adjusted_size = self.scroll_area.size()
        if adjusted_size.width() <= 0 or adjusted_size.height() <= 0:
            return None
            
        # 使用调整后的尺寸进行高质量缩放
        return pixmap.scaled(
            adjusted_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation  # 使用平滑变换
        ).scaled(
            adjusted_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation  # 二次平滑变换提升质量
        )

    def should_combine_pages(self, current_image, next_image) -> bool:
        if current_image is None or next_image is None or len(current_image.shape) < 2 or len(next_image.shape) < 2:
            return False
    
        height_diff = abs(current_image.shape[0] - next_image.shape[0])
        if height_diff > max(current_image.shape[0], next_image.shape[0]) * 0.1:
            return False
    
        available_size = self.scroll_area.size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            return False
    
        combined_width = current_image.shape[1] + next_image.shape[1]
        return combined_width * available_size.height() <= available_size.width() * current_image.shape[0]

    def combine_images(self, image1, image2):
        """合并两张图片为一张，自动调整高度一致"""
        try:
            # 如果高度不一致，先缩放到相同高度
            if image1.shape[0] != image2.shape[0]:
                # 取较大的高度作为基准
                target_height = max(image1.shape[0], image2.shape[0])
                
                # 计算等比例缩放后的宽度
                width1 = int(image1.shape[1] * (target_height / image1.shape[0]))
                width2 = int(image2.shape[1] * (target_height / image2.shape[0]))
                
                # 使用OpenCV进行高质量缩放
                image1 = cv2.resize(image1, (width1, target_height), 
                                  interpolation=cv2.INTER_LANCZOS4)
                image2 = cv2.resize(image2, (width2, target_height), 
                                  interpolation=cv2.INTER_LANCZOS4)
            
            # 计算合并后的尺寸
            width = image1.shape[1] + image2.shape[1]
            height = image1.shape[0]  # 现在高度已经一致
            
            # 根据阅读顺序决定合并方向
            if self.reading_order == 'right_to_left':
                left_image, right_image = image1, image2
            else:
                left_image, right_image = image2, image1
                
            # 使用OpenCV进行图像拼接
            combined = cv2.hconcat([left_image, right_image])
            return combined
        except Exception as e:
            print(f"合并图像时发生错误: {str(e)}")
            return None

    def update_display(self):
        """
        更新显示的图像
        处理单页/双页模式切换和图像显示
        """
        if not hasattr(self, 'current_manga') or not self.current_manga:
            self.image_area.setText("请选择一本漫画开始阅读")
            return
            
        current_page = self.manga_manager.current_page
        if current_page < 0 or current_page >= self.current_manga.total_pages:
            self.image_area.setText("页码超出范围")
            return
            
        # 获取当前页图片
        current_image = self.get_page_image(current_page)
        if current_image is None or current_image.size == 0:
            self.image_area.setText("无法获取图像")
            return
            
        # 判断并处理双页合并
        display_image = current_image
        next_page_index = current_page + 1
        if next_page_index < self.current_manga.total_pages:
            next_image = self.get_page_image(next_page_index)
            if next_image is not None and next_image.size > 0 and self.should_combine_pages(current_image, next_image):
                combined = self.combine_images(current_image, next_image)
                if combined is not None and combined.size > 0:
                    display_image = combined
                    self.display_mode = 'double'
                else:
                    self.display_mode = 'single'
            else:
                self.display_mode = 'single'
        else:
            self.display_mode = 'single'
        
        # 转换并缩放图片
        pixmap = self.convert_image_to_pixmap(display_image)
        scaled_pixmap = self.scale_pixmap(pixmap)
        
        if scaled_pixmap and not scaled_pixmap.isNull():
            self.image_area.setPixmap(scaled_pixmap)
            if hasattr(self, 'control_panel'):
                self.control_panel.update_page_label()
        else:
            self.image_area.setText("无法加载图像")
            
    def toggle_reading_order(self):
        """切换阅读顺序（从左到右/从右到左）并返回当前状态"""
        self.reading_order = 'left_to_right' if self.reading_order == 'right_to_left' else 'right_to_left'
        return self.reading_order
        
    def mouseMoveEvent(self, event):
        """鼠标移动事件处理"""
        # 获取窗口高度和鼠标Y坐标
        window_height = self.height()
        mouse_y = event.pos().y()
        
        # 定义底部区域的高度（像素）
        bottom_area_height = 100
        
        # 检查鼠标是否在底部区域
        if mouse_y > window_height - bottom_area_height:
            if not self.control_panel_visible:
                self.control_panel.show()
                self.control_panel_visible = True
        else:
            if self.control_panel_visible:
                self.control_panel.hide()
                self.control_panel_visible = False
                
    def leaveEvent(self, event):
        """鼠标离开事件处理"""
        if self.control_panel_visible:
            self.control_panel.hide()
            self.control_panel_visible = False


