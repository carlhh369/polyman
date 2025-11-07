"""
Polymarket API 服务
"""
import requests
from typing import List, Dict, Any, Optional
from utils.logger import logger


class PolymarketService:
    """Polymarket API 服务类"""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })
    
    def get_active_markets(
        self,
        limit: int = 10,
        min_volume: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        获取活跃市场列表
        
        Args:
            limit: 返回数量限制
            min_volume: 最小交易量过滤
        
        Returns:
            市场列表
        """
        try:
            url = f"{self.BASE_URL}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "order": "volume"
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            markets = response.json()
            
            # 确保 volume 是数字类型
            for market in markets:
                if "volume" in market:
                    try:
                        market["volume"] = float(market["volume"]) if market["volume"] else 0
                    except (ValueError, TypeError):
                        market["volume"] = 0
            
            # 过滤交易量
            if min_volume:
                markets = [m for m in markets if m.get("volume", 0) >= min_volume]
            
            logger.info(f"获取到 {len(markets)} 个活跃市场")
            return markets
            
        except Exception as e:
            logger.error(f"获取市场列表失败: {e}")
            return []
    
    def get_market_by_condition_id(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 condition_id 获取市场详情
        
        Args:
            condition_id: 市场条件 ID
        
        Returns:
            市场详情
        """
        try:
            url = f"{self.BASE_URL}/markets"
            params = {"condition_ids": condition_id}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            markets = response.json()
            if markets and len(markets) > 0:
                return markets[0]
            
            return None
            
        except Exception as e:
            logger.error(f"获取市场详情失败 {condition_id}: {e}")
            return None
    
    def get_market_prices(self, market: Dict[str, Any]) -> List[float]:
        """
        提取市场价格
        
        Args:
            market: 市场数据
        
        Returns:
            价格列表
        """
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
    
    def get_user_positions(self) -> List[Dict[str, Any]]:
        """
        获取用户当前持仓
        
        Returns:
            持仓列表
        """
        # TODO: 实现获取用户持仓的逻辑
        # 需要使用 CLOB API 和用户认证
        logger.warning("get_user_positions 尚未实现")
        return []
    
    def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float
    ) -> Dict[str, Any]:
        """
        下单
        
        Args:
            token_id: 代币 ID
            side: BUY 或 SELL
            price: 价格
            size: 数量
        
        Returns:
            订单结果
        """
        # TODO: 实现下单逻辑
        # 需要使用 CLOB API 和签名
        logger.warning(f"place_order 尚未实现: {side} {size} @ {price}")
        return {
            "success": False,
            "message": "下单功能尚未实现"
        }
