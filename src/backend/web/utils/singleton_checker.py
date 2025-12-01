"""
应用单例检查工具
用于防止应用程序重复启动
"""

import os
import sys
import time
import logging
import tempfile
import filelock
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class SingletonChecker:
    """应用单例检查器"""

    def __init__(self, app_name: str = "MangaReader"):
        self.app_name = app_name
        self.lock_file = None
        self.lock = None
        
        # 优先使用用户目录，避免权限问题
        try:
            user_dir = Path.home()
            lock_dir = user_dir / ".manga_reader"
            lock_dir.mkdir(exist_ok=True)
            self.lock_file_path = lock_dir / f"{app_name}.lock"
        except Exception:
            # 如果用户目录不可用，回退到临时目录
            temp_dir = Path(tempfile.gettempdir())
            self.lock_file_path = temp_dir / f"{app_name}_{os.getuid() if hasattr(os, 'getuid') else os.getpid()}.lock"

    def acquire_lock(self, timeout: float = 1.0) -> bool:
        """
        获取应用锁
        
        Args:
            timeout: 获取锁的超时时间（秒）
            
        Returns:
            bool: 是否成功获取锁
        """
        try:
            # 确保锁文件目录存在
            self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建文件锁，使用更宽松的权限
            self.lock = filelock.FileLock(str(self.lock_file_path), timeout=timeout)
            
            # 尝试获取锁
            self.lock.acquire()
            
            # 在锁文件中写入进程信息
            try:
                with open(self.lock_file_path, 'w') as f:
                    f.write(f"PID: {os.getpid()}\n")
                    f.write(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"App: {self.app_name}\n")
            except Exception as e:
                log.warning(f"写入锁文件信息失败: {e}")
            
            log.info(f"成功获取应用锁: {self.lock_file_path}")
            return True
            
        except filelock.Timeout:
            log.warning(f"无法获取应用锁，应用可能已在运行: {self.lock_file_path}")
            return False
        except PermissionError as e:
            log.error(f"权限不足，无法创建锁文件: {e}")
            # 权限不足时，允许继续运行但给出警告
            print("警告: 无法创建单例锁文件，应用可能允许多实例运行")
            return True
        except Exception as e:
            log.error(f"获取应用锁时出错: {e}")
            # 其他错误也允许继续运行
            print(f"警告: 单例检查失败 ({e})，应用继续运行")
            return True

    def release_lock(self):
        """释放应用锁"""
        try:
            if self.lock:
                self.lock.release()
                self.lock = None
                
            # 删除锁文件
            if self.lock_file_path.exists():
                try:
                    self.lock_file_path.unlink()
                except PermissionError:
                    log.warning(f"权限不足，无法删除锁文件: {self.lock_file_path}")
                except Exception as e:
                    log.warning(f"删除锁文件失败: {e}")
                
            log.info("已释放应用锁")
            
        except Exception as e:
            log.error(f"释放应用锁时出错: {e}")

    def is_another_instance_running(self) -> bool:
        """
        检查是否有其他实例在运行
        
        Returns:
            bool: 是否有其他实例在运行
        """
        try:
            # 检查锁文件是否存在
            if not self.lock_file_path.exists():
                return False
                
            # 尝试获取锁，如果能获取说明没有其他实例在运行
            temp_lock = filelock.FileLock(str(self.lock_file_path), timeout=0.1)
            try:
                temp_lock.acquire()
                temp_lock.release()
                return False
            except filelock.Timeout:
                return True
                
        except Exception as e:
            log.error(f"检查应用实例时出错: {e}")
            return False

    def get_running_instance_info(self) -> Optional[dict]:
        """
        获取正在运行的实例信息
        
        Returns:
            Optional[dict]: 实例信息，如果没有则返回None
        """
        try:
            if not self.lock_file_path.exists():
                return None
                
            with open(self.lock_file_path, 'r') as f:
                content = f.read()
                
            info = {}
            for line in content.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
                    
            return info
            
        except Exception as e:
            log.error(f"获取实例信息时出错: {e}")
            return None

    def __enter__(self):
        """上下文管理器入口"""
        if not self.acquire_lock():
            info = self.get_running_instance_info()
            if info:
                log.error(f"应用已在运行 (PID: {info.get('PID', 'Unknown')})")
                print(f"错误: 应用已在运行 (PID: {info.get('PID', 'Unknown')})")
                print(f"启动时间: {info.get('Start time', 'Unknown')}")
            else:
                log.error("应用已在运行")
                print("错误: 应用已在运行")
            print("请先关闭正在运行的实例，然后再启动新实例。")
            sys.exit(1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release_lock()


def check_singleton(app_name: str = "MangaReader") -> SingletonChecker:
    """
    检查应用单例
    
    Args:
        app_name: 应用名称
        
    Returns:
        SingletonChecker: 单例检查器实例
    """
    return SingletonChecker(app_name)


def main():
    """命令行测试工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="应用单例检查工具")
    parser.add_argument("--check", action="store_true", help="检查是否有其他实例在运行")
    parser.add_argument("--app-name", default="MangaReader", help="应用名称")
    
    args = parser.parse_args()
    
    if args.check:
        checker = SingletonChecker(args.app_name)
        if checker.is_another_instance_running():
            info = checker.get_running_instance_info()
            if info:
                print(f"应用 '{args.app_name}' 已在运行:")
                print(f"  PID: {info.get('PID', 'Unknown')}")
                print(f"  启动时间: {info.get('Start time', 'Unknown')}")
            else:
                print(f"应用 '{args.app_name}' 已在运行")
        else:
            print(f"应用 '{args.app_name}' 未在运行")
    else:
        # 测试单例锁
        try:
            with SingletonChecker(args.app_name) as checker:
                print(f"成功获取应用锁 '{args.app_name}'")
                print("按回车键释放锁...")
                input()
        except SystemExit:
            print("无法获取应用锁，可能有其他实例在运行")


if __name__ == "__main__":
    main()