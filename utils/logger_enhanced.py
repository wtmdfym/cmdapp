"""
增强的日志模块
提供更完整的日志功能，包括性能指标记录、日志分析等
"""

import logging
from typing import Any


class EnhancedLogger(logging.Logger):
    """增强的日志系统，支持指标记录和分析"""

    def __init__(self, logger_name: str = "crawler"):
        """
        初始化增强日志系统

        Args:
            logger_config: 日志配置字典
            logger_name: 日志器名称
        """

        self.name = logger_name

        # 性能指标存储
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_items_processed": 0,
            "task_timings": [],  # 记录所有任务耗时
        }

        self.info("✅ 增强日志系统已初始化")

    # # 基础日志方法
    # def debug(self, msg: str) -> None:
    #     """Debug级别日志"""
    #     self.logger.debug(msg)

    # def info(self, msg: str) -> None:
    #     """Info级别日志"""
    #     self.logger.info(msg)

    # def warning(self, msg: str) -> None:
    #     """Warning级别日志"""
    #     self.logger.warning(msg)

    # def error(self, msg: str, exception: Optional[Exception] = None) -> None:
    #     """Error级别日志"""
    #     if exception:
    #         self.logger.error(msg, exc_info=exception)
    #     else:
    #         self.logger.error(msg)

    # def critical(self, msg: str, exception: Optional[Exception] = None) -> None:
    #     """Critical级别日志"""
    #     if exception:
    #         self.logger.critical(msg, exc_info=exception)
    #     else:
    #         self.logger.critical(msg)

    # 性能指标记录
    def record_request(
        self, success: bool, response_time: float, status_code: int = 200, url: str = ""
    ) -> None:
        """
        记录HTTP请求指标

        Args:
            success: 请求是否成功
            response_time: 响应时间（秒）
            status_code: HTTP状态码
            url: 请求URL
        """
        self.metrics["total_requests"] += 1

        if success:
            self.metrics["successful_requests"] += 1
            self.debug(f"✅ 请求成功 [{status_code}] {url} ({response_time:.2f}s)")
        else:
            self.metrics["failed_requests"] += 1
            self.warning(f"❌ 请求失败 [{status_code}] {url} ({response_time:.2f}s)")

        self.metrics["task_timings"].append(response_time)

    def record_items_processed(self, count: int, pipeline_name: str = "") -> None:
        """
        记录处理的数据项

        Args:
            count: 处理的数据项数量
            pipeline_name: 管道名称
        """
        self.metrics["total_items_processed"] += count
        self.debug(f"📦 处理数据项: {count} [{pipeline_name}]")

    def record_task_execution(
        self, task_name: str, duration: float, success: bool, error_msg: str = ""
    ) -> None:
        """
        记录任务执行情况

        Args:
            task_name: 任务名称
            duration: 执行时长（秒）
            success: 是否成功
            error_msg: 错误信息
        """
        status_emoji = "✅" if success else "❌"
        status_text = "成功" if success else "失败"

        msg = f"{status_emoji} 任务 '{task_name}' {status_text} ({duration:.2f}s)"
        if error_msg:
            msg += f" - {error_msg}"

        if success:
            self.info(msg)
        else:
            self.error(msg)

    # 分析方法
    def get_statistics(self) -> dict[str, Any]:
        """
        获取性能统计信息

        Returns:
            包含各项统计数据的字典
        """
        timings = self.metrics["task_timings"]
        total_requests = self.metrics["total_requests"]

        if not timings:
            return {
                "total_requests": total_requests,
                "successful_requests": self.metrics["successful_requests"],
                "failed_requests": self.metrics["failed_requests"],
                "success_rate": 0.0,
                "total_items_processed": self.metrics["total_items_processed"],
                "average_response_time": 0.0,
                "min_response_time": 0.0,
                "max_response_time": 0.0,
                "requests_per_second": 0.0,
            }

        sorted_timings = sorted(timings)

        success_rate = (
            self.metrics["successful_requests"] / total_requests * 100
            if total_requests > 0
            else 0
        )

        return {
            "total_requests": total_requests,
            "successful_requests": self.metrics["successful_requests"],
            "failed_requests": self.metrics["failed_requests"],
            "success_rate": f"{success_rate:.1f}%",
            "total_items_processed": self.metrics["total_items_processed"],
            "average_response_time": f"{sum(timings) / len(timings):.2f}s",
            "min_response_time": f"{sorted_timings[0]:.2f}s",
            "max_response_time": f"{sorted_timings[-1]:.2f}s",
            "p50_response_time": f"{sorted_timings[len(sorted_timings)//2]:.2f}s",
            "p95_response_time": f"{sorted_timings[int(len(sorted_timings)*0.95)]:.2f}s",
            "p99_response_time": f"{sorted_timings[int(len(sorted_timings)*0.99)]:.2f}s",
            "requests_per_second": f"{total_requests / max(sum(timings), 0.001):.2f}",
        }

    def print_statistics(self) -> None:
        """打印性能统计信息"""
        stats = self.get_statistics()

        print("\n" + "=" * 60)
        print("  性能统计信息")
        print("=" * 60)
        for key, value in stats.items():
            print(f"  {key:<25}: {value}")
        print("=" * 60 + "\n")

    def reset_metrics(self) -> None:
        """重置所有指标"""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_items_processed": 0,
            "task_timings": [],
        }
        self.info("📊 指标已重置")


class LogFilter(logging.Filter):
    """自定义日志过滤器"""

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤日志记录"""
        # 可以在这里添加自定义过滤逻辑
        return True


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
        "RESET": "\033[0m",  # 重置
    }

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            )
        return super().format(record)


import sys


class Console:
    def __init__(self, keep_end: bool = True) -> None:
        self.keep_end = keep_end

        self.current_line = 0
        self.last_msg = ""
        self.end_msg = ""
        self.clear()

    def print(self, msg: str):
        print(msg)
        return
        if not (self.keep_end and self.end_msg):
            self.current_line += 1
            self.at(self.current_line, msg)

        self.at(self.current_line, msg, flush=False)
        self.current_line += 1
        self.at(self.current_line, self.end_msg)
        self.last_msg = msg

    def print_end(self, msg: str, clear_last: bool = True):
        print(msg)
        return
        self.end_msg = msg
        if clear_last and self.current_line == 0:
            self.current_line += 1
        self.at(self.current_line, msg)

    @staticmethod
    def at(line, text="", flush: bool = True):
        """在指定行输出/更新内容"""
        sys.stdout.write(f"\033[{line};1H\033[2K{text}")
        if flush:
            sys.stdout.flush()

    @staticmethod
    def delete(line):
        """删除指定行内容"""
        Console.at(line, "")

    @staticmethod
    def clear():
        """清屏"""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    @staticmethod
    def up(n=1):
        """光标上移n行"""
        sys.stdout.write(f"\033[{n}A")
        sys.stdout.flush()
