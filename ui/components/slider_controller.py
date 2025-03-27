from PyQt5.QtCore import Qt
from utils import manga_logger as log

class SliderController:
    """负责页面滑动条控制的组件"""
    
    def __init__(self, parent):
        self.parent = parent
        self.is_updating_slider = False
        self.page_slider = None
    
    def setup_slider(self, slider):
        """初始化滑动条"""
        self.page_slider = slider
        self.page_slider.valueChanged.connect(self.on_slider_value_changed)
    
    def on_slider_value_changed(self):
        """处理滑动条值变化"""
        if self.parent.current_manga and not self.is_updating_slider:
            self.is_updating_slider = True
            self.parent.current_manga.current_page = self.page_slider.value()
            self.parent.image_viewer.show_current_page(
                self.parent.current_manga,
                self.parent.navigation_controller.zoom_slider.value()
            )
            self.parent.navigation_controller.update_navigation_buttons()
            self.parent.title_bar.update_page_info()
            self.is_updating_slider = False
            
    def update_slider(self):
        """更新滑动条状态"""
        if self.parent.current_manga:
            self.is_updating_slider = True
            self.page_slider.setMaximum(self.parent.current_manga.total_pages - 1)
            self.page_slider.setValue(self.parent.current_manga.current_page)
            self.is_updating_slider = False