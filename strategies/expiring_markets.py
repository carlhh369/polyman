"""
到期市场策略（Chalk Eater）
"""
import json
from typing import List, Dict, Any
from strategies.base import BaseStrategy, MarketOpportunity
from config import config
from utils.logger import logger
from utils.helpers import parse_market_end_date, hours_until_expiry


class ExpiringMarketsStrategy(BaseStrategy):
    """到期市场策略 - 针对即将到期的高概率市场"""
    
    def __init__(self):
        strategy_config = {
            "enabled": True,
            "min_probability": config.EXPIRING_MIN_PROBABILITY,
            "max_hours_to_expiry": config.EXPIRING_MAX_HOURS,
            "min_hours_to_expiry": config.EXPIRING_MIN_HOURS,
            "min_volume": config.EXPIRING_MIN_VOLUME
        }
        
        super().__init__(
            name="ExpiringMarketsStrategy",
            description="针对即将到期且高概率的市场",
            config=strategy_config
        )
    
    def find_opportunities(
        self,
        markets: List[Dict[str, Any]],
        open_positions: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """查找交易机会"""
        if not self.is_active():
            return []
        
        opportunities = []
        
        logger.info(f"到期市场策略: 扫描 {len(markets)} 个市场")
        
        for market in markets:
            condition_id = market.get("conditionId")
            
            # 跳过已有持仓
            if condition_id in open_positions:
                continue
            
            # 分析市场
            market_opportunities = self.analyze_market(market)
            opportunities.extend(market_opportunities)
        
        logger.info(f"找到 {len(opportunities)} 个到期市场机会")
        return opportunities
    
    def analyze_market(
        self,
        market: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """分析单个市场"""
        opportunities = []
        
        # 检查是否即将到期
        if "endDate" not in market:
            return opportunities
        
        end_date = parse_market_end_date(market["endDate"])
        if not end_date:
            return opportunities
        
        hours_to_exp = hours_until_expiry(end_date)
        
        # 检查到期时间窗口
        if (hours_to_exp > self.config["max_hours_to_expiry"] or
            hours_to_exp < self.config["min_hours_to_expiry"]):
            return opportunities
        
        # 检查交易量
        volume = market.get("volume", 0)
        if volume < self.config["min_volume"]:
            logger.debug(
                f"市场 {market.get('question', '')[:50]}... 交易量过低: ${volume}"
            )
            return opportunities
        
        # 获取价格和结果
        prices = self.extract_prices(market)
        try:
            outcomes = json.loads(market.get("outcomes", '["Yes", "No"]'))
        except:
            outcomes = ["Yes", "No"]
        
        # 寻找高概率结果
        for i, outcome in enumerate(outcomes):
            if i >= len(prices):
                continue
            
            price = prices[i]
            outcome_name = outcome.upper()
            
            # 寻找极高概率的结果 (>= 95%)
            if price >= self.config["min_probability"]:
                profit_margin = 1.0 - price
                expected_return = profit_margin * 100
                
                # 计算信心度
                price_conf = (price - self.config["min_probability"]) / (1 - self.config["min_probability"])
                time_conf = 1 - (hours_to_exp / self.config["max_hours_to_expiry"])
                confidence = min(0.95, (price_conf + time_conf) / 2)
                
                opportunities.append(MarketOpportunity(
                    market_id=market.get("conditionId", ""),
                    question=market.get("question", ""),
                    outcome=outcome_name,
                    current_price=price,
                    predicted_probability=0.99,
                    confidence=confidence,
                    expected_value=expected_return,
                    news_signals=[
                        f"到期时间: {hours_to_exp:.1f} 小时",
                        f"当前价格: {price*100:.1f}%",
                        f"预期回报: {expected_return:.1f}%"
                    ],
                    risk_score=1 - price,
                    volume=volume,
                    hours_to_expiry=hours_to_exp
                ))
                
                logger.info(
                    f"📈 到期机会: {market.get('question', '')[:50]}..."
                )
                logger.info(
                    f"   {outcome_name} @ {price*100:.1f}% | "
                    f"到期: {hours_to_exp:.1f}h | 回报: {expected_return:.1f}%"
                )
            
            # 寻找极低概率的 NO 机会
            if price <= (1 - self.config["min_probability"]):
                no_price = 1 - price
                profit_margin = 1.0 - no_price
                expected_return = profit_margin * 100
                
                price_conf = (no_price - self.config["min_probability"]) / (1 - self.config["min_probability"])
                time_conf = 1 - (hours_to_exp / self.config["max_hours_to_expiry"])
                confidence = min(0.95, (price_conf + time_conf) / 2)
                
                opportunities.append(MarketOpportunity(
                    market_id=market.get("conditionId", ""),
                    question=market.get("question", ""),
                    outcome="NO",
                    current_price=no_price,
                    predicted_probability=0.99,
                    confidence=confidence,
                    expected_value=expected_return,
                    news_signals=[
                        f"到期时间: {hours_to_exp:.1f} 小时",
                        f"NO 价格: {no_price*100:.1f}% (YES @ {price*100:.1f}%)",
                        f"预期回报: {expected_return:.1f}%"
                    ],
                    risk_score=1 - no_price,
                    volume=volume,
                    hours_to_expiry=hours_to_exp
                ))
                
                logger.info(
                    f"📉 到期机会(反向): {market.get('question', '')[:50]}..."
                )
                logger.info(
                    f"   NO @ {no_price*100:.1f}% | "
                    f"到期: {hours_to_exp:.1f}h | 回报: {expected_return:.1f}%"
                )
        
        return opportunities
