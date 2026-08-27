"""
缓存管理模块

提供窗口信息的缓存机制，提高性能并减少Windows API调用频率。
"""

import time
from typing import List, Optional, Dict, Any

from .window_info import WindowInfo, DEFAULT_CACHE_DURATION


class CacheManager:
    """缓存管理器
    
    负责管理窗口信息的缓存，提供多种缓存策略和生命周期管理。
    """
    
    def __init__(self, cache_duration: float = DEFAULT_CACHE_DURATION):
        """初始化缓存管理器
        
        Args:
            cache_duration: 缓存持续时间（秒）
        """
        self.cache_duration = cache_duration
        self.last_enum_time = 0
        self.cached_windows: List[WindowInfo] = []
    
    def get_cached_windows(self) -> Optional[List[WindowInfo]]:
        """获取缓存的窗口列表
        
        Returns:
            如果缓存有效，返回窗口列表的副本；否则返回None
        """
        current_time = time.time()
        
        if (self.cached_windows and 
            current_time - self.last_enum_time < self.cache_duration):
            return self.cached_windows.copy()
        
        return None
    
    def update_cache(self, windows: List[WindowInfo]):
        """更新缓存
        
        Args:
            windows: 新的窗口列表
        """
        self.cached_windows = windows.copy()
        self.last_enum_time = time.time()
    
    def invalidate_cache(self):
        """清除缓存，强制下次重新枚举"""
        self.cached_windows = []
        self.last_enum_time = 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            缓存统计信息字典
        """
        current_time = time.time()
        cache_age = current_time - self.last_enum_time
        
        return {
            "cached_windows_count": len(self.cached_windows),
            "cache_age_seconds": cache_age,
            "cache_duration": self.cache_duration,
            "is_cache_valid": cache_age < self.cache_duration,
            "last_update_time": self.last_enum_time
        }