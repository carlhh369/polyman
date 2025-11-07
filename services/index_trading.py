"""
指数交易服务
用于跟踪和管理 SPMC 指数配置
"""
from typing import Dict, Any, List, Optional
from utils.logger import logger


class IndexAllocation:
    """指数配置项"""
    
    def __init__(
        self,
        condition_id: str,
        outcome: str,
        target_shares: float,
        weight: float
    ):
        self.condition_id = condition_id
        self.outcome = outcome
        self.target_shares = target_shares
        self.weight = weight
    
    def __repr__(self):
        return (
            f"<IndexAllocation: {self.condition_id[:10]}... "
            f"{self.outcome} - {self.target_shares} shares>"
        )


class IndexStatus:
    """指数状态"""
    
    def __init__(
        self,
        index_id: str,
        target_allocations: List[IndexAllocation],
        total_value: float,
        last_updated: str
    ):
        self.index_id = index_id
        self.target_allocations = target_allocations
        self.total_value = total_value
        self.last_updated = last_updated
    
    def __repr__(self):
        return (
            f"<IndexStatus: {self.index_id} - "
            f"{len(self.target_allocations)} allocations>"
        )


class IndexTradingService:
    """
    指数交易服务（单例）
    
    管理 SPMC 指数的跟踪和再平衡
    """
    
    _instance: Optional['IndexTradingService'] = None
    
    def __init__(self, index_id: str):
        self.index_id = index_id
        self.current_status: Optional[IndexStatus] = None
        logger.info(f"IndexTradingService 已初始化，指数 ID: {index_id}")
    
    @classmethod
    def get_instance(cls, index_id: Optional[str] = None) -> 'IndexTradingService':
        """获取单例实例"""
        if cls._instance is None:
            if index_id is None:
                raise ValueError("首次创建实例时必须提供 index_id")
            cls._instance = cls(index_id)
        return cls._instance
    
    async def initialize(self):
        """初始化服务"""
        logger.info(f"初始化指数交易服务: {self.index_id}")
        # TODO: 从 SPMC API 获取初始配置
        pass
    
    async def get_index_status(self) -> Optional[IndexStatus]:
        """
        获取指数状态
        
        Returns:
            指数状态，包含目标配置
        """
        try:
            # TODO: 实现从 SPMC API 获取指数状态
            # 这里返回模拟数据作为示例
            
            logger.warning("get_index_status 使用模拟数据（待实现 SPMC API 集成）")
            
            # 模拟数据
            allocations = [
                IndexAllocation(
                    condition_id="0x1234567890abcdef",
                    outcome="YES",
                    target_shares=100.0,
                    weight=0.3
                ),
                IndexAllocation(
                    condition_id="0xabcdef1234567890",
                    outcome="NO",
                    target_shares=50.0,
                    weight=0.2
                ),
            ]
            
            status = IndexStatus(
                index_id=self.index_id,
                target_allocations=allocations,
                total_value=1000.0,
                last_updated="2025-01-05T00:00:00Z"
            )
            
            self.current_status = status
            return status
            
        except Exception as e:
            logger.error(f"获取指数状态失败: {e}")
            return None
    
    async def sync_with_index(self) -> Dict[str, Any]:
        """
        与指数同步
        
        Returns:
            同步结果
        """
        try:
            status = await self.get_index_status()
            
            if not status:
                return {
                    "success": False,
                    "message": "无法获取指数状态"
                }
            
            logger.info(f"与指数 {self.index_id} 同步完成")
            
            return {
                "success": True,
                "allocations": len(status.target_allocations),
                "total_value": status.total_value
            }
            
        except Exception as e:
            logger.error(f"指数同步失败: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def calculate_rebalancing_needs(
        self,
        current_positions: Dict[str, Any],
        threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        计算再平衡需求
        
        Args:
            current_positions: 当前持仓
            threshold: 偏差阈值
        
        Returns:
            需要再平衡的列表
        """
        if not self.current_status:
            logger.warning("没有可用的指数状态")
            return []
        
        rebalancing_needs = []
        
        for allocation in self.current_status.target_allocations:
            current = current_positions.get(allocation.condition_id, {})
            current_shares = current.get("size", 0)
            target_shares = allocation.target_shares
            
            if target_shares == 0:
                deviation = 1.0 if current_shares > 0 else 0
            else:
                deviation = abs(target_shares - current_shares) / target_shares
            
            if deviation > threshold:
                rebalancing_needs.append({
                    "condition_id": allocation.condition_id,
                    "outcome": allocation.outcome,
                    "current_shares": current_shares,
                    "target_shares": target_shares,
                    "deviation": deviation,
                    "action": "BUY" if target_shares > current_shares else "SELL",
                    "amount": abs(target_shares - current_shares)
                })
        
        return rebalancing_needs
