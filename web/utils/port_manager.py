"""
端口管理工具
用于检查端口占用情况和自动选择可用端口
"""

import socket
import subprocess
import sys
import logging
from typing import Optional, List

log = logging.getLogger(__name__)


class PortManager:
    """端口管理器"""
    
    @staticmethod
    def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
        """
        检查端口是否可用
        
        Args:
            port: 端口号
            host: 主机地址
            
        Returns:
            bool: 端口是否可用
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0
        except Exception as e:
            log.warning(f"检查端口 {port} 时出错: {e}")
            return False
    
    @staticmethod
    def find_available_port(start_port: int = 8000, end_port: int = 8100, host: str = "127.0.0.1") -> Optional[int]:
        """
        查找可用端口
        
        Args:
            start_port: 起始端口
            end_port: 结束端口
            host: 主机地址
            
        Returns:
            Optional[int]: 可用端口号，如果没有找到则返回None
        """
        for port in range(start_port, end_port + 1):
            if PortManager.is_port_available(port, host):
                return port
        return None
    
    @staticmethod
    def get_port_process_info(port: int) -> Optional[dict]:
        """
        获取占用端口的进程信息
        
        Args:
            port: 端口号
            
        Returns:
            Optional[dict]: 进程信息，包含PID和进程名
        """
        try:
            if sys.platform == "win32":
                # Windows系统
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                for line in result.stdout.split('\n'):
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            try:
                                # 获取进程名
                                proc_result = subprocess.run(
                                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                lines = proc_result.stdout.strip().split('\n')
                                if len(lines) > 1:
                                    process_name = lines[1].split(',')[0].strip('"')
                                    return {
                                        "pid": pid,
                                        "process_name": process_name,
                                        "port": port
                                    }
                            except Exception:
                                return {
                                    "pid": pid,
                                    "process_name": "Unknown",
                                    "port": port
                                }
            else:
                # Linux/Mac系统
                result = subprocess.run(
                    ["lsof", "-i", f":{port}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        return {
                            "pid": parts[1],
                            "process_name": parts[0],
                            "port": port
                        }
                        
        except Exception as e:
            log.warning(f"获取端口 {port} 进程信息时出错: {e}")
        
        return None
    
    @staticmethod
    def kill_port_process(port: int) -> bool:
        """
        杀死占用端口的进程
        
        Args:
            port: 端口号
            
        Returns:
            bool: 是否成功杀死进程
        """
        process_info = PortManager.get_port_process_info(port)
        if not process_info:
            log.info(f"端口 {port} 没有被占用")
            return True
        
        pid = process_info["pid"]
        process_name = process_info["process_name"]
        
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["taskkill", "/PID", pid, "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                success = result.returncode == 0
            else:
                result = subprocess.run(
                    ["kill", "-9", pid],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                success = result.returncode == 0
            
            if success:
                log.info(f"成功杀死进程 {process_name} (PID: {pid})，释放端口 {port}")
            else:
                log.error(f"杀死进程失败: {result.stderr}")
            
            return success
            
        except Exception as e:
            log.error(f"杀死端口 {port} 进程时出错: {e}")
            return False
    
    @staticmethod
    def ensure_port_available(preferred_port: int, auto_kill: bool = False) -> int:
        """
        确保端口可用
        
        Args:
            preferred_port: 首选端口
            auto_kill: 是否自动杀死占用进程
            
        Returns:
            int: 可用的端口号
        """
        # 检查首选端口是否可用
        if PortManager.is_port_available(preferred_port):
            return preferred_port
        
        # 如果端口被占用，获取进程信息
        process_info = PortManager.get_port_process_info(preferred_port)
        if process_info:
            log.warning(f"端口 {preferred_port} 被进程 {process_info['process_name']} (PID: {process_info['pid']}) 占用")
            
            if auto_kill:
                log.info(f"尝试杀死占用端口 {preferred_port} 的进程...")
                if PortManager.kill_port_process(preferred_port):
                    # 等待一下让端口释放
                    import time
                    time.sleep(1)
                    if PortManager.is_port_available(preferred_port):
                        return preferred_port
        
        # 如果首选端口不可用，查找其他可用端口
        log.info(f"端口 {preferred_port} 不可用，正在查找其他可用端口...")
        available_port = PortManager.find_available_port(preferred_port + 1, preferred_port + 100)
        
        if available_port:
            log.info(f"找到可用端口: {available_port}")
            return available_port
        else:
            raise RuntimeError(f"无法找到可用端口 (范围: {preferred_port}-{preferred_port + 100})")


def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="端口管理工具")
    parser.add_argument("--check", type=int, help="检查指定端口是否可用")
    parser.add_argument("--find", type=int, default=8000, help="从指定端口开始查找可用端口")
    parser.add_argument("--info", type=int, help="获取占用指定端口的进程信息")
    parser.add_argument("--kill", type=int, help="杀死占用指定端口的进程")
    
    args = parser.parse_args()
    
    if args.check:
        available = PortManager.is_port_available(args.check)
        print(f"端口 {args.check}: {'可用' if available else '被占用'}")
    
    if args.find:
        port = PortManager.find_available_port(args.find)
        if port:
            print(f"找到可用端口: {port}")
        else:
            print("未找到可用端口")
    
    if args.info:
        info = PortManager.get_port_process_info(args.info)
        if info:
            print(f"端口 {args.info} 被进程占用:")
            print(f"  PID: {info['pid']}")
            print(f"  进程名: {info['process_name']}")
        else:
            print(f"端口 {args.info} 未被占用")
    
    if args.kill:
        success = PortManager.kill_port_process(args.kill)
        if success:
            print(f"成功释放端口 {args.kill}")
        else:
            print(f"释放端口 {args.kill} 失败")


if __name__ == "__main__":
    main()
