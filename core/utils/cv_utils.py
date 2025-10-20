# file: core/utils/cv_utils.py
"""
计算机视觉工具集
=================

提供基于传统计算机视觉（如OpenCV）的图像处理功能，
例如文本区域检测。
"""

import cv2
import numpy as np

class CVTextDetector:
    """
    使用经典的计算机视觉技术来检测图像中的文本区域。
    """

    @classmethod
    def detect_text_areas(cls, image_path: str, show_result: bool = True) -> list[tuple[int, int, int, int]]:
        """
        检测图像中的文本区域。

        这个方法通过一系列的图像滤镜和形态学变换来凸显和连接文本块，
        然后通过查找轮廓来确定它们的边界框。

        Args:
            image_path (str): 输入图像的路径。
            show_result (bool): 是否显示带有检测框的预览窗口。

        Returns:
            list[tuple[int, int, int, int]]: 一个包含所有检测到的文本区域边界框的列表。
                                             每个边界框是一个 (x, y, w, h) 的元组。
        """
        try:
            # 1. 加载图像并转为灰度图
            image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                print(f"错误: 无法读取图片: {image_path}")
                return []

            # 2. 通过高斯模糊和图像相减来增强边缘
            blurred = cv2.GaussianBlur(image, (9, 9), 0)
            subtracted = cv2.subtract(image, blurred)

            # 3. 使用Otsu自适应阈值进行二值化
            _, binary = cv2.threshold(
                subtracted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            # 4. 定义一个形态学操作的核
            kernel = np.ones((9, 9), np.uint8)

            # 5. 使用闭运算填充文本内部的空洞
            closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

            # 6. 使用膨胀操作连接邻近的字符和词语
            dilated = cv2.dilate(closed, kernel, iterations=1)

            # 7. 查找处理后图像中的所有轮廓
            contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            text_areas = []
            output_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

            # 8. 遍历所有轮廓
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # 9. 过滤掉太小或太扁平的区域，以减少噪声
                if w > 5 and h > 13:
                    text_areas.append((x, y, w, h))
                    # 在输出图像上绘制绿色的矩形框
                    cv2.rectangle(output_image, (x, y), (x + w, y + h), (0, 255, 0), 2)

            print(f"在 '{image_path}' 中检测到 {len(text_areas)} 个潜在文本区域。")

            # 10. 如果需要，显示结果图片
            if show_result:
                cv2.imshow("Detected Text Areas", output_image)
                print("按任意键关闭预览窗口...")
                cv2.waitKey(0)
                cv2.destroyAllWindows()

            return text_areas

        except Exception as e:
            print(f"处理图片时发生错误: {e}")
            return []


if __name__ == "__main__":
    # 使用我们项目中的漫画图片进行测试
    test_image_path = "storage/manga/02.webp"
    print("--- 开始测试文本检测算法 ---")
    print(f"测试图片: {test_image_path}")
    
    detected_boxes = CVTextDetector.detect_text_areas(test_image_path, show_result=True)
    
    if detected_boxes:
        print("\n检测到的边界框 (x, y, w, h):")
        for i, box in enumerate(detected_boxes):
            print(f"  - 框 {i+1}: {box}")
    
    print("\n--- 测试结束 ---")