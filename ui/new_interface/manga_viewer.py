# Qt核心模块
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QSizePolicy, QGridLayout)
from PyQt5.QtGui import QPixmap, QImage

# 第三方UI组件
from qfluentwidgets import (CardWidget, PushButton, InfoBar, 
                           InfoBarPosition, BodyLabel, ImageLabel,
                           SmoothScrollArea)

# 项目内部模块
from ui.new_interface.control_panel import ControlPanel
from core.manga_manager import MangaManager
from core.manga_model import MangaLoader
from core.config import config, DisplayMode, ReadingOrder

# 标准库和第三方库
import time
import cv2

class MangaViewer(CardWidget):
    """
    漫画查看器组件，继承自CardWidget
    
    主要功能：
    - 显示单页或双页漫画图片
    - 支持图片缩放以适应窗口大小
    - 处理键盘和滚轮翻页事件
    - 根据阅读方向自动调整页面顺序
    - 提供悬浮控制面板进行交互
    
    属性：
        display_mode: 显示模式（'single'或'double'）
        reading_order: 阅读顺序（'right_to_left'或'left_to_right'）
        auto_page: 是否自动翻页
        manga_manager: 漫画管理器实例
        manga_loader: 漫画加载器实例
    """
    def __init__(self, parent=None, manga_manager=None):
        """
        初始化漫画查看器组件
        
        参数：
            parent: 父组件，用于嵌入到其他界面中
            manga_manager: 可选的漫画管理器实例，如果未提供则创建新实例
        """
        super().__init__(parent)
        self.parent = parent
        # 使用传入的管理器或新建实例
        self.manga_manager = manga_manager or MangaManager()  
        # 从管理器获取设置
        self.display_mode = config.display_mode.value
        config.display_mode.valueChanged.connect(self.update_display)
        self.reading_order = config.reading_order.value
        config.reading_order.valueChanged.connect(self.update_display)
        self.manga_loader = MangaLoader()  # 创建漫画加载器实例
        self.original_image_size = None  # 存储原始图片尺寸
        self.current_scale = 1.0  # 当前缩放比例
        self.max_scale = 1.0  # 最大缩放比例(不超过原图尺寸)
        # 连接信号槽
        self.manga_manager.current_manga_changed.connect(self.on_current_manga_changed)
        self.manga_manager.page_changed.connect(self.on_page_changed)
        
        # 初始化控制面板显示状态
        self.control_panel_visible = False
        
        # 初始化拖动相关的属性
        self.is_dragging = False
        self.last_mouse_pos = None
        
        self.setup_ui()  # 初始化UI
        
        # 重写窗口大小变化事件处理
        self.resizeEvent = self.on_resize
        
        # 启用键盘和滚轮事件
        self.setFocusPolicy(Qt.StrongFocus)
        
    def setup_ui(self):
        """
        初始化用户界面布局
        
        创建以下UI元素：
        - 主布局使用QGridLayout实现组件重叠
        - 图像显示区域使用SmoothScrollArea实现平滑滚动
        - 控制面板悬浮在图像区域底部
        
        布局特点：
        - 图像区域充满整个窗口
        - 控制面板仅在鼠标悬停时显示
        - 支持键盘和鼠标事件交互
        """
        
        self.layout = QGridLayout(self) # <-- 将主布局改为 QGridLayout
        # 移除主布局的内边距和单元格间距，让内容充满窗口
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0) # 移除单元格之间的间距
        
        # 设置鼠标追踪，以便接收鼠标移动事件
        self.setMouseTracking(True)

        

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
        self.image_area.setScaledContents(False)
        self.image_area.setAlignment(Qt.AlignCenter) # 设置图像在标签内部居中 (当图片小于标签时)

        # 将图像标签添加到容器的布局中，并确保在 QVBoxLayout 中水平居中
        scroll_container.layout().addWidget(self.image_area, 0, Qt.AlignCenter)

        # 将容器设置为滚动区域的 widget
        self.scroll_area.setWidget(scroll_container)
        

        
        self.control_panel = ControlPanel(self)
        # 控制面板的尺寸策略：水平伸展以适应窗口宽度，垂直固定或首选，不应伸展并挤压背景
        self.control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # <-- 垂直策略 Fixed 或 Preferred

        
        # 将 scroll_area (作为背景) 添加到网格布局的 (0, 0) 单元格，跨 1 行 1 列
        # 它应该伸展以填充整个单元格 (整个窗口)
        self.layout.addWidget(self.scroll_area, 0, 0, 1, 1) # row 0, col 0, row span 1, col span 1

        # 将 control_panel (作为前景覆盖层) 也添加到网格布局的 **同一个** (0, 0) 单元格
        # 使用对齐标志将其放在单元格的底部中央
        self.layout.addWidget(self.control_panel, 0, 0, 1, 1, Qt.AlignBottom | Qt.AlignHCenter)
        

        
        # 让 (0, 0) 单元格所在的行和列可以伸展，这样 scroll_area 会填充整个窗口
        self.layout.setRowStretch(0, 1) # 第 0 行可伸展
        self.layout.setColumnStretch(0, 1) # 第 0 列可伸展

        self.control_panel.raise_() # <-- 添加这一行
        
        # 初始化时隐藏控制面板
        self.control_panel.hide()

        

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
        # 只有当没有其他组件拥有焦点时才处理方向键事件
        if not self.focusWidget() or self.focusWidget() == self:
            if event.key() == Qt.Key_Left:
                self.prev_page()
            elif event.key() == Qt.Key_Right:
                self.next_page()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
            
    def wheelEvent(self, event):
        """滚轮事件处理"""
        if event.modifiers() == Qt.ControlModifier:
            # CTRL+滚轮缩放图片
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # 普通滚轮翻页
            if event.angleDelta().y() > 0:
                self.prev_page()
            else:
                self.next_page()
            
    def prev_page(self):
        """上一页"""
        if self.manga_manager and hasattr(self.manga_manager, 'current_manga') and self.manga_manager.current_manga:
            current_page = config.current_page.value
            step = 2 if self.display_mode == DisplayMode.DOUBLE.value else 1
            
            # 处理双页模式下的边界情况
            if self.display_mode == DisplayMode.DOUBLE.value and current_page == 1:
                self.manga_manager.change_page(0)
                return
                
            if self.reading_order != ReadingOrder.RIGHT_TO_LEFT.value:
                if current_page >= step:
                    self.manga_manager.change_page(current_page - step)
            else:
                if current_page < self.manga_manager.current_manga.total_pages - step:
                    self.manga_manager.change_page(current_page + step)

    def next_page(self):
        """下一页"""
        if self.manga_manager and hasattr(self.manga_manager, 'current_manga') and self.manga_manager.current_manga:
            current_page = config.current_page.value
            step = 2 if self.display_mode == DisplayMode.DOUBLE.value else 1
            
            # 处理双页模式下的边界情况
            if self.display_mode == DisplayMode.DOUBLE.value and current_page == self.manga_manager.current_manga.total_pages - 2:
                self.manga_manager.change_page(self.manga_manager.current_manga.total_pages - 1)
                return
                
            if self.reading_order != ReadingOrder.RIGHT_TO_LEFT.value:
                if current_page < self.manga_manager.current_manga.total_pages - step:
                    self.manga_manager.change_page(current_page + step)
            else:
                if current_page >= step:
                    self.manga_manager.change_page(current_page - step)
                    
    def on_resize(self, event):
        super().resizeEvent(event)
        self.update_display()

    def convert_image_to_qimage(self, image):
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
            return qim
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

    def scale_image(self, image):
        """缩放OpenCV图像到合适大小"""
        if image is None or len(image.shape) < 2:
            print("无效的图像输入")
            return None
            
        # 获取容器尺寸作为缩放基准
        container_size = self.scroll_area.size()
        if container_size.width() <= 0 or container_size.height() <= 0:
            print(f"无效的容器尺寸: {container_size.width()}x{container_size.height()}")
            return None
            
        # 计算保持宽高比的缩放尺寸
        h, w = image.shape[:2]
        
        # 计算两种缩放比例下的目标尺寸
        width_ratio = container_size.width() / w
        height_ratio = container_size.height() / h
        
        # 选择较小的缩放比例，确保图像完整显示在容器内
        if width_ratio * h <= container_size.height():
            target_width = container_size.width()
            target_height = int(h * width_ratio)
        else:
            target_height = container_size.height()
            target_width = int(w * height_ratio)
        
        # 使用LANCZOS4插值进行高质量缩放
        scaled_image = cv2.resize(image, (target_width, target_height), 
                         interpolation=cv2.INTER_AREA)
        return scaled_image

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
        """合并两张图片为一张"""
        try:

            # 检查图片是否存在且尺寸匹配
            if image1 is None or image2 is None or len(image1.shape) < 2 or len(image2.shape) < 2:
                return None
            

            # 根据阅读顺序决定合并方向
            if self.reading_order == ReadingOrder.RIGHT_TO_LEFT.value:
                left_image, right_image = image2, image1
            else:
                left_image, right_image = image1, image2
                
            # 检查高度是否一致，如果不一致则调整高度
            if left_image.shape[0] != right_image.shape[0]:
                # 调整第二张图片的高度以匹配第一张
                right_image = cv2.resize(right_image, (right_image.shape[1], left_image.shape[0]))
                
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
            
        current_page = config.current_page.value
        if current_page < 0 or current_page >= self.current_manga.total_pages:
            self.image_area.setText("页码超出范围")
            return
            
        # 获取当前页图片
        current_image = self.get_page_image(current_page)
        if current_image is None or current_image.size == 0:
            self.image_area.setText("无法获取图像")
            return
            
        # 从配置获取最新设置
        self.display_mode = config.display_mode.value
        self.reading_order = config.reading_order.value
        
        # 判断并处理双页合并
        display_image = current_image
        if self.display_mode != DisplayMode.SINGLE.value:
            next_page_index = current_page + 1
            if next_page_index < self.current_manga.total_pages:
                next_image = self.get_page_image(next_page_index)
                if next_image is not None and next_image.size > 0 and self.should_combine_pages(current_image, next_image):
                    combined = self.combine_images(current_image, next_image)
                    if combined is not None and combined.size > 0:
                        display_image = combined
        
        qimage = self.convert_image_to_qimage(display_image)
        if qimage and not qimage.isNull():
            self.original_image_size = qimage.size()  # 记录原始尺寸
            self.image_area.setPixmap(qimage)
            # 计算初始尺寸(保持宽高比)
            container_height = self.scroll_area.height()
            self.current_scale = (container_height / qimage.height())
            scaled_width = int(qimage.width() * (container_height / qimage.height()))
            self.image_area.setFixedSize(scaled_width, container_height)
        else:
            self.image_area.setText("无法加载图像")
            
    def toggle_reading_order(self):
        """切换阅读顺序（从左到右/从右到左）并返回当前状态"""
        self.reading_order = ReadingOrder.LEFT_TO_RIGHT if self.reading_order == ReadingOrder.RIGHT_TO_LEFT.value else ReadingOrder.RIGHT_TO_LEFT.value
        return self.reading_order
        
    def mousePressEvent(self, event):
        """鼠标按下事件处理"""
        if event.modifiers() == Qt.ControlModifier and event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)  # 改变鼠标指针样式为抓取状态
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件处理"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.last_mouse_pos = None
            self.setCursor(Qt.ArrowCursor)  # 恢复鼠标指针样式
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件处理"""
        # 处理拖动逻辑
        if self.is_dragging and self.last_mouse_pos:
            delta = event.pos() - self.last_mouse_pos
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x()
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y()
            )
            self.last_mouse_pos = event.pos()
            return

        # 原有的控制面板显示逻辑
        window_height = self.height()
        mouse_y = event.pos().y()
        bottom_area_height = 100
        
        if mouse_y > window_height - bottom_area_height:
            if not self.control_panel_visible:
                self.control_panel.show()
                self.control_panel_visible = True
                self.control_panel.set_opacity()
        else:
            if self.control_panel_visible:
                self.control_panel.hide()
                self.control_panel_visible = False

    def leaveEvent(self, event):
        """鼠标离开事件处理"""
        if self.control_panel_visible:
            self.control_panel.hide()
            self.control_panel_visible = False

    def zoom_in(self):
        """放大图片"""
        if self.current_scale < self.max_scale:
            self.current_scale = min(self.current_scale * 1.1, self.max_scale)
            self.apply_zoom()

    def zoom_out(self):
        """缩小图片"""
        if self.current_scale > 0.1:  # 最小缩放比例为10%
            self.current_scale = max(self.current_scale * 0.9, 0.1)
            self.apply_zoom()

    def apply_zoom(self):
        """应用当前缩放比例"""
        if self.original_image_size:
            # 计算缩放后的尺寸
            scaled_width = int(self.original_image_size.width() * self.current_scale)
            scaled_height = int(self.original_image_size.height() * self.current_scale)
            
            # 直接调整ImageLabel的大小，让Qt自动处理图片缩放
            self.image_area.setFixedSize(QSize(scaled_width, scaled_height))
