"""
Performance monitoring and debugging utilities for Streamlit applications.
Provides comprehensive instrumentation for timing, memory usage, and bottleneck identification.
"""

import time
import psutil
import functools
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
import pandas as pd
import streamlit as st
import json
import traceback
from contextlib import contextmanager
import sys
import gc
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import numpy as np

@dataclass
class PerformanceMetric:
    """Data class for storing performance metrics."""
    function_name: str
    start_time: float
    end_time: float
    duration: float
    memory_before: float
    memory_after: float
    memory_delta: float
    cpu_percent: float
    thread_id: int
    timestamp: str
    args_hash: str
    cache_hit: bool = False
    error: Optional[str] = None
    additional_data: Dict[str, Any] = None

class PerformanceMonitor:
    """
    Comprehensive performance monitoring system for Streamlit applications.
    Tracks timing, memory usage, cache performance, and identifies bottlenecks.
    """
    
    def __init__(self, max_metrics: int = 1000):
        """
        Initialize performance monitor.
        
        Args:
            max_metrics: Maximum number of metrics to store in memory
        """
        self.metrics: deque = deque(maxlen=max_metrics)
        self.function_stats: Dict[str, Dict] = defaultdict(lambda: {
            'call_count': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'total_memory_delta': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'error_count': 0
        })
        self.session_start_time = time.time()
        self.session_start_memory = self._get_memory_usage()
        self.lock = threading.Lock()
        
        # Streamlit-specific monitoring
        self.rerun_count = 0
        self.widget_render_times: Dict[str, List[float]] = defaultdict(list)
        self.cache_performance: Dict[str, Dict] = defaultdict(lambda: {
            'hits': 0,
            'misses': 0,
            'total_time_saved': 0.0
        })
        
        # Database query tracking
        self.db_queries: List[Dict] = []
        self.slow_queries_threshold = 5.0  # seconds
        
        # Component render tracking
        self.component_render_times: Dict[str, List[float]] = defaultdict(list)
        
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def _get_cpu_percent(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return 0.0
    
    def _hash_args(self, args: tuple, kwargs: dict) -> str:
        """Create hash of function arguments for cache tracking."""
        try:
            args_str = str(args) + str(sorted(kwargs.items()))
            return str(hash(args_str))
        except Exception:
            return "unhashable"
    
    def timing_decorator(self, function_name: Optional[str] = None, 
                        track_memory: bool = True,
                        track_cache: bool = False):
        """
        Decorator for timing function execution and tracking performance metrics.
        
        Args:
            function_name: Custom name for the function (defaults to actual function name)
            track_memory: Whether to track memory usage
            track_cache: Whether to track cache performance
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                name = function_name or f"{func.__module__}.{func.__name__}"
                
                # Pre-execution metrics
                start_time = time.time()
                memory_before = self._get_memory_usage() if track_memory else 0.0
                cpu_percent = self._get_cpu_percent()
                args_hash = self._hash_args(args, kwargs) if track_cache else ""
                
                error = None
                result = None
                cache_hit = False
                
                try:
                    # Check if this is a cached function call
                    if track_cache and hasattr(func, '_cached_result'):
                        cache_hit = True
                        self.cache_performance[name]['hits'] += 1
                    
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    if not cache_hit and track_cache:
                        self.cache_performance[name]['misses'] += 1
                    
                except Exception as e:
                    error = str(e)
                    self.function_stats[name]['error_count'] += 1
                    raise
                
                finally:
                    # Post-execution metrics
                    end_time = time.time()
                    duration = end_time - start_time
                    memory_after = self._get_memory_usage() if track_memory else 0.0
                    memory_delta = memory_after - memory_before
                    
                    # Create metric record
                    metric = PerformanceMetric(
                        function_name=name,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        memory_before=memory_before,
                        memory_after=memory_after,
                        memory_delta=memory_delta,
                        cpu_percent=cpu_percent,
                        thread_id=threading.get_ident(),
                        timestamp=datetime.now().isoformat(),
                        args_hash=args_hash,
                        cache_hit=cache_hit,
                        error=error
                    )
                    
                    # Store metric
                    with self.lock:
                        self.metrics.append(metric)
                        self._update_function_stats(name, metric)
                    
                    # Log slow operations
                    if duration > 1.0:  # Log operations taking more than 1 second
                        self._log_slow_operation(name, duration, memory_delta)
                
                return result
            
            return wrapper
        return decorator
    
    def _update_function_stats(self, name: str, metric: PerformanceMetric):
        """Update aggregated function statistics."""
        stats = self.function_stats[name]
        stats['call_count'] += 1
        stats['total_time'] += metric.duration
        stats['avg_time'] = stats['total_time'] / stats['call_count']
        stats['min_time'] = min(stats['min_time'], metric.duration)
        stats['max_time'] = max(stats['max_time'], metric.duration)
        stats['total_memory_delta'] += metric.memory_delta
        
        if metric.cache_hit:
            stats['cache_hits'] += 1
        else:
            stats['cache_misses'] += 1
    
    def _log_slow_operation(self, name: str, duration: float, memory_delta: float):
        """Log slow operations for analysis."""
        if 'slow_operations' not in st.session_state:
            st.session_state.slow_operations = []
        
        st.session_state.slow_operations.append({
            'function': name,
            'duration': duration,
            'memory_delta': memory_delta,
            'timestamp': datetime.now().isoformat()
        })
    
    @contextmanager
    def measure_component(self, component_name: str):
        """
        Context manager for measuring component render times.
        
        Args:
            component_name: Name of the component being measured
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.component_render_times[component_name].append(duration)
    
    def track_database_query(self, query: str, duration: float, 
                           row_count: Optional[int] = None,
                           error: Optional[str] = None):
        """
        Track database query performance.
        
        Args:
            query: SQL query (truncated for privacy)
            duration: Query execution time
            row_count: Number of rows returned
            error: Error message if query failed
        """
        query_info = {
            'query_hash': str(hash(query)),
            'query_preview': query[:100] + "..." if len(query) > 100 else query,
            'duration': duration,
            'row_count': row_count,
            'timestamp': datetime.now().isoformat(),
            'error': error,
            'is_slow': duration > self.slow_queries_threshold
        }
        
        self.db_queries.append(query_info)
        
        # Keep only recent queries
        if len(self.db_queries) > 100:
            self.db_queries = self.db_queries[-100:]
    
    def track_streamlit_rerun(self):
        """Track Streamlit app reruns."""
        self.rerun_count += 1
        
        if 'rerun_timestamps' not in st.session_state:
            st.session_state.rerun_timestamps = []
        
        st.session_state.rerun_timestamps.append(datetime.now().isoformat())
        
        # Keep only recent reruns
        if len(st.session_state.rerun_timestamps) > 50:
            st.session_state.rerun_timestamps = st.session_state.rerun_timestamps[-50:]
    
    def track_cache_performance(self, cache_name: str, hit: bool, time_saved: float = 0.0):
        """
        Track cache hit/miss performance.
        
        Args:
            cache_name: Name of the cache
            hit: Whether it was a cache hit
            time_saved: Time saved by cache hit
        """
        cache_stats = self.cache_performance[cache_name]
        
        if hit:
            cache_stats['hits'] += 1
            cache_stats['total_time_saved'] += time_saved
        else:
            cache_stats['misses'] += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        with self.lock:
            current_time = time.time()
            session_duration = current_time - self.session_start_time
            current_memory = self._get_memory_usage()
            memory_growth = current_memory - self.session_start_memory
            
            # Calculate overall statistics
            total_function_calls = sum(stats['call_count'] for stats in self.function_stats.values())
            total_execution_time = sum(stats['total_time'] for stats in self.function_stats.values())
            
            # Find bottlenecks
            bottlenecks = sorted(
                [(name, stats) for name, stats in self.function_stats.items()],
                key=lambda x: x[1]['total_time'],
                reverse=True
            )[:10]
            
            # Cache performance summary
            cache_summary = {}
            for cache_name, stats in self.cache_performance.items():
                total_requests = stats['hits'] + stats['misses']
                hit_rate = (stats['hits'] / total_requests * 100) if total_requests > 0 else 0
                cache_summary[cache_name] = {
                    'hit_rate': hit_rate,
                    'total_requests': total_requests,
                    'time_saved': stats['total_time_saved']
                }
            
            # Database query summary
            slow_queries = [q for q in self.db_queries if q['is_slow']]
            avg_query_time = np.mean([q['duration'] for q in self.db_queries]) if self.db_queries else 0
            
            return {
                'session_duration': session_duration,
                'memory_usage': {
                    'current': current_memory,
                    'growth': memory_growth,
                    'peak': max([m.memory_after for m in self.metrics], default=current_memory)
                },
                'function_performance': {
                    'total_calls': total_function_calls,
                    'total_execution_time': total_execution_time,
                    'avg_execution_time': total_execution_time / total_function_calls if total_function_calls > 0 else 0
                },
                'bottlenecks': [
                    {
                        'function': name,
                        'total_time': stats['total_time'],
                        'avg_time': stats['avg_time'],
                        'call_count': stats['call_count'],
                        'percentage_of_total': (stats['total_time'] / total_execution_time * 100) if total_execution_time > 0 else 0
                    }
                    for name, stats in bottlenecks
                ],
                'cache_performance': cache_summary,
                'database_queries': {
                    'total_queries': len(self.db_queries),
                    'slow_queries': len(slow_queries),
                    'avg_query_time': avg_query_time,
                    'slowest_query': max(self.db_queries, key=lambda x: x['duration'], default={}).get('duration', 0)
                },
                'streamlit_metrics': {
                    'rerun_count': self.rerun_count,
                    'component_render_times': {
                        name: {
                            'avg': np.mean(times),
                            'max': np.max(times),
                            'count': len(times)
                        }
                        for name, times in self.component_render_times.items()
                    }
                }
            }
    
    def get_detailed_metrics_df(self) -> pd.DataFrame:
        """Get detailed metrics as DataFrame for analysis."""
        with self.lock:
            if not self.metrics:
                return pd.DataFrame()
            
            metrics_data = [asdict(metric) for metric in self.metrics]
            df = pd.DataFrame(metrics_data)
            
            # Add derived columns
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['duration_ms'] = df['duration'] * 1000
                df['memory_delta_mb'] = df['memory_delta']
                df['is_slow'] = df['duration'] > 1.0
                df['efficiency_score'] = df.apply(
                    lambda row: row['duration'] / max(row['memory_delta'], 0.1), axis=1
                )
            
            return df
    
    def export_performance_report(self) -> Dict[str, Any]:
        """Export comprehensive performance report."""
        summary = self.get_performance_summary()
        metrics_df = self.get_detailed_metrics_df()
        
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'summary': summary,
            'function_details': dict(self.function_stats),
            'recent_metrics': metrics_df.tail(50).to_dict('records') if not metrics_df.empty else [],
            'slow_operations': getattr(st.session_state, 'slow_operations', []),
            'database_queries': self.db_queries[-20:],  # Last 20 queries
            'recommendations': self._generate_recommendations(summary)
        }
        
        return report
    
    def _generate_recommendations(self, summary: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        # Memory recommendations
        if summary['memory_usage']['growth'] > 100:  # >100MB growth
            recommendations.append({
                'category': 'Memory',
                'priority': 'High',
                'issue': f"High memory growth: {summary['memory_usage']['growth']:.1f}MB",
                'recommendation': 'Consider implementing data pagination or clearing unused DataFrames'
            })
        
        # Cache recommendations
        for cache_name, cache_stats in summary['cache_performance'].items():
            if cache_stats['hit_rate'] < 50 and cache_stats['total_requests'] > 10:
                recommendations.append({
                    'category': 'Caching',
                    'priority': 'Medium',
                    'issue': f"Low cache hit rate for {cache_name}: {cache_stats['hit_rate']:.1f}%",
                    'recommendation': 'Review cache TTL settings or cache key strategy'
                })
        
        # Database recommendations
        if summary['database_queries']['slow_queries'] > 0:
            recommendations.append({
                'category': 'Database',
                'priority': 'High',
                'issue': f"{summary['database_queries']['slow_queries']} slow queries detected",
                'recommendation': 'Optimize slow queries or implement query result caching'
            })
        
        # Function performance recommendations
        bottlenecks = summary['bottlenecks'][:3]  # Top 3 bottlenecks
        for bottleneck in bottlenecks:
            if bottleneck['percentage_of_total'] > 20:  # >20% of total execution time
                recommendations.append({
                    'category': 'Performance',
                    'priority': 'High',
                    'issue': f"{bottleneck['function']} consumes {bottleneck['percentage_of_total']:.1f}% of execution time",
                    'recommendation': 'Consider optimizing this function or implementing caching'
                })
        
        # Streamlit-specific recommendations
        if summary['streamlit_metrics']['rerun_count'] > 20:
            recommendations.append({
                'category': 'Streamlit',
                'priority': 'Medium',
                'issue': f"High rerun count: {summary['streamlit_metrics']['rerun_count']}",
                'recommendation': 'Review widget interactions and consider using st.form to reduce reruns'
            })
        
        return recommendations
    
    def display_performance_dashboard(self):
        """Display performance monitoring dashboard in Streamlit."""
        st.subheader("🔍 Performance Monitoring Dashboard")
        
        summary = self.get_performance_summary()
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Session Duration",
                f"{summary['session_duration']:.1f}s",
                help="Total time since app started"
            )
        
        with col2:
            st.metric(
                "Memory Usage",
                f"{summary['memory_usage']['current']:.1f}MB",
                delta=f"{summary['memory_usage']['growth']:+.1f}MB",
                help="Current memory usage and growth since start"
            )
        
        with col3:
            st.metric(
                "Function Calls",
                f"{summary['function_performance']['total_calls']:,}",
                help="Total number of function calls tracked"
            )
        
        with col4:
            st.metric(
                "Avg Response Time",
                f"{summary['function_performance']['avg_execution_time']*1000:.1f}ms",
                help="Average function execution time"
            )
        
        # Performance bottlenecks
        if summary['bottlenecks']:
            st.subheader("⚡ Performance Bottlenecks")
            bottleneck_data = []
            for bottleneck in summary['bottlenecks'][:10]:
                bottleneck_data.append({
                    'Function': bottleneck['function'].split('.')[-1],  # Just function name
                    'Total Time (s)': f"{bottleneck['total_time']:.3f}",
                    'Avg Time (ms)': f"{bottleneck['avg_time']*1000:.1f}",
                    'Calls': bottleneck['call_count'],
                    '% of Total': f"{bottleneck['percentage_of_total']:.1f}%"
                })
            
            st.dataframe(pd.DataFrame(bottleneck_data), use_container_width=True)
        
        # Cache performance
        if summary['cache_performance']:
            st.subheader("💾 Cache Performance")
            cache_data = []
            for cache_name, stats in summary['cache_performance'].items():
                cache_data.append({
                    'Cache': cache_name.split('.')[-1],
                    'Hit Rate': f"{stats['hit_rate']:.1f}%",
                    'Total Requests': stats['total_requests'],
                    'Time Saved (s)': f"{stats['time_saved']:.3f}"
                })
            
            st.dataframe(pd.DataFrame(cache_data), use_container_width=True)
        
        # Database performance
        if summary['database_queries']['total_queries'] > 0:
            st.subheader("🗄️ Database Performance")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Queries", summary['database_queries']['total_queries'])
            with col2:
                st.metric("Slow Queries", summary['database_queries']['slow_queries'])
            with col3:
                st.metric("Avg Query Time", f"{summary['database_queries']['avg_query_time']:.2f}s")
        
        # Recommendations
        recommendations = self._generate_recommendations(summary)
        if recommendations:
            st.subheader("💡 Optimization Recommendations")
            for rec in recommendations:
                priority_color = {
                    'High': '🔴',
                    'Medium': '🟡',
                    'Low': '🟢'
                }.get(rec['priority'], '⚪')
                
                st.write(f"{priority_color} **{rec['category']}** - {rec['issue']}")
                st.write(f"   💡 {rec['recommendation']}")
                st.write("")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Convenience decorators
