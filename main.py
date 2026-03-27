import asyncio
import sys
from threading import Thread, Event
import logging.config

from engine import Engine
from spiders import PixivSpiders
from data import EngineStatus
from utils import Console, ConfigManager


class CLIManager:
    """CLI命令管理器"""

    def __init__(self, engine: Engine, console: Console, exit_event: Event):
        self.engine = engine
        self.console = console
        self.should_exit = False
        self.exit_event = exit_event  # 用于通知主循环退出

    def print_welcome(self):
        """打印欢迎信息"""
        welcome = f"""
╔════════════════════════════════════════════════════════════╗
║{"🎉 Welcome to Pixiv Crawler CLI":^59}║
╠════════════════════════════════════════════════════════════╣
║  {"Enter 'help' show all commands":<58}║
║  {"Enter 'spider' list available spiders":<58}║
║  {"Enter 'start' run default spider":<58}║
║  {"Enter 'exit' to exit the program":<58}║
╚════════════════════════════════════════════════════════════╝
        """
        self.console.print(welcome)

    def print_help(self):
        """打印帮助信息"""
        help_text = f"""
╔════════════════════════════════════════════════════════════╗
║                 Pixiv Crawler CLI Commands                 ║
╠════════════════════════════════════════════════════════════╣
║  start        - {"Run default spider (workinfo)":<43}║
║  spider       - {"List available spiders":<43}║
║  run <name>   - {"Run the specified crawler":<43}║
║  pause        - {"Pause crawler operation":<43}║
║  resume       - {"Restore crawler operation":<43}║
║  status       - {"Show current status and statistics.":<43}║
║  help         - {"Show this help information":<43}║
║  clear        - {"Clear console output":<43}║
║  exit/quit/q  - {"Exit the program":<43}║
╚════════════════════════════════════════════════════════════╝
        """
        self.console.print(help_text)

    def display_status(self):
        """显示运行状态"""
        status_info = self.engine.get_status()
        status_info = f"""
╔════════════════════════════════════════════════════════════╗
║                Engine Status & Statistics                  ║
╠════════════════════════════════════════════════════════════╣
║ Status             : {status_info["status"].upper():<37} ║
║ Running Time       : {status_info["running_time"]:<37} ║
║ Current Spider     : {status_info["running_spider"]if status_info["running_spider"] else "None":<37} ║
║ Active Workers     : {status_info["worker_count"]:<37} ║
║ Queue Size         : {status_info["queue_size"]:<37} ║
║ Finished Requests  : {status_info["finished_requests"]:<37} ║
╚════════════════════════════════════════════════════════════╝
        """
        self.console.print(status_info)

    def list_spiders(self):
        """列出所有可用爬虫"""
        if not self.engine._spider_collections:
            self.console.print("No registered crawlers")
            return

        self.console.print("\nList of available crawlers:")
        self.console.print("─" * 50)
        for spider_collection in self.engine._spider_collections:
            self.console.print(f"  Spider Collection: {spider_collection.name}")
            for msg in spider_collection.list_spider_with_status():
                self.console.print(msg)

        self.console.print("─" * 50 + "\n")

    def execute_command(self, command: str):
        """执行CLI命令"""
        parts = command.strip().lower().split()
        if not parts:
            return

        cmd = parts[0]

        if cmd == "help":
            self.print_help()

        elif cmd == "status":
            self.display_status()

        elif cmd == "spider":
            self.list_spiders()

        elif cmd == "start":
            # 启动默认爬虫
            if self.engine.running_spider:
                print("A crawler is already running.")
                return
            self.engine.run_spider("bookmarkwork")
            self.engine.resume()  # 确保引擎处于运行状态
            print("The default crawler (bookmarkwork) start.")

        elif cmd == "pause":
            if self.engine.status == EngineStatus.PAUSE:
                print("The crawler has already been paused.")
            else:
                self.engine.pause()
                # print("✅ 爬虫已暂停")

        elif cmd == "resume":
            if self.engine.status == EngineStatus.RUNNING:
                print("The crawler is already running.")
            else:
                self.engine.resume()
                # print("✅ 爬虫已恢复运行")

        elif cmd == "run":
            if len(parts) < 2:
                print("Usage: run <spider_name>")
                self.list_spiders()
                return
            spider_name = parts[1]
            if self.engine.running_spider:
                self.engine.pause()
                self.engine.running_spider = None
            success = self.engine.run_spider(spider_name)
            if success:
                print(f"Web crawler started: {spider_name}")

        elif cmd == "clear":
            self.console.clear()

        elif cmd in ["exit", "quit", "q"]:
            print("Closing the program...")
            self.should_exit = True
            self.exit_event.set()  # 通知主循环退出

        else:
            print(f"Unknown command: {cmd}, type 'help' to view the command list.")

    def input_loop(self):
        """后台输入循环 - 独立线程中运行"""
        self.console.print_end("crawler> ")
        command = ""
        try:
            while not self.should_exit and self.engine.status != EngineStatus.STOP:
                try:
                    # 获取用户输入
                    command = input("crawler> ").strip()
                    if command:
                        self.execute_command(command)
                except EOFError:
                    # 处理重定向或管道输入的情况
                    self.should_exit = True
                    self.exit_event.set()
                    break
                except KeyboardInterrupt:
                    # print("\n👋 收到中断信号，正在关闭...")
                    self.should_exit = True
                    self.exit_event.set()
                    break
        except Exception as e:
            print(f"Input loop error: {e}")
            self.should_exit = True
            self.exit_event.set()


