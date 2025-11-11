"""
LLM 增强的到期市场策略
基于 expiring_markets 策略，使用大模型进行智能决策
"""
import json
from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, MarketOpportunity
from services.llm import llm_service
from config import config
from utils.logger import logger
from utils.helpers import parse_market_end_date, hours_until_expiry


class LLMExpiringMarketsStrategy(BaseStrategy):
    """LLM 增强的到期市场策略 - 使用大模型判断即将到期市场的交易机会"""
    
    def __init__(self):
        strategy_config = {
            "enabled": True,
            "min_probability": config.EXPIRING_MIN_PROBABILITY,
            "max_hours_to_expiry": config.EXPIRING_MAX_HOURS,
            "min_hours_to_expiry": config.EXPIRING_MIN_HOURS,
            "min_volume": config.EXPIRING_MIN_VOLUME,
            "llm_confidence_threshold": 0.7,  # LLM 判断的最低信心阈值
            "use_llm_override": True  # 是否允许 LLM 覆盖规则判断
        }
        
        super().__init__(
            name="LLMExpiringMarketsStrategy",
            description="使用 LLM 智能分析即将到期的市场机会",
            config=strategy_config
        )
        
        self.llm_enabled = llm_service.is_enabled()
        if not self.llm_enabled:
            logger.warning(f"{self.name}: LLM 服务未启用，将回退到规则判断")

    def find_opportunities(
        self,
        markets: List[Dict[str, Any]],
        open_positions: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """查找交易机会"""
        if not self.is_active():
            return []
        
        opportunities = []
        
        logger.info(f"LLM 到期市场策略: 扫描 {len(markets)} 个市场")
        
        for market in markets:
            condition_id = market.get("conditionId")
            
            # 跳过已有持仓
            if condition_id in open_positions:
                continue
            
            # 分析市场
            market_opportunities = self.analyze_market(market)
            opportunities.extend(market_opportunities)
        
        logger.info(f"找到 {len(opportunities)} 个 LLM 到期市场机会")
        return opportunities
    
    def analyze_market(
        self,
        market: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """分析单个市场 - 使用 LLM 增强决策"""
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
            return opportunities
        
        # 获取价格和结果
        prices = self.extract_prices(market)
        try:
            outcomes = json.loads(market.get("outcomes", '["Yes", "No"]'))
        except:
            outcomes = ["Yes", "No"]
        
        # 使用 LLM 分析市场
        if self.llm_enabled:
            llm_opportunities = self._analyze_with_llm(
                market, prices, outcomes, hours_to_exp, volume
            )
            if llm_opportunities:
                opportunities.extend(llm_opportunities)
                return opportunities
        
        # 回退到规则判断
        opportunities.extend(
            self._analyze_with_rules(market, prices, outcomes, hours_to_exp, volume)
        )
        
        return opportunities

    def _build_llm_prompt(
        self,
        market: Dict[str, Any],
        prices: List[float],
        outcomes: List[str],
        hours_to_exp: float,
        volume: float
    ) -> str:
        """Build LLM analysis prompt"""
        question = market.get("question", "")
        description = market.get("description", "")
        
        # Build price information
        price_info = []
        for i, outcome in enumerate(outcomes):
            if i < len(prices):
                price_info.append(f"  - {outcome}: {prices[i]*100:.1f}%")
        price_text = "\n".join(price_info)
        
        prompt = f"""You are a professional prediction market trading analyst. Analyze the following expiring market and determine if there is a high-certainty trading opportunity.

Market Question:
{question}

Market Description:
{description if description else "None"}

Current Market Status:
- Time until expiry: {hours_to_exp:.1f} hours
- Trading volume: ${volume:,.0f}
- Current prices:
{price_text}

Analysis Points:
1. Does the market question already have a clear answer or highly certain outcome?
2. Does the current price reflect the true probability? Is there an obvious mispricing?
3. Given the imminent expiry ({hours_to_exp:.1f} hours), how certain is the outcome?
4. Is the trading volume (${volume:,.0f}) sufficient to support a trade?
5. Are there any potential black swan events that could change the outcome?

Please respond in JSON format with the following fields:
{{
  "has_opportunity": true/false,
  "recommended_outcome": "YES/NO/outcome_name",
  "confidence": 0.0-1.0,
  "reasoning": "Brief analysis rationale",
  "risk_factors": ["risk_factor_1", "risk_factor_2"],
  "expected_probability": 0.0-1.0
}}

Important Notes:
- confidence represents your certainty in the judgment (only consider trading if >= 0.7)
- expected_probability represents the true probability you believe for this outcome
- Only recommend trades when outcome is highly certain (>95%) and price is favorable
- Given the short time to expiry, prioritize events that are already determined or near-certain"""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                logger.warning("LLM 响应中未找到 JSON 格式")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"LLM 响应 JSON 解析失败: {e}")
            logger.debug(f"原始响应: {response}")
            return None

    def _analyze_with_llm(
        self,
        market: Dict[str, Any],
        prices: List[float],
        outcomes: List[str],
        hours_to_exp: float,
        volume: float
    ) -> List[MarketOpportunity]:
        """使用 LLM 分析市场"""
        opportunities = []
        
        # 构建提示词
        prompt = self._build_llm_prompt(market, prices, outcomes, hours_to_exp, volume)
        
        # Call LLM
        system_prompt = "You are a professional prediction market trading analyst, skilled at identifying high-certainty trading opportunities. Always respond in JSON format."
        
        response = llm_service.call_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,  # Low temperature for more deterministic judgments
            max_tokens=800
        )
        
        if not response:
            logger.warning(f"LLM 调用失败，回退到规则判断: {market.get('question', '')[:50]}...")
            return []
        
        # 解析响应
        llm_result = self._parse_llm_response(response)
        if not llm_result:
            return []
        
        # 检查是否有机会
        if not llm_result.get("has_opportunity", False):
            logger.debug(f"LLM 判断无机会: {market.get('question', '')[:50]}...")
            return []
        
        # 检查信心阈值
        llm_confidence = llm_result.get("confidence", 0)
        if llm_confidence < self.config["llm_confidence_threshold"]:
            logger.debug(
                f"LLM 信心不足 ({llm_confidence:.2f}): {market.get('question', '')[:50]}..."
            )
            return []
        
        # 获取推荐结果
        recommended_outcome = llm_result.get("recommended_outcome", "").upper()
        expected_prob = llm_result.get("expected_probability", 0.99)
        reasoning = llm_result.get("reasoning", "")
        risk_factors = llm_result.get("risk_factors", [])
        
        # 查找对应的价格
        outcome_index = -1
        for i, outcome in enumerate(outcomes):
            if outcome.upper() == recommended_outcome:
                outcome_index = i
                break
        
        if outcome_index == -1 or outcome_index >= len(prices):
            logger.warning(f"LLM 推荐的结果 {recommended_outcome} 未找到对应价格")
            return []
        
        current_price = prices[outcome_index]
        
        # 计算预期回报
        profit_margin = expected_prob - current_price
        expected_return = (profit_margin / current_price) * 100 if current_price > 0 else 0
        
        # 只在有正向预期时创建机会
        if profit_margin <= 0:
            logger.debug(
                f"LLM 推荐但无正向预期: {recommended_outcome} @ {current_price*100:.1f}% "
                f"(预期: {expected_prob*100:.1f}%)"
            )
            return []
        
        # 构建信号列表
        news_signals = [
            f"🤖 LLM 分析 (信心: {llm_confidence*100:.0f}%)",
            f"到期时间: {hours_to_exp:.1f} 小时",
            f"当前价格: {current_price*100:.1f}%",
            f"预期概率: {expected_prob*100:.1f}%",
            f"预期回报: {expected_return:.1f}%",
            f"分析: {reasoning}"
        ]
        
        if risk_factors:
            news_signals.append(f"风险: {', '.join(risk_factors)}")
        
        # 计算综合风险评分
        price_risk = 1 - expected_prob
        time_risk = min(0.3, hours_to_exp / self.config["max_hours_to_expiry"])
        volume_risk = 0.2 if volume < 50000 else 0
        llm_risk = 1 - llm_confidence
        
        risk_score = (price_risk + time_risk + volume_risk + llm_risk) / 4
        
        opportunity = MarketOpportunity(
            market_id=market.get("conditionId", ""),
            question=market.get("question", ""),
            outcome=recommended_outcome,
            current_price=current_price,
            predicted_probability=expected_prob,
            confidence=llm_confidence,
            expected_value=expected_return,
            news_signals=news_signals,
            risk_score=risk_score,
            volume=volume,
            hours_to_expiry=hours_to_exp
        )
        
        opportunities.append(opportunity)
        
        logger.info(f"🤖 LLM 到期机会: {market.get('question', '')[:50]}...")
        logger.info(
            f"   {recommended_outcome} @ {current_price*100:.1f}% | "
            f"LLM信心: {llm_confidence*100:.0f}% | "
            f"到期: {hours_to_exp:.1f}h | 回报: {expected_return:.1f}%"
        )
        logger.info(f"   分析: {reasoning}")
        
        return opportunities

    def _analyze_with_rules(
        self,
        market: Dict[str, Any],
        prices: List[float],
        outcomes: List[str],
        hours_to_exp: float,
        volume: float
    ) -> List[MarketOpportunity]:
        """使用规则进行分析（回退方案）"""
        opportunities = []
        
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
                        "📊 规则判断（LLM 未启用）",
                        f"到期时间: {hours_to_exp:.1f} 小时",
                        f"当前价格: {price*100:.1f}%",
                        f"预期回报: {expected_return:.1f}%"
                    ],
                    risk_score=1 - price,
                    volume=volume,
                    hours_to_expiry=hours_to_exp
                ))
                
                logger.info(
                    f"📈 规则到期机会: {market.get('question', '')[:50]}..."
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
                        "📊 规则判断（LLM 未启用）",
                        f"到期时间: {hours_to_exp:.1f} 小时",
                        f"NO 价格: {no_price*100:.1f}% (YES @ {price*100:.1f}%)",
                        f"预期回报: {expected_return:.1f}%"
                    ],
                    risk_score=1 - no_price,
                    volume=volume,
                    hours_to_expiry=hours_to_exp
                ))
                
                logger.info(
                    f"📉 规则到期机会(反向): {market.get('question', '')[:50]}..."
                )
                logger.info(
                    f"   NO @ {no_price*100:.1f}% | "
                    f"到期: {hours_to_exp:.1f}h | 回报: {expected_return:.1f}%"
                )
        
        return opportunities
