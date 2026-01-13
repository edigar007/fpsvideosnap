"""
测试性能分析器功能
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from src.utils.performance_profiler import get_profiler, ProfilerContext
import time

def test_performance_profiler():
    """测试性能分析器"""
    profiler = get_profiler()
    profiler.reset()  # 重置以确保干净的状态
    
    print("测试性能分析器...")
    
    # 测试 1: 使用 start/end 方法
    profiler.start('test_step1')
    time.sleep(0.1)
    profiler.end('test_step1')
    
    # 测试 2: 使用 with 语句
    with ProfilerContext('test_step2'):
        time.sleep(0.2)
    
    # 测试 3: 多次调用同一个步骤
    for i in range(5):
        profiler.start('test_loop')
        time.sleep(0.05)
        profiler.end('test_loop')
    
    # 测试 4: 嵌套的步骤
    profiler.start('test_parent')
    with ProfilerContext('test_child1'):
        time.sleep(0.05)
    with ProfilerContext('test_child2'):
        time.sleep(0.05)
    profiler.end('test_parent')
    
    # 打印统计信息
    print("\n统计信息:")
    stats = profiler.get_all_stats()
    for step_name, stat in stats.items():
        print(f"{step_name}: count={stat['count']}, avg={stat['avg']:.4f}s, total={stat['total']:.4f}s")
    
    # 打印摘要
    profiler.print_summary(use_print=True)
    
    # 保存到文件
    profiler.save_to_file('temp/test_performance.json')
    print("\n性能数据已保存到 temp/test_performance.json")

if __name__ == '__main__':
    test_performance_profiler()
