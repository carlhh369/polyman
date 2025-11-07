"""
风险管理模块
"""
from typing import Dict, Any
from datetime import datetime
from config import config
from utils.logger import logger
from utils.helpers import calculate_kelly_size, calculate_risk_score


class RiskManager:
    """风险管理器"""
    
    def __init__(self):
        self.daily_trades = 0
        self.last_reset = datetime.now().date()
        self.open_positions = 0
    
    def reset_daily_counter(self):
        """重置每日计数器"""
        today = datetime.now().date()
        if today > self.last_reset:
            self.daily_trades = 0
            self.last_reset = today
            logger.info("每日交易计数器已重置")
    
    def can_trade(self) -> bool:
        """检查是否可以交易"""
        self.reset_daily_counter()
        
        if self.daily_trades >= config.MAX_DAILY_TRADES:
            logger.warning(f"已达到每日交易限制: {config.MAX_DAILY_TRADES}")
            return False
        
        if self.open_positions >= config.MAX_OPEN_POSITIONS:
            logger.warning(f"已达到最大持仓数: {config.MAX_OPEN_POSITIONS}")
            return False
        
        return True
    
    def calculate_position_size(
        self,
        edge: float,
        current_price: float
    ) -> float:
        """
        计算仓位大小
        
        Args:
            edge: 价格边际
            current_price: 当前价格
        
        Returns:
            仓位大小（USDC）
        """
        size = calculate_kelly_size(
            edge=edge,
            current_price=current_price,
            max_position=config.MAX_POSITION_SIZE,
            risk_limit=config.RISK_LIMIT_PER_TRADE
        )
        
        logger.debug(f"计算仓位: edge={edge:.3f}, price={current_price:.3f} -> size=${size}")
        return size
    
    def evaluate_opportunity(
        self,
        opportunity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估交易机会
        
        Args:
            opportunity: 交易机会数据
        
        Returns:
            评估结果
        """
        # 计算风险评分（calculate_risk_score 会自动处理类型转换）
        risk_score = calculate_risk_score(
            volume=opportunity.get("volume", 0),
            hours_to_expiry=opportunity.get("hours_to_expiry"),
            edge=opportunity.get("edge", 0)
        )
        
        # 计算最终信心度
        confidence = opportunity.get("confidence", 0)
        final_confidence = confidence * (1 - risk_score)
        
        # 计算仓位大小
        position_size = self.calculate_position_size(
            edge=opportunity.get("edge", 0),
            current_price=opportunity.get("current_price", 0.5)
        )
        
        # 判断是否应该交易
        should_trade = (
            final_confidence >= config.MIN_CONFIDENCE_THRESHOLD and
            position_size > 0 and
            opportunity.get("expected_value", 0) > 5 and
            risk_score < 0.5 and
            self.can_trade()
        )
        
        # 生成交易理由
        reasoning = self._generate_reasoning(
            opportunity,
            should_trade,
            final_confidence,
            risk_score
        )
        
        return {
            "should_trade": should_trade,
            "position_size": position_size,
            "final_confidence": final_confidence,
            "risk_score": risk_score,
            "reasoning": reasoning
        }
    
    def _generate_reasoning(
        self,
        opportunity: Dict[str, Any],
        should_trade: bool,
        final_confidence: float,
        risk_score: float
    ) -> str:
        """生成交易理由"""
        reasons = []
        
        if should_trade:
            reasons.append(f"信心度: {final_confidence*100:.1f}%")
            reasons.append(f"期望值: ${opportunity.get('expected_value', 0):.2f}")
            
            if opportunity.get("news_signals"):
                reasons.append(f"新闻支持: {len(opportunity['news_signals'])} 条信号")
            
            edge = opportunity.get("edge", 0)
            reasons.append(
                f"价格优势: {opportunity.get('current_price', 0)*100:.1f}% -> "
                f"{(opportunity.get('current_price', 0) + edge)*100:.1f}%"
            )
        else:
            if final_confidence < config.MIN_CONFIDENCE_THRESHOLD:
                reasons.append(
                    f"信心度不足 ({final_confidence*100:.1f}% < "
                    f"{config.MIN_CONFIDENCE_THRESHOLD*100:.0f}%)"
                )
            
            if opportunity.get("expected_value", 0) <= 5:
                reasons.append(
                    f"期望值过小 (${opportunity.get('expected_value', 0):.2f})"
                )
            
            if risk_score > 0.5:
                reasons.append(f"风险评分过高 ({risk_score*100:.1f}%)")
            
            if not self.can_trade():
                reasons.append("已达到交易限制")
        
        return ". ".join(reasons)
    
    def record_trade(self):
        """记录一笔交易"""
        self.daily_trades += 1
        self.open_positions += 1
        logger.info(f"记录交易: 今日 {self.daily_trades}/{config.MAX_DAILY_TRADES}")
    
    def close_position(self):
        """关闭一个持仓"""
        if self.open_positions > 0:
            self.open_positions -= 1
            logger.info(f"关闭持仓: 当前 {self.open_positions}/{config.MAX_OPEN_POSITIONS}")
