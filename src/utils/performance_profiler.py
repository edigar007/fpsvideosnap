"""
Performance profiler for tracking and analyzing processing time of each step.
"""
import time
from typing import Dict, List, Optional
from collections import defaultdict
import json
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceProfiler:
    """
    记录和分析各个处理步骤的耗时统计
    """
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.timings = defaultdict(list)  # {step_name: [duration1, duration2, ...]}
        self.current_steps = {}  # {step_name: start_time}
        self.counters = defaultdict(int)  # {step_name: count}
        
    def start(self, step_name: str):
        """开始计时某个步骤"""
        if not self.enabled:
            return
        self.current_steps[step_name] = time.time()
    
    def end(self, step_name: str):
        """结束计时某个步骤"""
        if not self.enabled:
            return
        
        if step_name not in self.current_steps:
            logger.warning(f"Performance profiler: step '{step_name}' not started")
            return
        
        duration = time.time() - self.current_steps[step_name]
        self.timings[step_name].append(duration)
        self.counters[step_name] += 1
        del self.current_steps[step_name]
        return duration
    
    def record(self, step_name: str, duration: float):
        """直接记录一个步骤的耗时"""
        if not self.enabled:
            return
        self.timings[step_name].append(duration)
        self.counters[step_name] += 1
    
    def get_stats(self, step_name: str) -> Dict:
        """获取某个步骤的统计信息"""
        if step_name not in self.timings:
            return {}
        
        durations = self.timings[step_name]
        return {
            'count': len(durations),
            'total': sum(durations),
            'avg': sum(durations) / len(durations),
            'min': min(durations),
            'max': max(durations),
            'step_name': step_name
        }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有步骤的统计信息"""
        stats = {}
        for step_name in self.timings.keys():
            stats[step_name] = self.get_stats(step_name)
        return stats
    
    def print_summary(self, use_print: bool = False):
        """打印性能统计摘要
        
        Args:
            use_print: 如果为 True，使用 print() 而非 logger.info()
        """
        if not self.enabled or not self.timings:
            return
        
        output = print if use_print else logger.info
        
        output("\n" + "="*80)
        output("[bold cyan]性能分析报告 (Performance Profile)[/bold cyan]" if not use_print else "性能分析报告 (Performance Profile)")
        output("="*80)
        
        all_stats = self.get_all_stats()
        
        # 按总耗时排序
        sorted_stats = sorted(all_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        total_time = sum(s['total'] for s in all_stats.values())
        
        output(f"\n{'步骤名称':<40} {'调用次数':>10} {'总耗时(s)':>12} {'平均(s)':>10} {'占比':>8}")
        output("-"*80)
        
        for step_name, stats in sorted_stats:
            percentage = (stats['total'] / total_time * 100) if total_time > 0 else 0
            output(
                f"{step_name:<40} {stats['count']:>10} "
                f"{stats['total']:>12.3f} {stats['avg']:>10.3f} {percentage:>7.1f}%"
            )
        
        output("-"*80)
        output(f"{'总计':<40} {sum(s['count'] for s in all_stats.values()):>10} {total_time:>12.3f}")
        output("="*80 + "\n")
    
    def save_to_file(self, filepath: str):
        """保存统计信息到JSON文件"""
        if not self.enabled:
            return
        
        stats = self.get_all_stats()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Performance profile saved to: {filepath}")
    
    def reset(self):
        """重置所有统计信息"""
        self.timings.clear()
        self.current_steps.clear()
        self.counters.clear()


# 全局性能分析器实例
_global_profiler = PerformanceProfiler(enabled=True)


def get_profiler() -> PerformanceProfiler:
    """获取全局性能分析器"""
    return _global_profiler


def enable_profiler():
    """启用性能分析"""
    _global_profiler.enabled = True


def disable_profiler():
    """禁用性能分析"""
    _global_profiler.enabled = False


class ProfilerContext:
    """性能分析上下文管理器，便于使用 with 语句"""
    def __init__(self, step_name: str, profiler: Optional[PerformanceProfiler] = None):
        self.step_name = step_name
        self.profiler = profiler or get_profiler()
    
    def __enter__(self):
        self.profiler.start(self.step_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.profiler.end(self.step_name)
