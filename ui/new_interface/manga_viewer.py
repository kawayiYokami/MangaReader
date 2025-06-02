# Qt核心模块
from PySide6.QtCore import Qt, QSize, QThread, Signal, Slot # 添加 Slot 导入
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QGridLayout,
)
from PySide6.QtGui import QPixmap, QImage

# 第三方UI组件
from qfluentwidgets import (
    CardWidget,
    PushButton,
    InfoBar,
    InfoBarPosition,
    BodyLabel,
    ImageLabel,
    SmoothScrollArea,
)

# 项目内部模块
from ui.new_interface.control_panel import ControlPanel
from core.manga_manager import MangaManager
from core.manga_model import MangaLoader
from core.config import config, DisplayMode, ReadingOrder
from core.batch_translation_worker import BatchTranslationWorker, TranslationTaskItem

# 标准库和第三方库
import time
import cv2
import numpy as np # 导入 numpy
import os # 导入 os 模块


class MangaViewer(CardWidget):
    """
    漫画查看器组件，继承自CardWidget

    主要功能：
    - 显示单页或双页漫画图片
    - 支持图片缩放以适应窗口大小
    - 处理键盘和滚轮翻页事件
    - 根据阅读方向自动调整页面顺序
    - 提供悬浮控制面板进行交互
    - 集成漫画翻译功能

    属性：
        display_mode: 显示模式（'single'或'double'）
        reading_order: 阅读顺序（'right_to_left'或'left_to_right'）
        auto_page: 是否自动翻页
        manga_manager: 漫画管理器实例
        manga_loader: 漫画加载器实例
        translation_enabled: 翻译功能是否启用
        translated_image_cache: 翻译后的图片缓存
        batch_translation_worker: 批量翻译工作器实例
        translation_thread: 翻译线程实例
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
        self.manga_manager = manga_manager or MangaManager(self)
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

        # 翻译相关属性
        self.translation_enabled = False
        self.translated_image_cache = {} # 使用字典存储翻译后的图片数据 {页码: 图片数据}
        self.batch_translation_worker = None
        self.translation_thread = None

        # 初始化控制面板显示状态
        self.control_panel_visible = False
        self.actual_pages_displayed = 1 # 记录当前实际显示的页面数量

        # 初始化拖动相关的属性
        self.is_dragging = False
        self.last_mouse_pos = None

        self.setup_ui()  # 初始化UI

        # 重写窗口大小变化事件处理
        self.resizeEvent = self.on_resize

        # 启用键盘和滚轮事件
        self.setFocusPolicy(Qt.StrongFocus)

        # 初始化时检查是否有当前漫画
        if hasattr(self.manga_manager, 'current_manga') and self.manga_manager.current_manga:
            self.on_current_manga_changed(self.manga_manager.current_manga)


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

        self.layout = QGridLayout(self)  # <-- 将主布局改为 QGridLayout
        # 移除主布局的内边距和单元格间距，让内容充满窗口
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)  # 移除单元格之间的间距

        # 设置鼠标追踪，以便接收鼠标移动事件
        self.setMouseTracking(True)

        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setStyleSheet("border: none; background: transparent;")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )  # 确保滚动区域可以伸展
        self.scroll_area.setAttribute(
            Qt.WA_TransparentForMouseEvents
        )  # 允许鼠标事件穿透

        # 创建滚动区域内部的容器和图像标签
        scroll_container = QWidget()
        scroll_container.setLayout(QVBoxLayout())
        scroll_container.layout().setContentsMargins(0, 0, 0, 0)
        scroll_container.layout().setSpacing(0)  # 移除容器内部布局的间距

        self.image_area = ImageLabel("请选择一本漫画开始阅读")
        self.image_area.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )  # 图像标签可以伸展
        self.image_area.setScaledContents(False)
        self.image_area.setAlignment(
            Qt.AlignCenter
        )  # 设置图像在标签内部居中 (当图片小于标签时)

        # 将图像标签添加到容器的布局中，并确保在 QVBoxLayout 中水平居中
        scroll_container.layout().addWidget(self.image_area, 0, Qt.AlignCenter)

        # 将容器设置为滚动区域的 widget
        self.scroll_area.setWidget(scroll_container)

        self.control_panel = ControlPanel(self, self.manga_manager)
        # 控制面板的尺寸策略：水平伸展以适应窗口宽度，垂直固定或首选，不应伸展并挤压背景
        self.control_panel.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )  # <-- 垂直策略 Fixed 或 Preferred

        # 将 scroll_area (作为背景) 添加到网格布局的 (0, 0) 单元格，跨 1 行 1 列
        # 它应该伸展以填充整个单元格 (整个窗口)
        self.layout.addWidget(
            self.scroll_area, 0, 0, 1, 1
        )  # row 0, col 0, row span 1, col span 1

        # 将 control_panel (作为前景覆盖层) 也添加到网格布局的 **同一个** (0, 0) 单元格
        # 使用对齐标志将其放在单元格的底部中央
        self.layout.addWidget(
            self.control_panel, 0, 0, 1, 1, Qt.AlignBottom | Qt.AlignHCenter
        )
        # 连接 ControlPanel 的翻译开关信号
        self.control_panel.translate_switch.checkedChanged.connect(self.set_translation_enabled)


        # 让 (0, 0) 单元格所在的行和列可以伸展，这样 scroll_area 会填充整个窗口
        self.layout.setRowStretch(0, 1)  # 第 0 行可伸展
        self.layout.setColumnStretch(0, 1)  # 第 0 列可伸展

        self.control_panel.raise_()  # <-- 添加这一行

        # 初始化时隐藏控制面板
        self.control_panel.hide()


    def on_current_manga_changed(self, manga):
        """
        当前漫画变更时的处理函数
        :param manga: 当前选中的漫画对象
        """
        if manga:
            self.current_manga = manga
            # 漫画变更时清空翻译缓存
            self.translated_image_cache.clear()
            # 如果翻译功能开启，重新启动翻译工作器
            if self.translation_enabled:
                 self.set_translation_enabled(True) # 重新启动翻译
            else:
                 self.update_display()  # 更新显示原始图片
        else:
            self.image_area.setText("请选择一本漫画开始阅读")
            # 清空缓存并停止翻译工作器
            self.translated_image_cache.clear()
            if self.batch_translation_worker and self.translation_thread and self.translation_thread.isRunning():
                 self.batch_translation_worker.cancel()
                 self.translation_thread.wait()


    def on_page_changed(self, page):
        """
        页码变更时的处理函数
        :param page: 当前页码
        """
        if hasattr(self, "current_manga"):
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
        if (
            self.manga_manager
            and hasattr(self.manga_manager, "current_manga")
            and self.manga_manager.current_manga
        ):
            current_page = config.current_page.value
            step = self.actual_pages_displayed # 根据实际显示的页面数量来决定步长

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
        if (
            self.manga_manager
            and hasattr(self.manga_manager, "current_manga")
            and self.manga_manager.current_manga
        ):
            current_page = config.current_page.value
            step = self.actual_pages_displayed # 根据实际显示的页面数量来决定步长

            # 处理双页模式下的边界情况
            if (
                self.display_mode == DisplayMode.DOUBLE.value
                and current_page == self.manga_manager.current_manga.total_pages - 2
            ):
                self.manga_manager.change_page(
                    self.manga_manager.current_manga.total_pages - 1
                )
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
            qim = QImage(
                image.data, width, height, bytes_per_line, QImage.Format_RGB888
            )
            return qim
        return QImage()

    def get_page_image(self, current_page):
        """
        获取指定页面的图像
        :param current_page: 当前页码
        :return: OpenCV图像对象(numpy数组)
        """
        if not hasattr(self, "current_manga") or not self.current_manga:
            return None
        if current_page < 0 or current_page >= self.current_manga.total_pages:
            return None

        # 记录开始时间
        start_time = time.time()

        # 获取原始图片
        image = self.manga_loader.get_page_image(self.current_manga, current_page)
        load_time = time.time()

        return image

    def scale_image(self, image, container_size: QSize):
        """缩放OpenCV图像到合适大小"""
        if image is None:
            print("scale_image: 无效的图像输入 (is None)")
            return None
        if not hasattr(image, 'shape') or not isinstance(image, np.ndarray) or len(image.shape) < 2:
            print(f"scale_image: 无效的图像输入 (type: {type(image)}, no shape or invalid shape)")
            return None

        if container_size.width() <= 0 or container_size.height() <= 0:
            print(f"无效的容器尺寸: {container_size.width()}x{container_size.height()}")
            return None # Return None if container size is invalid

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
        # 确保目标尺寸大于0
        if target_width <= 0 or target_height <= 0:
             print(f"计算出的目标尺寸无效: {target_width}x{target_height}")
             return None # Return None if target dimensions are invalid

        # 使用LANCZOS4插值进行高质量缩放
        scaled_image = cv2.resize(
            image, (target_width, target_height), interpolation=cv2.INTER_AREA
        )
        return scaled_image

    def should_combine_pages(self, current_image, next_image, container_size: QSize) -> bool:
        if (
            current_image is None
            or next_image is None
            or len(current_image.shape) < 2
            or len(next_image.shape) < 2
        ):
            return False

        height_diff = abs(current_image.shape[0] - next_image.shape[0])
        if height_diff > max(current_image.shape[0], next_image.shape[0]) * 0.1:
            return False

        if container_size.width() <= 0 or container_size.height() <= 0:
            return False

        combined_width = current_image.shape[1] + next_image.shape[1]
        return (
            combined_width * container_size.height()
            <= container_size.width() * current_image.shape[0]
        )

    def combine_images(self, image1, image2):
        """合并两张图片为一张"""
        try:

            # 检查图片是否存在且尺寸匹配
            if (
                image1 is None
                or image2 is None
                or len(image1.shape) < 2
                or len(image2.shape) < 2
            ):
                return None

            # 根据阅读顺序决定合并方向
            if self.reading_order == ReadingOrder.RIGHT_TO_LEFT.value:
                left_image, right_image = image2, image1
            else:
                left_image, right_image = image1, image2

            # 检查高度是否一致，如果不一致则调整高度
            if left_image.shape[0] != right_image.shape[0]:
                # 调整第二张图片的高度以匹配第一张
                right_image = cv2.resize(
                    right_image, (right_image.shape[1], left_image.shape[0])
                )

            # 使用OpenCV进行图像拼接
            combined = cv2.hconcat([left_image, right_image])
            return combined
        except Exception as e:
            print(f"合并图像时发生错误: {str(e)}")
            return None

    def update_display(self):
        """
        更新显示的图像
        处理单页/双页模式切换、翻译显示和图像缩放
        """
        if not hasattr(self, "current_manga") or not self.current_manga:
            self.image_area.setText("请选择一本漫画开始阅读")
            self.image_area.setPixmap(QPixmap()) # Clear pixmap
            return

        current_page = config.current_page.value
        if current_page < 0 or current_page >= self.current_manga.total_pages:
            self.image_area.setText("页码超出范围")
            self.image_area.setPixmap(QPixmap()) # Clear pixmap
            return

        # 从配置获取最新设置
        self.display_mode = config.display_mode.value
        self.reading_order = config.reading_order.value
        container_size = self.scroll_area.size()

        # This will hold the raw (unscaled) image data to be displayed
        final_image_data_unscaled = None
        self.actual_pages_displayed = 1 # 默认单页

        if self.translation_enabled and current_page in self.translated_image_cache:
            print(f"翻译开启且缓存命中，准备显示页码 {current_page} 的翻译图片。")
            current_image_unscaled = self.translated_image_cache.get(current_page) # Can be None

            if self.display_mode != DisplayMode.SINGLE.value:
                next_page_index = current_page + 1
                next_image_unscaled = None
                if next_page_index < self.current_manga.total_pages and next_page_index in self.translated_image_cache:
                    next_image_unscaled = self.translated_image_cache.get(next_page_index) # Can be None

                if current_image_unscaled is not None and next_image_unscaled is not None and \
                   self.should_combine_pages(current_image_unscaled, next_image_unscaled, container_size):
                    combined_data = self.combine_images(current_image_unscaled, next_image_unscaled)
                    # combine_images handles None inputs and can return None
                    if combined_data is not None and combined_data.size > 0:
                        final_image_data_unscaled = combined_data
                        self.actual_pages_displayed = 2
                    else: # Combine failed or one of the images was None
                        final_image_data_unscaled = current_image_unscaled # Fallback to current
                else: # Not combining (or one image is None)
                    final_image_data_unscaled = current_image_unscaled
            else: # Single page mode
                final_image_data_unscaled = current_image_unscaled
        else:
            # 翻译关闭或缓存未命中，显示原始图片
            print(f"翻译关闭或缓存未命中，准备显示页码 {current_page} 的原始图片。")
            current_image_unscaled = self.get_page_image(current_page) # Can be None

            if current_image_unscaled is None: # Explicit check after get_page_image
                self.image_area.setText("无法获取原始图像")
                self.image_area.setPixmap(QPixmap())
                return
            if not hasattr(current_image_unscaled, 'size') or current_image_unscaled.size == 0:
                self.image_area.setText("原始图像数据无效或为空")
                self.image_area.setPixmap(QPixmap())
                return

            if self.display_mode != DisplayMode.SINGLE.value:
                next_page_index = current_page + 1
                next_image_unscaled = None
                if next_page_index < self.current_manga.total_pages:
                    next_image_unscaled = self.get_page_image(next_page_index) # Can be None

                # current_image_unscaled is guaranteed not None here
                if next_image_unscaled is not None and \
                   self.should_combine_pages(current_image_unscaled, next_image_unscaled, container_size):
                    combined_data = self.combine_images(current_image_unscaled, next_image_unscaled)
                    if combined_data is not None and combined_data.size > 0:
                        final_image_data_unscaled = combined_data
                        self.actual_pages_displayed = 2
                    else: # Combine failed
                        final_image_data_unscaled = current_image_unscaled
                else: # Not combining or next_image_unscaled is None
                    final_image_data_unscaled = current_image_unscaled
            else: # Single page mode
                final_image_data_unscaled = current_image_unscaled

        # Now, scale final_image_data_unscaled if it's not None
        if final_image_data_unscaled is None:
            self.image_area.setText("无法加载最终图像数据")
            self.image_area.setPixmap(QPixmap())
            return

        # Check size again, in case combine_images returned an empty array or similar
        if not hasattr(final_image_data_unscaled, 'size') or final_image_data_unscaled.size == 0:
            self.image_area.setText("最终图像数据为空或无效")
            self.image_area.setPixmap(QPixmap())
            return

        scaled_display_image = self.scale_image(final_image_data_unscaled, container_size)

        if scaled_display_image is None: # scale_image might return None
            self.image_area.setText("图像缩放失败")
            self.image_area.setPixmap(QPixmap())
            return

        q_image = self.convert_image_to_qimage(scaled_display_image)
        if q_image.isNull():
            self.image_area.setText("图像转换失败")
            self.image_area.setPixmap(QPixmap())
        else:
            self.image_area.setPixmap(QPixmap.fromImage(q_image))


    def toggle_reading_order(self):
        """切换阅读顺序"""
        current_order = config.reading_order.value
        new_order = (
            ReadingOrder.LEFT_TO_RIGHT.value
            if current_order == ReadingOrder.RIGHT_TO_LEFT.value
            else ReadingOrder.RIGHT_TO_LEFT.value
        )
        config.reading_order.set_value(new_order)

    def mousePressEvent(self, event):
        """鼠标按下事件处理，用于图片拖动"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件处理"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件处理，用于显示/隐藏控制面板和图片拖动"""
        # 控制面板显示/隐藏逻辑
        # 检查鼠标是否在窗口底部区域 (例如，底部50像素)
        if event.pos().y() >= self.height() - 50:
            if not self.control_panel.isVisible() and self.control_panel.isEnabled(): # 仅在启用时显示
                self.control_panel.show()
                self.control_panel_visible = True # 更新状态
        else:
            if self.control_panel.isVisible():
                self.control_panel.hide()
                self.control_panel_visible = False # 更新状态

        # 图片拖动逻辑
        if self.is_dragging and self.last_mouse_pos:
            delta = event.pos() - self.last_mouse_pos
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            self.last_mouse_pos = event.pos()

        super().mouseMoveEvent(event)


    def leaveEvent(self, event):
        """鼠标离开窗口事件处理"""
        if self.control_panel.isVisible():
            self.control_panel.hide()
            self.control_panel_visible = False # 更新状态
        super().leaveEvent(event)


    def zoom_in(self):
        """放大图片"""
        self.current_scale = min(self.max_scale, self.current_scale + 0.1)
        self.apply_zoom()

    def zoom_out(self):
        """缩小图片"""
        self.current_scale = max(0.1, self.current_scale - 0.1) # 最小缩放比例为0.1
        self.apply_zoom()

    def apply_zoom(self):
        """应用缩放并更新显示"""
        # 注意：这里的缩放逻辑可能需要更复杂的实现，
        # 例如，基于原始图片尺寸进行缩放，而不是简单地缩放当前显示的QPixmap
        # 目前的实现是概念性的，实际效果可能需要调整
        if self.original_image_size:
            # 重新计算并设置ImageLabel的尺寸或Pixmap
            # 这需要重新调用update_display或一个专门的缩放更新函数
            self.update_display() # 重新调用update_display以应用缩放


    @Slot(bool) # 接收 bool 类型的信号参数
    def set_translation_enabled(self, enabled: bool):
        """
        设置翻译功能的启用状态
        :param enabled: True表示启用翻译，False表示禁用
        """
        self.translation_enabled = enabled
        print(f"翻译功能已 {'启用' if enabled else '禁用'}")

        if enabled:
            if not hasattr(self, "current_manga") or not self.current_manga:
                InfoBar.warning(
                    title="提示",
                    content="请先选择一本漫画再启用翻译。",
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )
                self.control_panel.translate_switch.setChecked(False) # 重置开关状态
                return

            if self.translation_thread and self.translation_thread.isRunning():
                if self.batch_translation_worker:
                    self.batch_translation_worker.cancel()
                self.translation_thread.quit()
                self.translation_thread.wait()

            translation_tasks = []
            current_translator_engine = config.translator_type.value
            source_lang = "auto"
            target_lang = "zh-CN"

            if current_translator_engine == "NLLB":
                source_lang = config.nllb_source_lang.value
                target_lang = config.nllb_target_lang.value

            # 确定 original_archive_path
            # MangaInfo.file_path 存储的是完整路径
            # 检查 self.current_manga.file_path 是否为 .zip 文件
            is_zip_archive = False
            if self.current_manga and hasattr(self.current_manga, 'file_path') and self.current_manga.file_path:
                is_zip_archive = self.current_manga.file_path.lower().endswith(".zip")
            
            original_archive_path_for_task = self.current_manga.file_path if is_zip_archive else None


            for i in range(self.current_manga.total_pages):
                image_data = self.get_page_image(i)
                if image_data is not None:
                    task_item = TranslationTaskItem(
                        task_id=f"page_{i}",
                        image_data=image_data,
                        page_index=i,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        original_archive_path=original_archive_path_for_task
                    )
                    translation_tasks.append(task_item)
                else:
                    print(f"警告: 无法获取第 {i} 页的图像数据，跳过此页的翻译任务。")

            if not translation_tasks:
                InfoBar.warning(
                    title="提示",
                    content="当前漫画没有可供翻译的页面。",
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )
                self.control_panel.translate_switch.setChecked(False)
                return

            self.batch_translation_worker = BatchTranslationWorker(
                tasks=translation_tasks,
                save_to_disk=False,
                translator_engine=current_translator_engine
            )
            self.translation_thread = QThread()
            self.batch_translation_worker.moveToThread(self.translation_thread)

            self.batch_translation_worker.single_page_translated.connect(self.on_single_page_translated)
            self.batch_translation_worker.overall_progress.connect(self.on_batch_translation_progress)
            self.batch_translation_worker.all_tasks_finished.connect(self.on_all_tasks_finished)
            self.batch_translation_worker.error_occurred.connect(self.on_translation_error)
            self.translation_thread.started.connect(self.batch_translation_worker.run)

            self.translation_thread.start()
            InfoBar.info(
                title="翻译已启动",
                content="正在后台翻译当前漫画...",
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )
        else:
            if self.translation_thread and self.translation_thread.isRunning():
                if self.batch_translation_worker:
                    self.batch_translation_worker.cancel()
                self.translation_thread.quit()
                self.translation_thread.wait()
            self.batch_translation_worker = None
            self.translation_thread = None
            self.translated_image_cache.clear()
            self.update_display()
            InfoBar.info(
                title="翻译已关闭",
                content="已切换回显示原始图片。",
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )


    @Slot(int, object) # page_index, translated_image_data
    def on_single_page_translated(self, page_index: int, translated_image_data):
        """单个页面翻译完成的回调"""
        if translated_image_data is not None:
            self.translated_image_cache[page_index] = translated_image_data
            print(f"页面 {page_index} 翻译完成并已缓存。")
            if config.current_page.value == page_index or \
               (self.display_mode != DisplayMode.SINGLE.value and config.current_page.value + 1 == page_index):
                self.update_display()
        else:
            print(f"页面 {page_index} 翻译返回空数据。")


    @Slot(int, str)
    def on_batch_translation_progress(self, percent: int, message: str):
        """批量翻译进度更新回调"""
        pass

    @Slot(str)
    def on_all_tasks_finished(self, result_message: str):
        """所有翻译任务完成的回调"""
        InfoBar.success(
            title="翻译完成",
            content=result_message,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
        print("所有翻译任务已完成。")
        if self.translation_thread:
            self.translation_thread.quit()


    @Slot(str)
    def on_translation_error(self, error_message: str):
        """翻译错误回调"""
        error_content = str(error_message)
        InfoBar.error(
            title="翻译错误",
            content=error_content,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )
        print(f"翻译过程中发生错误: {error_content}")
