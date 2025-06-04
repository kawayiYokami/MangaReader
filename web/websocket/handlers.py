"""
WebSocket 处理器

处理WebSocket连接和消息传递，提供实时通信功能。
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime

from utils import manga_logger as log

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # 存储连接信息
        self.connection_info[websocket] = {
            "client_id": client_id or f"client_{len(self.active_connections)}",
            "connected_at": datetime.now(),
            "subscriptions": set()
        }
        
        log.info(f"WebSocket客户端连接: {self.connection_info[websocket]['client_id']}")
        
        # 发送欢迎消息
        await self.send_personal_message({
            "type": "connection",
            "status": "connected",
            "client_id": self.connection_info[websocket]["client_id"],
            "message": "WebSocket连接成功"
        }, websocket)
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        if websocket in self.active_connections:
            client_info = self.connection_info.get(websocket, {})
            client_id = client_info.get("client_id", "unknown")
            
            self.active_connections.remove(websocket)
            if websocket in self.connection_info:
                del self.connection_info[websocket]
            
            log.info(f"WebSocket客户端断开: {client_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """发送消息给特定客户端"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            log.error(f"发送WebSocket消息失败: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any], subscription: str = None):
        """广播消息给所有客户端或订阅了特定主题的客户端"""
        disconnected_clients = []
        
        for websocket in self.active_connections:
            try:
                # 如果指定了订阅主题，只发送给订阅了该主题的客户端
                if subscription:
                    client_subscriptions = self.connection_info.get(websocket, {}).get("subscriptions", set())
                    if subscription not in client_subscriptions:
                        continue
                
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
            except Exception as e:
                log.error(f"广播WebSocket消息失败: {e}")
                disconnected_clients.append(websocket)
        
        # 清理断开的连接
        for websocket in disconnected_clients:
            self.disconnect(websocket)
    
    def subscribe(self, websocket: WebSocket, subscription: str):
        """订阅主题"""
        if websocket in self.connection_info:
            self.connection_info[websocket]["subscriptions"].add(subscription)
            log.info(f"客户端 {self.connection_info[websocket]['client_id']} 订阅了 {subscription}")
    
    def unsubscribe(self, websocket: WebSocket, subscription: str):
        """取消订阅主题"""
        if websocket in self.connection_info:
            self.connection_info[websocket]["subscriptions"].discard(subscription)
            log.info(f"客户端 {self.connection_info[websocket]['client_id']} 取消订阅了 {subscription}")

# 全局连接管理器实例
manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点处理函数"""
    client_id = None
    
    try:
        # 接受连接
        await manager.connect(websocket)
        
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await handle_message(websocket, message)
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "无效的JSON格式"
                }, websocket)
            except Exception as e:
                log.error(f"处理WebSocket消息失败: {e}")
                await manager.send_personal_message({
                    "type": "error",
                    "message": f"处理消息失败: {str(e)}"
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        log.error(f"WebSocket连接异常: {e}")
        manager.disconnect(websocket)

async def handle_message(websocket: WebSocket, message: Dict[str, Any]):
    """处理接收到的WebSocket消息"""
    message_type = message.get("type")
    
    if message_type == "ping":
        # 心跳检测
        await manager.send_personal_message({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
    elif message_type == "subscribe":
        # 订阅主题
        subscription = message.get("subscription")
        if subscription:
            manager.subscribe(websocket, subscription)
            await manager.send_personal_message({
                "type": "subscribed",
                "subscription": subscription,
                "message": f"已订阅 {subscription}"
            }, websocket)
        
    elif message_type == "unsubscribe":
        # 取消订阅
        subscription = message.get("subscription")
        if subscription:
            manager.unsubscribe(websocket, subscription)
            await manager.send_personal_message({
                "type": "unsubscribed",
                "subscription": subscription,
                "message": f"已取消订阅 {subscription}"
            }, websocket)
        
    elif message_type == "get_status":
        # 获取系统状态
        await manager.send_personal_message({
            "type": "status",
            "data": {
                "connected_clients": len(manager.active_connections),
                "server_time": datetime.now().isoformat(),
                "status": "running"
            }
        }, websocket)
        
    else:
        # 未知消息类型
        await manager.send_personal_message({
            "type": "error",
            "message": f"未知的消息类型: {message_type}"
        }, websocket)

# 用于其他模块调用的广播函数
async def broadcast_translation_progress(progress: Dict[str, Any]):
    """广播翻译进度"""
    await manager.broadcast({
        "type": "translation_progress",
        "data": progress,
        "timestamp": datetime.now().isoformat()
    }, subscription="translation")

async def broadcast_scan_progress(progress: Dict[str, Any]):
    """广播扫描进度"""
    await manager.broadcast({
        "type": "scan_progress",
        "data": progress,
        "timestamp": datetime.now().isoformat()
    }, subscription="scan")

async def broadcast_system_notification(notification: Dict[str, Any]):
    """广播系统通知"""
    await manager.broadcast({
        "type": "notification",
        "data": notification,
        "timestamp": datetime.now().isoformat()
    })

async def broadcast_log_message(level: str, message: str):
    """广播日志消息"""
    await manager.broadcast({
        "type": "log",
        "data": {
            "level": level,
            "message": message
        },
        "timestamp": datetime.now().isoformat()
    }, subscription="logs")

# 导出给其他模块使用
__all__ = [
    "websocket_endpoint",
    "broadcast_translation_progress",
    "broadcast_scan_progress", 
    "broadcast_system_notification",
    "broadcast_log_message",
    "manager"
]
