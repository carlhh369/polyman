"""
指数跟踪策略
跟随 SPMC 指数配置并进行再平衡
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from strategies.base import BaseStrategy, MarketOpportunity
from services.index_trading import IndexTradingService
from config import config
from utils.logger import logger


class IndexStrategy(BaseStrategy):
    """
    指数跟踪策略
    
    严格跟踪 SPMC 指数配置，当实际持仓与目标偏离超过阈值时进行再平衡
    """
    
    def __init__(self, index_id: str = None):
        # 从环境变量或参数获取指数 ID
        if index_id is None:
            index_id = config.__dict__.get("SPMC_INDEX_ID", "default-index")
        
        strategy_config = {
            "enabled": True,
            "index_id": index_id,
            "rebalance_threshold": 0.05,  # 5% 偏差触发再平衡
            "check_interval": 60,  # 60 分钟检查一次
            "max_position_deviation": 0.10  # 最大允许 10% 偏差
        }
        
        super().__init__(
            name="IndexStrategy",
            description="跟随 SPMC 指数配置并维持投资组合对齐",
            config=strategy_config
        )
        
        self.index_service: IndexTradingService = None
        self.last_check = datetime.min
    
    async def initialize(self):
        """初始化策略"""
        if self.config["enabled"]:
            self.index_service = IndexTradingService.get_instance(
                self.config["index_id"]
            )
            await self.index_service.initialize()
            logger.info(
                f"指数策略已初始化，指数: {self.config['index_id']}"
            )
    
    def find_opportunities(
        self,
        markets: List[Dict[str, Any]],
        open_positions: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """查找交易机会"""
        if not self.is_active() or not self.index_service:
            return []
        
        # 检查是否到了检查时间
        now = datetime.now()
        minutes_since_last = (now - self.last_check).total_seconds() / 60
        
        if minutes_since_last < self.config["check_interval"]:
            logger.debug(
                f"指数策略: 跳过检查，距上次检查仅 "
                f"{minutes_since_last:.1f} 分钟"
            )
            return []
        
        self.last_check = now
        logger.info("指数策略: 检查再平衡机会")
        
        try:
            # 使用同步方式获取指数状态（简化实现）
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            index_status = loop.run_until_complete(
                self.index_service.get_index_status()
            )
            
            if not index_status or not index_status.target_allocations:
                logger.warning("指数策略: 无法获取指数状态")
                return []
            
            opportunities = []
            
            # 检查每个目标配置
            for target in index_status.target_allocations:
                current_position = open_positions.get(target.condition_id, {})
                current_allocation = current_position.get("size", 0)
                target_allocation = target.target_shares
                
                # 计算偏差
                if target_allocation == 0:
                    deviation = 1.0 if current_allocation > 0 else 0
                else:
                    deviation = (
                        abs(target_allocation - current_allocation) /
                        target_allocation
                    )
                
                # 如果偏差超过阈值，创建机会
                if deviation > self.config["rebalance_threshold"]:
                    # 从市场列表中查找对应市场
                    market = self._find_market_by_condition_id(
                        markets,
                        target.condition_id
                    )
                    
                    if market:
                        prices = self.extract_prices(market)
                        need_to_buy = target_allocation > current_allocation
                        
                        opportunities.append(MarketOpportunity(
                            market_id=target.condition_id,
                            question=market.get("question", ""),
                            outcome=target.outcome,
                            current_price=prices[0] if prices else 0.5,
                            predicted_probability=prices[0] if prices else 0.5,
                            confidence=0.9,  # 指数跟踪高信心
                            expected_value=0,  # 不基于边际，而是基于指数配置
                            news_signals=[
                                f"指数再平衡: "
                                f"{'买入' if need_to_buy else '卖出'} "
                                f"以匹配 {self.config['index_id']} 配置"
                            ],
                            risk_score=0.1,  # 指数跟踪低风险
                            volume=market.get("volume", 0)
                        ))
                        
                        logger.info(
                            f"指数机会: {market.get('question', '')[:50]}... - "
                            f"{'买入' if need_to_buy else '卖出'} "
                            f"{abs(target_allocation - current_allocation)} 份额"
                        )
            
            # 检查持有但不在指数中的持仓
            for condition_id, position in open_positions.items():
                in_index = any(
                    t.condition_id == condition_id
                    for t in index_status.target_allocations
                )
                
                if not in_index and position.get("size", 0) > 0:
                    market = self._find_market_by_condition_id(
                        markets,
                        condition_id
                    )
                    
                    if market:
                        prices = self.extract_prices(market)
                        
                        opportunities.append(MarketOpportunity(
                            market_id=condition_id,
                            question=market.get("question", ""),
                            outcome=position.get("outcome", "YES"),
                            current_price=prices[0] if prices else 0.5,
                            predicted_probability=0,  # 卖出目标
                            confidence=0.95,  # 非常高的信心退出非指数持仓
                            expected_value=0,
                            news_signals=[
                                f"指数再平衡: 退出不在 "
                                f"{self.config['index_id']} 中的持仓"
                            ],
                            risk_score=0.05,
                            volume=market.get("volume", 0)
                        ))
                        
                        logger.info(
                            f"指数退出机会: {market.get('question', '')[:50]}... - "
                            f"卖出全部持仓（不在指数中）"
                        )
            
            return opportunities
            
        except Exception as e:
            logger.error(f"指数策略错误: {e}")
            return []
    
    def analyze_market(
        self,
        market: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """
        分析单个市场
        
        指数策略不分析单个市场，只跟随指数配置
        """
        return []
    
    def _find_market_by_condition_id(
        self,
        markets: List[Dict[str, Any]],
        condition_id: str
    ) -> Dict[str, Any]:
        """根据 condition_id 查找市场"""
        for market in markets:
            if market.get("conditionId") == condition_id:
                return market
        
        # 如果在列表中找不到，尝试从 API 获取
        try:
            from services.polymarket import PolymarketService
            service = PolymarketService()
            market = service.get_market_by_condition_id(condition_id)
            if market:
                return market
        except Exception as e:
            logger.debug(f"无法获取市场 {condition_id}: {e}")
        
        return {}
