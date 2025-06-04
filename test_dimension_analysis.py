#!/usr/bin/env python3
"""
页面尺寸分析功能测试脚本

用于测试和验证漫画页面尺寸分析功能的正确性。
"""

import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.manga_model import MangaLoader
from core.config import config
from utils import manga_logger as log

def test_dimension_analysis():
    """测试页面尺寸分析功能"""
    
    # 设置日志级别为DEBUG以查看详细信息
    log.setLevel(logging.DEBUG)
    
    print("=" * 60)
    print("页面尺寸分析功能测试")
    print("=" * 60)
    
    # 显示当前配置
    print(f"启用尺寸分析: {config.enable_dimension_analysis.value}")
    print(f"方差阈值: {config.dimension_variance_threshold.value}")
    print(f"过滤非漫画: {config.filter_non_manga.value}")
    print()
    
    # 获取测试目录
    test_dir = input("请输入要测试的漫画目录路径: ").strip()
    if not test_dir or not os.path.exists(test_dir):
        print("目录不存在或无效！")
        return
    
    print(f"开始扫描目录: {test_dir}")
    print("-" * 40)
    
    # 查找漫画文件
    manga_files = MangaLoader.find_manga_files(test_dir)
    print(f"找到 {len(manga_files)} 个潜在漫画文件")
    print()
    
    # 分析每个文件
    results = []
    for i, file_path in enumerate(manga_files[:10]):  # 限制测试前10个文件
        print(f"[{i+1}/{min(10, len(manga_files))}] 分析: {os.path.basename(file_path)}")
        
        try:
            # 加载漫画并进行尺寸分析
            manga = MangaLoader.load_manga(file_path, analyze_dimensions=True)
            
            if manga:
                result = {
                    'file_path': file_path,
                    'title': manga.title,
                    'total_pages': manga.total_pages,
                    'is_valid': manga.is_valid,
                    'page_dimensions': manga.page_dimensions,
                    'dimension_variance': manga.dimension_variance,
                    'is_likely_manga': manga.is_likely_manga
                }
                results.append(result)
                
                print(f"  总页数: {manga.total_pages}")
                print(f"  采样页数: {len(manga.page_dimensions)}")
                if manga.dimension_variance is not None:
                    print(f"  方差分数: {manga.dimension_variance:.4f}")
                    print(f"  可能是漫画: {manga.is_likely_manga}")
                    
                    # 显示尺寸统计
                    if manga.page_dimensions:
                        widths = [d[0] for d in manga.page_dimensions]
                        heights = [d[1] for d in manga.page_dimensions]
                        print(f"  宽度范围: {min(widths)} - {max(widths)}")
                        print(f"  高度范围: {min(heights)} - {max(heights)}")
                else:
                    print("  未进行尺寸分析")
            else:
                print("  加载失败")
                
        except Exception as e:
            print(f"  错误: {e}")
        
        print()
    
    # 显示汇总结果
    print("=" * 60)
    print("分析结果汇总")
    print("=" * 60)
    
    if results:
        valid_results = [r for r in results if r['dimension_variance'] is not None]
        
        if valid_results:
            variances = [r['dimension_variance'] for r in valid_results]
            likely_manga = [r for r in valid_results if r['is_likely_manga']]
            
            print(f"成功分析文件数: {len(valid_results)}")
            print(f"方差分数范围: {min(variances):.4f} - {max(variances):.4f}")
            print(f"平均方差分数: {sum(variances)/len(variances):.4f}")
            print(f"识别为漫画: {len(likely_manga)}/{len(valid_results)}")
            print()
            
            # 按方差分数排序显示
            sorted_results = sorted(valid_results, key=lambda x: x['dimension_variance'])
            
            print("按方差分数排序 (越小越一致):")
            print("-" * 40)
            for r in sorted_results:
                status = "✓漫画" if r['is_likely_manga'] else "✗非漫画"
                print(f"{r['dimension_variance']:.4f} - {status} - {os.path.basename(r['file_path'])}")
        else:
            print("没有成功分析的文件")
    else:
        print("没有找到有效的漫画文件")

def test_threshold_sensitivity():
    """测试不同阈值的敏感性"""
    print("\n" + "=" * 60)
    print("阈值敏感性测试")
    print("=" * 60)
    
    # 测试不同的阈值
    test_thresholds = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    
    test_dir = input("请输入要测试的漫画目录路径: ").strip()
    if not test_dir or not os.path.exists(test_dir):
        print("目录不存在或无效！")
        return
    
    manga_files = MangaLoader.find_manga_files(test_dir)[:5]  # 测试前5个文件
    
    print(f"使用 {len(manga_files)} 个文件测试不同阈值")
    print()
    
    for threshold in test_thresholds:
        # 临时设置阈值
        original_threshold = config.dimension_variance_threshold.value
        config.dimension_variance_threshold.value = threshold
        
        manga_count = 0
        total_count = 0
        
        for file_path in manga_files:
            try:
                manga = MangaLoader.load_manga(file_path, analyze_dimensions=True)
                if manga and manga.dimension_variance is not None:
                    total_count += 1
                    if manga.is_likely_manga:
                        manga_count += 1
            except:
                continue
        
        # 恢复原始阈值
        config.dimension_variance_threshold.value = original_threshold
        
        if total_count > 0:
            percentage = (manga_count / total_count) * 100
            print(f"阈值 {threshold:.2f}: {manga_count}/{total_count} ({percentage:.1f}%) 识别为漫画")
        else:
            print(f"阈值 {threshold:.2f}: 无有效数据")

if __name__ == "__main__":
    try:
        test_dimension_analysis()
        
        # 询问是否进行阈值敏感性测试
        if input("\n是否进行阈值敏感性测试? (y/n): ").lower() == 'y':
            test_threshold_sensitivity()
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
