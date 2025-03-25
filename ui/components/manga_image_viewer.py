from PyQt5.QtWidgets import QLabel, QScrollArea, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from utils import manga_logger as log
from ui.components.image_label import ImageLabel
from ui.components.zoom_slider import ZoomSlider

class MangaImageViewer:
    """负责漫画图像显示和处理的组件"""
    
    def __init__(self, parent):
        self.parent = parent
        self.image_label = None
        self.zoom_slider = None
        self.scroll_area = None
        self.next_page_on_right = True
        self.is_single_page_mode = False
    
    def setup_ui(self, layout):
        # 图片查看区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.image_label = ImageLabel(self.parent)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)
        
        # 确保图像显示控件可以接收键盘焦点
        self.image_label.setFocusPolicy(Qt.StrongFocus)
        # 启用鼠标追踪
        self.image_label.setMouseTracking(True)
        
        # 创建缩放滑块
        self.zoom_slider = ZoomSlider()
        
        return self.zoom_slider
    
    def show_current_page(self, manga, zoom_factor):
        """显示当前页面"""
        if not manga:
            return
        
        try:
            # 加载当前页面
            from core.manga_model import MangaLoader
            current_image = MangaLoader.get_page_image(manga, manga.current_page)
            if not current_image:
                self.image_label.setText("无法加载图像")
                return

            # 获取下一页图像（如果是双页模式且存在下一页）
            next_image = None
            if not self.is_single_page_mode and manga.current_page < manga.total_pages - 1:
                next_image = MangaLoader.get_page_image(manga, manga.current_page + 1)

            try:
                # 处理当前页面
                if current_image.mode != 'RGB':
                    current_image = current_image.convert('RGB')
                
                # 如果是双页模式且有下一页，处理下一页图像
                if next_image and not self.is_single_page_mode:
                    if next_image.mode != 'RGB':
                        next_image = next_image.convert('RGB')
                    
                    # 创建合并图像
                    total_width = current_image.width + (next_image.width if next_image else 0)
                    max_height = max(current_image.height, next_image.height if next_image else 0)
                    
                    # 创建新的RGB图像
                    combined_image = Image.new('RGB', (total_width, max_height))
                    
                    # 根据显示方向粘贴图像
                    if self.next_page_on_right:
                        combined_image.paste(current_image, (0, 0))
                        combined_image.paste(next_image, (current_image.width, 0))
                    else:
                        combined_image.paste(next_image, (0, 0))
                        combined_image.paste(current_image, (next_image.width, 0))
                else:
                    # 单页模式，直接使用当前页面
                    combined_image = current_image
                
                # 转换为QImage
                img_data = combined_image.tobytes()
                qim = QImage(img_data, combined_image.width, combined_image.height, 
                           combined_image.width * 3, QImage.Format_RGB888)
                
                if qim.isNull():
                    log.error("QImage创建失败")
                    self.image_label.setText("图像转换失败")
                    return
                
                # 创建QPixmap并缩放
                pixmap = QPixmap.fromImage(qim)
                if pixmap.isNull():
                    log.error("QPixmap创建失败")
                    self.image_label.setText("图像转换失败：无法创建QPixmap")
                    return
                
                # 获取 QScrollArea
                if self.scroll_area:
                    viewport_size = self.scroll_area.viewport().size()
                    scale_w = viewport_size.width() / pixmap.width()
                    scale_h = viewport_size.height() / pixmap.height()
                    scale = min(scale_w, scale_h)
                    
                    # 应用用户缩放比例
                    scale *= zoom_factor / 100.0
                    
                    new_width = int(pixmap.width() * scale)
                    new_height = int(pixmap.height() * scale)
                    
                    scaled_pixmap = pixmap.scaled(new_width, new_height, 
                                                Qt.KeepAspectRatio, 
                                                Qt.SmoothTransformation)
                    
                    self.image_label.setPixmap(scaled_pixmap)
                    self.image_label.setFixedSize(new_width, new_height)
                else:
                    self.image_label.setPixmap(pixmap)
                
            except Exception as e:
                log.error(f"处理图像时发生错误: {str(e)}")
                self.image_label.setText(f"图像处理错误: {str(e)}")
                
        except Exception as e:
            log.error(f"显示页面时发生错误: {str(e)}")
            self.image_label.setText(f"显示错误: {str(e)}")
    
    def toggle_page_direction(self):
        """切换页面显示方向"""
        self.next_page_on_right = not self.next_page_on_right
    
    def toggle_page_mode(self, is_single_page):
        """切换单页/双页显示模式"""
        self.is_single_page_mode = is_single_page
    
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