def time_it(func_name: str = None):
    """Simple timing decorator."""
    return performance_monitor.timing_decorator(func_name, track_memory=True, track_cache=False)

def monitor_cache(func_name: str = None):
    """Decorator for monitoring cached functions."""
    return performance_monitor.timing_decorator(func_name, track_memory=True, track_cache=True)

def monitor_db_operation(func_name: str = None):
    """Decorator for monitoring database operations."""
    return performance_monitor.timing_decorator(func_name, track_memory=True, track_cache=False)

# Context managers
@contextmanager
def measure_time(operation_name: str):
    """Context manager for measuring operation time."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        if 'operation_times' not in st.session_state:
            st.session_state.operation_times = {}
        
        if operation_name not in st.session_state.operation_times:
            st.session_state.operation_times[operation_name] = []
        
        st.session_state.operation_times[operation_name].append(duration)

@contextmanager
def measure_memory(operation_name: str):
    """Context manager for measuring memory usage."""
    process = psutil.Process()
    memory_before = process.memory_info().rss / 1024 / 1024
    
    try:
        yield
    finally:
        memory_after = process.memory_info().rss / 1024 / 1024
        memory_delta = memory_after - memory_before
        
        if 'memory_usage' not in st.session_state:
            st.session_state.memory_usage = {}
        
        if operation_name not in st.session_state.memory_usage:
            st.session_state.memory_usage[operation_name] = []
        
        st.session_state.memory_usage[operation_name].append({
            'before': memory_before,
            'after': memory_after,
            'delta': memory_delta,
            'timestamp': datetime.now().isoformat()
        })
