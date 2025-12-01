"""
端口配置管理工具
用于管理应用程序的端口配置
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


class PortConfigManager:
    """端口配置管理器"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录，默认为用户主目录下的 .manga_reader
        """
        if config_dir is None:
            # 使用用户主目录下的配置目录
            home_dir = Path.home()
            self.config_dir = home_dir / ".manga_reader"
        else:
            self.config_dir = config_dir
            
        self.config_file = self.config_dir / "port_config.json"
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 默认配置
        self.default_config = {
            "web_server": {
                "preferred_port": 9000,
                "host": "0.0.0.0",
                "auto_kill": False,
                "port_range": 100,
                "last_used_port": None
            },
            "desktop_app": {
                "preferred_port": 9000,
                "host": "127.0.0.1",
                "auto_kill": True,
                "port_range": 100,
                "last_used_port": None
            },
            "global": {
                "avoid_conflicts": True,
                "remember_last_port": True,
                "max_port_attempts": 100
            }
        }

    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 合并默认配置，确保所有必要的键都存在
                return self._merge_config(self.default_config, config)
            else:
                # 如果配置文件不存在，创建默认配置
                self.save_config(self.default_config)
                return self.default_config.copy()
                
        except Exception as e:
            log.error(f"加载配置文件失败: {e}")
            log.info("使用默认配置")
            return self.default_config.copy()

    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        保存配置文件
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 是否保存成功
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            log.info(f"配置已保存到: {self.config_file}")
            return True
            
        except Exception as e:
            log.error(f"保存配置文件失败: {e}")
            return False

    def get_web_server_config(self) -> Dict[str, Any]:
        """
        获取Web服务器配置
        
        Returns:
            Dict[str, Any]: Web服务器配置
        """
        config = self.load_config()
        return config.get("web_server", self.default_config["web_server"])

    def get_desktop_app_config(self) -> Dict[str, Any]:
        """
        获取桌面应用配置
        
        Returns:
            Dict[str, Any]: 桌面应用配置
        """
        config = self.load_config()
        return config.get("desktop_app", self.default_config["desktop_app"])

    def update_web_server_config(self, **kwargs) -> bool:
        """
        更新Web服务器配置
        
        Args:
            **kwargs: 要更新的配置项
            
        Returns:
            bool: 是否更新成功
        """
        try:
            config = self.load_config()
            web_config = config.setdefault("web_server", {})
            
            # 更新配置项
            for key, value in kwargs.items():
                if key in self.default_config["web_server"]:
                    web_config[key] = value
                else:
                    log.warning(f"未知的Web服务器配置项: {key}")
            
            return self.save_config(config)
            
        except Exception as e:
            log.error(f"更新Web服务器配置失败: {e}")
            return False

    def update_desktop_app_config(self, **kwargs) -> bool:
        """
        更新桌面应用配置
        
        Args:
            **kwargs: 要更新的配置项
            
        Returns:
            bool: 是否更新成功
        """
        try:
            config = self.load_config()
            desktop_config = config.setdefault("desktop_app", {})
            
            # 更新配置项
            for key, value in kwargs.items():
                if key in self.default_config["desktop_app"]:
                    desktop_config[key] = value
                else:
                    log.warning(f"未知的桌面应用配置项: {key}")
            
            return self.save_config(config)
            
        except Exception as e:
            log.error(f"更新桌面应用配置失败: {e}")
            return False

    def set_last_used_port(self, app_type: str, port: int) -> bool:
        """
        设置最后使用的端口
        
        Args:
            app_type: 应用类型 ("web_server" 或 "desktop_app")
            port: 端口号
            
        Returns:
            bool: 是否设置成功
        """
        try:
            config = self.load_config()
            if app_type in config:
                config[app_type]["last_used_port"] = port
                return self.save_config(config)
            else:
                log.error(f"未知的应用类型: {app_type}")
                return False
                
        except Exception as e:
            log.error(f"设置最后使用端口失败: {e}")
            return False

    def get_last_used_port(self, app_type: str) -> Optional[int]:
        """
        获取最后使用的端口
        
        Args:
            app_type: 应用类型 ("web_server" 或 "desktop_app")
            
        Returns:
            Optional[int]: 最后使用的端口号，如果没有则返回None
        """
        try:
            config = self.load_config()
            if app_type in config:
                return config[app_type].get("last_used_port")
            else:
                log.error(f"未知的应用类型: {app_type}")
                return None
                
        except Exception as e:
            log.error(f"获取最后使用端口失败: {e}")
            return None

    def reset_to_defaults(self) -> bool:
        """
        重置为默认配置
        
        Returns:
            bool: 是否重置成功
        """
        try:
            return self.save_config(self.default_config.copy())
        except Exception as e:
            log.error(f"重置配置失败: {e}")
            return False

    def _merge_config(self, default: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并配置，确保所有默认键都存在
        
        Args:
            default: 默认配置
            current: 当前配置
            
        Returns:
            Dict[str, Any]: 合并后的配置
        """
        result = default.copy()
        
        for key, value in current.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    result[key] = self._merge_config(result[key], value)
                else:
                    result[key] = value
            else:
                result[key] = value
                
        return result

    def print_config(self):
        """打印当前配置"""
        config = self.load_config()
        print("当前端口配置:")
        print("=" * 50)
        
        for section, settings in config.items():
            print(f"\n[{section}]")
            for key, value in settings.items():
                print(f"  {key}: {value}")


def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="端口配置管理工具")
    parser.add_argument("--show", action="store_true", help="显示当前配置")
    parser.add_argument("--reset", action="store_true", help="重置为默认配置")
    parser.add_argument("--set-web", nargs=2, metavar=("KEY", "VALUE"), 
                       help="设置Web服务器配置 (例: --set-web preferred_port 9001)")
    parser.add_argument("--set-desktop", nargs=2, metavar=("KEY", "VALUE"), 
                       help="设置桌面应用配置 (例: --set-desktop preferred_port 9001)")
    
    args = parser.parse_args()
    
    manager = PortConfigManager()
    
    if args.show:
        manager.print_config()
    elif args.reset:
        if manager.reset_to_defaults():
            print("配置已重置为默认值")
        else:
            print("重置配置失败")
    elif args.set_web:
        key, value = args.set_web
        # 尝试转换值的类型
        if value.isdigit():
            value = int(value)
        elif value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
            
        if manager.update_web_server_config(**{key: value}):
            print(f"Web服务器配置已更新: {key} = {value}")
        else:
            print(f"更新Web服务器配置失败: {key} = {value}")
    elif args.set_desktop:
        key, value = args.set_desktop
        # 尝试转换值的类型
        if value.isdigit():
            value = int(value)
        elif value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
            
        if manager.update_desktop_app_config(**{key: value}):
            print(f"桌面应用配置已更新: {key} = {value}")
        else:
            print(f"更新桌面应用配置失败: {key} = {value}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()