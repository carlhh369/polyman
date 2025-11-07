"""
基础策略类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from utils.logger import logger


class MarketOpportunity:
    """市场机会类"""
    
    def __init__(
        self,
        market_id: str,
        question: str,
        outcome: str,
        current_price: float,
        predicted_probability: float,
        confidence: float,
        expected_value: float,
        news_signals: List[str],
        risk_score: float,
        volume: float = 0,
        hours_to_expiry: Optional[float] = None
    ):
        self.market_id = market_id
        self.question = question
        self.outcome = outcome
        self.current_price = current_price
        self.predicted_probability = predicted_probability
        self.confidence = confidence
        self.expected_value = expected_value
        self.news_signals = news_signals
        self.risk_score = risk_score
        self.volume = volume
        self.hours_to_expiry = hours_to_expiry
        self.edge = abs(predicted_probability - current_price)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "market_id": self.market_id,
            "question": self.question,
            "outcome": self.outcome,
            "current_price": self.current_price,
            "predicted_probability": self.predicted_probability,
            "confidence": self.confidence,
            "expected_value": self.expected_value,
            "news_signals": self.news_signals,
            "risk_score": self.risk_score,
            "volume": self.volume,
            "hours_to_expiry": self.hours_to_expiry,
            "edge": self.edge
        }
    
    def __repr__(self):
        return (
            f"<Opportunity: {self.question[:30]}... "
            f"{self.outcome} @ {self.current_price:.2f} "
            f"(conf: {self.confidence:.2f})>"
        )


class BaseStrategy(ABC):
    """基础策略抽象类"""
    
    def __init__(self, name: str, description: str, config: Dict[str, Any]):
        self.name = name
        self.description = description
        self.config = config
        self.enabled = config.get("enabled", True)
    
    @abstractmethod
    def find_opportunities(
        self,
        markets: List[Dict[str, Any]],
        open_positions: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """
        查找交易机会
        
        Args:
            markets: 市场列表
            open_positions: 当前持仓
        
        Returns:
            机会列表
        """
        pass
    
    @abstractmethod
    def analyze_market(
        self,
        market: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """
        分析单个市场
        
        Args:
            market: 市场数据
        
        Returns:
            机会列表
        """
        pass
    
    def is_active(self) -> bool:
        """策略是否激活"""
        return self.enabled
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self.config
    
    def update_config(self, config: Dict[str, Any]):
        """更新配置"""
        self.config.update(config)
        logger.info(f"{self.name} 配置已更新: {config}")
    
    def extract_prices(self, market: Dict[str, Any]) -> List[float]:
        """从市场数据提取价格"""
        prices = []
        
        # 尝试从 outcomePrices 获取
        if "outcomePrices" in market and market["outcomePrices"]:
            try:
                import json
                price_strings = json.loads(market["outcomePrices"])
                prices = [float(p) for p in price_strings]
            except:
                pass
        
        # 尝试从 marketMakerData 获取
        if not prices and "marketMakerData" in market:
            try:
                import json
                mm_data = json.loads(market.get("marketMakerData", "{}"))
                prices = mm_data.get("prices", [])
            except:
                pass
        
        # 使用 bid/ask 中间价
        if not prices and "bestBid" in market and "bestAsk" in market:
            try:
                bid = float(market.get("bestBid", 0.5))
                ask = float(market.get("bestAsk", 0.5))
                prices = [(bid + ask) / 2]
            except:
                pass
        
        # 默认值
        if not prices:
            prices = [0.5]
        
        return prices
    
    def calculate_risk_score(
        self,
        market: Dict[str, Any],
        edge: float
    ) -> float:
        """计算风险评分"""
        from utils.helpers import safe_float
        
        volume = safe_float(market.get("volume", 0), 0)
        edge = safe_float(edge, 0)
        
        volume_risk = 0.3 if volume < 50000 else 0
        
        # 时间风险
        time_risk = 0
        if "endDate" in market:
            from utils.helpers import parse_market_end_date, hours_until_expiry
            end_date = parse_market_end_date(market["endDate"])
            if end_date:
                hours = hours_until_expiry(end_date)
                time_risk = 0.3 if hours < 24 else 0
        
        edge_risk = 0.4 if edge < 0.1 else 0
        
        return volume_risk + time_risk + edge_risk
