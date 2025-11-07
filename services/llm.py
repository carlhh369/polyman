"""
LLM 服务模块
统一管理大语言模型调用
"""
from typing import Optional
from config import config
from utils.logger import logger
import requests


class LLMService:
    """LLM 服务类"""
    
    def __init__(self):
        """初始化 LLM 服务"""
        self.api_key = config.OPENROUTER_API_KEY
        self.api_url = config.OPENROUTER_API_URL
        self.model = config.OPENROUTER_MODEL
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            logger.info(f"✓ LLM 服务已启用 (模型: {self.model})")
        else:
            logger.info("LLM 服务未启用（未配置 API Key）")
    
    def is_enabled(self) -> bool:
        """检查 LLM 服务是否启用"""
        return self.enabled
    
    def call(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        调用 LLM API
        
        Args:
            prompt: 用户提示词
            max_tokens: 最大 token 数
            temperature: 温度参数（0-1，越低越确定）
            system_prompt: 系统提示词（可选）
        
        Returns:
            模型响应文本
        
        Raises:
            Exception: API 调用失败时抛出异常
        """
        if not self.enabled:
            raise Exception("LLM 服务未启用，请配置 OPENROUTER_API_KEY")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            logger.debug(f"LLM 调用成功 (tokens: {result.get('usage', {}).get('total_tokens', 'N/A')})")
            
            return content
            
        except requests.exceptions.Timeout:
            logger.error("LLM API 调用超时")
            raise Exception("LLM API 调用超时")
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API 调用失败: {e}")
            raise Exception(f"LLM API 调用失败: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"LLM 响应解析失败: {e}")
            raise Exception(f"LLM 响应解析失败: {e}")
    
    def call_with_retry(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None,
        max_retries: int = 2
    ) -> Optional[str]:
        """
        带重试的 LLM 调用
        
        Args:
            prompt: 用户提示词
            max_tokens: 最大 token 数
            temperature: 温度参数
            system_prompt: 系统提示词
            max_retries: 最大重试次数
        
        Returns:
            模型响应文本，失败返回 None
        """
        for attempt in range(max_retries + 1):
            try:
                return self.call(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system_prompt=system_prompt
                )
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM 调用失败，重试 {attempt + 1}/{max_retries}: {e}")
                else:
                    logger.error(f"LLM 调用失败，已达最大重试次数: {e}")
                    return None
        
        return None


# 创建全局 LLM 服务实例
llm_service = LLMService()