async def main():
    """主程序入口"""

    exit_event = Event()
    console = Console()
    config = ConfigManager(config_file_path="config.json")
    logging.config.dictConfig(config.require("logger_config"))

    console.print("\n" + "=" * 60)
    console.print(f"{"Crawler - Starting...":^60}")
    console.print("=" * 60)

    try:
        console.print("Initializing the crawler engine...")
        engine = Engine(config)

        cli_manager = CLIManager(engine, console, exit_event)

        console.print("Start engine...")
        await engine.start()

        console.print("Registering crawler...")
        engine.add_spider_collection(
            PixivSpiders(engine.logger),
            config=engine.config,
            dataservice=engine.dataservice,
        )

        # 启动CLI线程 - daemon=False 让程序等待线程完成
        cli_thread = Thread(target=cli_manager.input_loop, daemon=False)
        cli_thread.start()

        cli_manager.print_welcome()
        console.print("CLI ready, please enter the command (type 'help' to view help).")
        console.print("\n")

        # Main loop - Check exit event
        try:
            will_pause_time = 0
            while not exit_event.is_set():
                # console.print("=====================Test=====================")
                # If there is a running crawler, execute the engine loop.
                if engine.running_spider is not None:
                    try:
                        # Use `wait_for` to add a timeout to avoid prolonged blocking.
                        will_pause_time = await asyncio.wait_for(
                            engine.loop(will_pause_time),
                            timeout=3,
                        )

                    except asyncio.TimeoutError:
                        # The timeout is normal; continue checking the exit event.
                        pass
                else:
                    # When no crawler is running, briefly hibernate to avoid busy polling.
                    await asyncio.sleep(0.5)

                # Check if the CLI thread is still alive.
                if not cli_thread.is_alive() and exit_event.is_set():
                    break

        except KeyboardInterrupt:
            console.print("\nReceived KeyboardInterrupt signal")
            exit_event.set()

        # Wait for the CLI thread to finish (maximum 5 seconds).
        console.print("\nClosing...")
        exit_event.set()
        cli_thread.join(timeout=5)

        await engine.shutdown()
        console.print("The crawler has been safely shut down.")

        # Showing final statistics
        cli_manager.display_status()

        console.print("\nThe program has exited normally.\n")

    except Exception as e:
        print(f"Unexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"\nProgram crash: {e}")
        sys.exit(1)
