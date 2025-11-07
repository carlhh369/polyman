"""
配置管理模块
从环境变量加载配置
"""
import os
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """全局配置类"""
    
    # Polymarket 配置
    POLYMARKET_PRIVATE_KEY: str = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    POLYMARKET_API_KEY: str = os.getenv("POLYMARKET_API_KEY", "")
    POLYMARKET_PASSPHRASE: str = os.getenv("POLYMARKET_PASSPHRASE", "")
    POLYMARKET_SECRET: str = os.getenv("POLYMARKET_SECRET", "")
    
    # 测试模式
    TEST_MODE: bool = os.getenv("TEST_MODE", "true").lower() == "true"
    MOCK_TRADING: bool = os.getenv("MOCK_TRADING", "true").lower() == "true"
    
    # News API
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    
    # OpenRouter API (for LLM-based analysis)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_URL: str = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")
    
    # 交易配置
    MAX_POSITION_SIZE: float = float(os.getenv("MAX_POSITION_SIZE", "100"))
    MIN_CONFIDENCE_THRESHOLD: float = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.7"))
    MAX_DAILY_TRADES: int = int(os.getenv("MAX_DAILY_TRADES", "10"))
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", "20"))
    RISK_LIMIT_PER_TRADE: float = float(os.getenv("RISK_LIMIT_PER_TRADE", "50"))
    MIN_EDGE: float = float(os.getenv("MIN_EDGE", "0.15"))
    
    # 策略选择
    STRATEGY: str = os.getenv("STRATEGY", "simple")
    
    # 简单阈值策略
    SIMPLE_BUY_THRESHOLD: float = float(os.getenv("SIMPLE_BUY_THRESHOLD", "0.3"))
    SIMPLE_SELL_THRESHOLD: float = float(os.getenv("SIMPLE_SELL_THRESHOLD", "0.7"))
    SIMPLE_MIN_EDGE: float = float(os.getenv("SIMPLE_MIN_EDGE", "0.15"))
    
    # 到期市场策略
    EXPIRING_MIN_PROBABILITY: float = float(os.getenv("EXPIRING_MIN_PROBABILITY", "0.95"))
    EXPIRING_MAX_HOURS: int = int(os.getenv("EXPIRING_MAX_HOURS", "48"))
    EXPIRING_MIN_HOURS: int = int(os.getenv("EXPIRING_MIN_HOURS", "2"))
    EXPIRING_MIN_VOLUME: float = float(os.getenv("EXPIRING_MIN_VOLUME", "10000"))
    
    # 交互式策略
    INTERACTIVE_PRICE_EDGE: float = float(os.getenv("INTERACTIVE_PRICE_EDGE", "0.15"))
    INTERACTIVE_MIN_VOLUME: float = float(os.getenv("INTERACTIVE_MIN_VOLUME", "50000"))
    SENTIMENT_WEIGHT: float = float(os.getenv("SENTIMENT_WEIGHT", "0.3"))
    PRICE_WEIGHT: float = float(os.getenv("PRICE_WEIGHT", "0.4"))
    VOLUME_WEIGHT: float = float(os.getenv("VOLUME_WEIGHT", "0.3"))
    
    # 指数跟踪策略
    SPMC_INDEX_ID: str = os.getenv("SPMC_INDEX_ID", "")
    INDEX_REBALANCE_THRESHOLD: float = float(os.getenv("INDEX_REBALANCE_THRESHOLD", "0.05"))
    INDEX_CHECK_INTERVAL: int = int(os.getenv("INDEX_CHECK_INTERVAL", "60"))
    INDEX_MAX_DEVIATION: float = float(os.getenv("INDEX_MAX_DEVIATION", "0.10"))
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "agent.log")
    
    # 监控配置
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "300"))
    
    @classmethod
    def validate(cls) -> bool:
        """验证必需的配置项"""
        # 测试模式下不需要验证 Polymarket 配置
        if cls.TEST_MODE:
            return True
        
        required = [
            ("POLYMARKET_PRIVATE_KEY", cls.POLYMARKET_PRIVATE_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            raise ValueError(f"缺少必需的配置项: {', '.join(missing)}")
        
        return True


# 创建全局配置实例
config = Config()
