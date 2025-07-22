# file: core/ai_translator/tools/get_models.py
"""
获取 OpenAI 兼容接口的模型列表工具
=====================================

本脚本用于查询一个 OpenAI 兼容的 API 端点，并列出其支持的所有模型。

如何使用:
1. 在下面的 `API_KEY` 和 `API_BASE_URL` 变量中填入您的信息。
2. 从项目根目录运行此脚本: `python -m core.ai_translator.tools.get_models`
"""
import asyncio
import aiohttp
import json

# --- 请在此处配置您的 API 信息 ---
API_KEY = "user-token"  # 填入您的 API 密钥
API_BASE_URL = "http://localhost:8888/v1" # 您指定的 API 地址
# ------------------------------------

async def fetch_models():
    """
    连接到 API 端点并获取模型列表。
    """
    if API_KEY == "YOUR_API_KEY_HERE":
        print("错误：请先在本脚本中设置您的 API_KEY。")
        return

    print(f"正在从 {API_BASE_URL} 获取模型列表...")
    
    api_url = f"{API_BASE_URL.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url, headers=headers, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
                print("\n--- 可用模型列表 ---")
                # 格式化输出 JSON
                print(json.dumps(data, indent=2, ensure_ascii=False))

                # 提取并打印模型 ID 列表
                if 'data' in data and isinstance(data['data'], list):
                    model_ids = [model.get('id') for model in data['data'] if 'id' in model]
                    print("\n--- 模型 ID ---")
                    for model_id in sorted(model_ids):
                        print(model_id)
                
        except aiohttp.ClientResponseError as e:
            print(f"\n错误：无法连接到 API 或 API 返回错误。")
            print(f"状态码: {e.status}")
            print(f"信息: {e.message}")
        except Exception as e:
            print(f"\n发生未知错误: {e}")

async def main():
    await fetch_models()

if __name__ == "__main__":
    asyncio.run(main())