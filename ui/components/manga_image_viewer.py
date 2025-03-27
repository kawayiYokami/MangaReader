from PyQt5.QtWidgets import QLabel, QScrollArea, QSizePolicy, QHBoxLayout, QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QPoint
from PyQt5.QtGui import QPixmap, QImage, QTransform
from PIL import Image
from utils import manga_logger as log
from ui.components.image_label import ImageLabel
from ui.components.zoom_slider import ZoomSlider
from ui.components.vertical_zoom_slider import VerticalZoomSlider
from PyQt5 import QtCore

class MangaImageViewer(QWidget): # 将 class MangaImageViewer: 修改为 class MangaImageViewer(QWidget):
    """负责漫画图像显示和处理的组件"""

    def __init__(self, parent):
        super().__init__(parent) # 调用父类 QWidget 的 __init__ 方法
        self.parent = parent
        self.image_label = None
        self.zoom_slider = None
        self.vertical_zoom_slider = None
        self.scroll_area = None
        self.next_page_on_right = True
        self.is_single_page_mode = False
        self.auto_hide_controls = True
        self.current_style = parent.current_style
        self._current_zoom_factor = 100.0 # 记录当前的缩放比例
        self.animation = None
        self.target_zoom_factor = 100.0
        self.current_manga = None
        self.current_pixmap = None # 保存当前的 QPixmap
        self._last_displayed_manga = None
        self._last_displayed_page = -1
        self._last_displayed_direction = self.next_page_on_right
        self._last_displayed_single_page_mode = self.is_single_page_mode
        self._last_zoom_factor = 100.0  # 初始化为默认缩放比例

    def setup_ui(self, layout):
        # 创建一个容器来包含滚动区域和垂直缩放滑动条
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(5)  # 设置间距为5像素
        
        # 图片查看区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.image_label = ImageLabel(self.parent)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        container_layout.addWidget(self.scroll_area)
        
        # 确保图像显示控件可以接收键盘焦点
        self.image_label.setFocusPolicy(Qt.StrongFocus)
        # 启用鼠标追踪
        self.image_label.setMouseTracking(True)
        
        # 创建垂直缩放滑动条
        self.vertical_zoom_slider = VerticalZoomSlider()
        
        # 设置滑动条为绝对定位
        self.vertical_zoom_slider.setParent(self.scroll_area)
        self.update_slider_position()
        self.vertical_zoom_slider.raise_()
        
        # 监听滚动区域大小变化
        self.scroll_area.resizeEvent = self.on_scroll_area_resized
        
        # 添加容器到主布局
        layout.addWidget(container)        
        
        return self.vertical_zoom_slider
    
    def show_current_page(self, manga, zoom_factor):
        """显示当前页面，仅加载和设置原始 Pixmap"""
        if not manga:
            return

        target_zoom_factor = zoom_factor # 接收来自滑动条的值

        if target_zoom_factor <= 100:
            # 将滑动条值 1-100 映射到缩放 10%-100%
            target_zoom = 10 + (target_zoom_factor - 1) * (90 / 99)
        else:
            # 将滑动条值 100-200 映射到缩放 100%-500%
            target_zoom = 100 + (target_zoom_factor - 100) * (400 / 100)

        should_reload = (
            manga != self._last_displayed_manga or
            manga.current_page != self._last_displayed_page or
            self.current_pixmap is None or
            self.is_single_page_mode != self._last_displayed_single_page_mode or
            self.next_page_on_right != self._last_displayed_direction
        )

        if should_reload:
            try:
                from core.manga_model import MangaLoader
                current_image = MangaLoader.get_page_image(manga, manga.current_page)
                next_image = None
                if not self.is_single_page_mode and manga.current_page < manga.total_pages - 1:
                    next_image = MangaLoader.get_page_image(manga, manga.current_page + 1)

                combined_image = self._combine_images(current_image, next_image)
                if combined_image:
                    qim = self._pil_image_to_qimage(combined_image)
                    if not qim.isNull():
                        self.current_pixmap = QPixmap.fromImage(qim)
                    else:
                        self.current_pixmap = None
                        self.image_label.setText("图像转换失败")
                        return
                else:
                    self.current_pixmap = None
                    self.image_label.setText("无法加载图像")
                    return
                self.current_manga = manga
                self._last_displayed_manga = manga
                self._last_displayed_page = manga.current_page
                self._last_displayed_direction = self.next_page_on_right
                self._last_displayed_single_page_mode = self.is_single_page_mode
                if self.current_pixmap:
                    self._update_zoomed_pixmap(self.current_pixmap, target_zoom)
                    self._last_zoom_factor = target_zoom
            except Exception as e:
                log.error(f"加载图像时发生错误: {str(e)}")
                self.image_label.setText(f"加载错误: {str(e)}")
                return

        if self.current_pixmap and target_zoom != self._last_zoom_factor:
            self._update_zoomed_pixmap(self.current_pixmap, target_zoom)
            self._last_zoom_factor = target_zoom
        elif self.current_pixmap is not None and self._last_zoom_factor == 100.0 and target_zoom != 100.0: # 首次加载时
            self._update_zoomed_pixmap(self.current_pixmap, target_zoom)
            self._last_zoom_factor = target_zoom

    def _combine_images(self, img1, img2):
        # ... (合并图像的逻辑保持不变) ...
        if img1.mode != 'RGB':
            img1 = img1.convert('RGB')
        if img2 and img2.mode != 'RGB':
            img2 = img2.convert('RGB')

        if img2 and not self.is_single_page_mode:
            total_width = img1.width + (img2.width if img2 else 0)
            max_height = max(img1.height, img2.height if img2 else 0)
            combined_image = Image.new('RGB', (total_width, max_height))
            if self.next_page_on_right:
                combined_image.paste(img1, (0, 0))
                combined_image.paste(img2, (img1.width, 0))
            else:
                combined_image.paste(img2, (0, 0))
                combined_image.paste(img1, (img2.width, 0))
            return combined_image
        else:
            return img1

    def _pil_image_to_qimage(self, image):
        # ... (PIL Image 转 QImage 的逻辑保持不变) ...
        if image:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            img_data = image.tobytes()
            qim = QImage(img_data, image.width, image.height, image.width * 3, QImage.Format_RGB888)
            return qim
        return QImage()

    def _update_zoomed_pixmap(self, pixmap, zoom_factor):
        """根据缩放因子更新显示的 Pixmap"""
        if self.scroll_area and pixmap:
            viewport_size = self.scroll_area.viewport().size()
            scale_w = viewport_size.width() / pixmap.width()
            scale_h = viewport_size.height() / pixmap.height()
            initial_scale = min(scale_w, scale_h)

            scale = initial_scale * zoom_factor / 100.0

            new_width = int(pixmap.width() * scale)
            new_height = int(pixmap.height() * scale)

            scaled_pixmap = pixmap.scaled(new_width, new_height,
                                            Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setFixedSize(new_width, new_height)

    def _animate_zoom(self, zoom):
        """动画更新函数，根据当前的缩放值更新图像"""
        if self.current_pixmap:
            self._update_zoomed_pixmap(self.current_pixmap, zoom)
        self._current_zoom_factor = zoom # 更新当前的缩放比例

    def toggle_page_direction(self):
        """切换页面显示方向"""
        self.next_page_on_right = not self.next_page_on_right
        # 切换方向后，需要重新显示当前页以应用新的方向
        if self.parent.current_manga:
            self.show_current_page(self.parent.current_manga, self.parent.navigation_controller.zoom_slider.value())

    def toggle_page_mode(self, is_single_page):
        """切换单页/双页显示模式"""
        self.is_single_page_mode = is_single_page
        # 切换单双页模式后，需要重新显示当前页以应用新的模式
        if self.parent.current_manga:
            self.show_current_page(self.parent.current_manga, self.parent.navigation_controller.zoom_slider.value())

    def set_auto_hide(self, auto_hide):
        """设置是否自动隐藏控件"""
        self.auto_hide_controls = auto_hide
        self.vertical_zoom_slider.setAutoHide(auto_hide)

    def on_scroll_area_resized(self, event):
        """处理滚动区域大小变化事件"""
        if hasattr(self, 'vertical_zoom_slider') and self.vertical_zoom_slider:
            self.update_slider_position()

    def update_slider_position(self):
        """更新滑动条位置，使其始终位于滚动区域右侧并垂直居中"""
        if hasattr(self, 'vertical_zoom_slider') and self.vertical_zoom_slider:
            right_margin = 15
            self.vertical_zoom_slider.move(
                self.scroll_area.width() - self.vertical_zoom_slider.width() - right_margin,
                (self.scroll_area.height() - self.vertical_zoom_slider.height()) // 2
            )

    def convert_image_to_pixmap(self, image):
        """将 PIL Image 转换为 QPixmap"""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            img_data = image.tobytes()
            qim = QImage(img_data, image.width, image.height, image.width * 3, QImage.Format_RGB888)
            if qim.isNull():
                return None
            return QPixmap.fromImage(qim)
        except Exception as e:
            log.error(f"转换图像时发生错误: {str(e)}")
            return None