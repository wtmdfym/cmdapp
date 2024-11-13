# -*-coding:utf-8-*-
import sys
import os
import pymongo
import asyncio
import logging
import sys
from motor import motor_asyncio
from PyQt6.QtCore import (
    QCoreApplication,
    QMetaObject,
    QRect,
    Qt,
)
from PyQt6.QtGui import QImageReader, QFont     # , QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    # QTabBar,
    QWidget,
    # QSystemTrayIcon,
)

# from GUI.widgets import
# , ImageTab, OriginalImageTab
from GUIcmd.tabs import MainTab, SearchTab, TagsTab, UserTab, ConfigTab, ImageTab, OriginalImageTab
from Tool import MyLogging, ConfigSetter


class MainWindow(QMainWindow):
    def __init__(self, scaleRate):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle("Pixiv Crawler")
        # 初始化设置信息
        self.default_config_save_path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "default_config.json"
        )
        self.config_save_path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "config.json"
        )
        self.config_dict = ConfigSetter.get_config(
            self.config_save_path, self.default_config_save_path)
        client = pymongo.MongoClient("localhost", 27017)
        self.db = client["pixiv"]
        self.backup_collection = client["backup"]["backup of pixiv infos"]
        # PyQt6获取屏幕参数
        screen = QApplication.primaryScreen().size()
        self.default_width = 1260
        self.default_height = 768
        # 设置最小大小
        self.setMinimumSize(self.default_width, self.default_height)
        # self.width_ratio = 1
        # self.height_ratio = 1
        self.default_tab_width = 1240
        self.default_tab_height = 732
        # 居中显示
        width = int(self.default_width * scaleRate)
        height = int(self.default_height * scaleRate)
        self.setGeometry(
            QRect(
                (screen.width() - width) // 2,
                (screen.height() - height) // 2,
                width,
                height,
            )
        )
        # 设置图片最大大小
        QImageReader.setAllocationLimit(256)
        self.setupUi()

    def setupUi(self):
        # Tab数量
        self.tab_count = 5
        # 初始化tabWidget
        self.centralwidget = QWidget(parent=self)
        self.centralwidget.setObjectName("centralwidget")
        self.tabWidget = QTabWidget(parent=self.centralwidget)
        self.tabWidget.setGeometry(
            QRect(0, 0, self.default_tab_width, self.default_tab_height)
        )
        self.tabWidget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.tabWidget.setTabPosition(QTabWidget.TabPosition.North)
        self.tabWidget.setTabShape(QTabWidget.TabShape.Rounded)
        self.tabWidget.setDocumentMode(False)
        self.tabWidget.setObjectName("tabWidget")
        # 设置tab可关闭
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.tabCloseRequested.connect(self.close_tab)
        # self.tabWidget.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        # 初始化MainTab
        self.tab = MainTab(self, self.config_dict, self.config_save_path, loop,
                           asyncdb, asyncbackupcollection, logger)
        self.tab.setObjectName("MainTab")
        self.tabWidget.addTab(self.tab, "")
        # 初始化SearchTab
        self.tab_1 = SearchTab(
            self, self.config_dict["save_path"], logger, self.backup_collection,
            self.creat_image_tab, self.config_dict["use_thumbnail"])
        self.tab_1.setObjectName("SearchTab")
        self.tabWidget.addTab(self.tab_1, "")
        # 初始化TagsTab
        self.tab_2 = TagsTab(
            self,
            self.db,
            changetab=self.tabWidget.setCurrentIndex,
            settext=self.tab_1.searchEdit.setText,
        )
        self.tab_2.setObjectName("TagsTab")
        self.tabWidget.addTab(self.tab_2, "")
        # 初始化UserTab
        self.tab_3 = UserTab(
            self, logger, self.db, self.config_dict["save_path"], self.config_dict["use_thumbnail"])
        self.tab_3.setObjectName("UserTab")
        self.tabWidget.addTab(self.tab_3, "")
        # 初始化ConfigsTab
        self.tab_4 = ConfigTab(self, logger, self.config_dict,
                               self.config_save_path, self.db, self.reloadUI)
        self.tab_4.setObjectName("ConfigsTab")
        self.tabWidget.addTab(self.tab_4, "")
        # 设置主窗口
        self.setCentralWidget(self.centralwidget)
        # 设置菜单栏
        self.menubar = QMenuBar(parent=self)
        self.menubar.setGeometry(QRect(0, 0, 768, 22))
        self.menubar.setObjectName("menubar")
        self.menuHelp = QMenu(parent=self.menubar)
        self.menuHelp.setObjectName("menuHelp")
        self.setMenuBar(self.menubar)
        # 设置状态栏
        self.statusbar = QStatusBar(parent=self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menuHelp.menuAction())
        # 显示文字
        self.retranslateUi()
        self.tabWidget.setCurrentIndex(1)
        # self.statusbar.showMessage
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        # 显示翻译
        _translate = QCoreApplication.translate
        self.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.tab.retranslateUi()
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab), _translate(
                "MainWindow", "Main")
        )
        self.tab_1.retranslateUi()
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_1), _translate(
                "MainWindow", "Search")
        )
        self.tab_2.retranslateUi()
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_2), _translate(
                "MainWindow", "Tags")
        )
        self.tab_3.retranslateUi()
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_3), _translate(
                "MainWindow", "User")
        )
        self.tab_4.retranslateUi()
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_4), _translate(
                "MainWindow", "Settings")
        )
        self.menuHelp.setTitle(_translate("MainWindow", "Help"))

    def resizeEvent(self, a0) -> None:
        new_width = self.width()
        new_height = self.height()
        width_ratio = new_width / self.default_width
        height_ratio = new_height / self.default_height
        # if self.width_ratio != width_ratio or self.height_ratio != height_ratio:
        #    self.width_ratio = width_ratio
        #    self.height_ratio = height_ratio
        # self.tab.resize(int(self.tab.default_width*width_ratio), int(self.tab.default_height*height_ratio))
        self.tabWidget.resize(
            int(self.default_tab_width * width_ratio),
            int(self.default_tab_height * height_ratio),
        )
        self.tab.resize(
            int(self.tab.default_width * width_ratio),
            int(self.tab.default_height * height_ratio),
        )
        self.tab_1.resize(
            int(self.tab_1.default_width * width_ratio),
            int(self.tab_1.default_height * height_ratio),
        )
        self.tab_2.resize(
            int(self.tab_2.default_width * width_ratio),
            int(self.tab_2.default_height * height_ratio),
        )
        self.tab_3.resize(
            int(self.tab_3.default_width * width_ratio),
            int(self.tab_3.default_height * height_ratio),
        )
        self.tab_4.resize(
            int(self.tab_4.default_width * width_ratio),
            int(self.tab_4.default_height * height_ratio),
        )
        return super().resizeEvent(a0)

    def reloadUI(self):
        # 重新加载设置
        global config_dict, logger
        config_dict = ConfigSetter.get_config(
            self.config_save_path, self.default_config_save_path)
        """
        # 弹出提示框
        info_box = QMessageBox()
        info_box.setWindowTitle("Pixiv")     # QMessageBox标题
        info_box.setText("重新加载窗口")      # QMessageBox的提示文字
        info_box.setStandardButtons(
            QMessageBox.StandardButton.Ok)      # QMessageBox显示的按钮

        info_box.button(QMessageBox.StandardButton.Ok).animateClick()
        info_box.exec()    # 如果使用.show(),会导致QMessageBox框一闪而逝
        time.sleep(1)
        # self.timer = QTimer(self)  # 初始化一个定时器
        """
        # 重新加载窗口
        self.destroy(True, True)
        self.setupUi()

    def creat_image_tab(self, image_data: dict | tuple):
        # print(image_data)
        if isinstance(image_data, dict):
            id = image_data.get("id")
            if len(image_data.get("relative_path")) == 1:
                tab = OriginalImageTab(image_data)
                tab.open_image(
                    self.config_dict["save_path"]+image_data.get("relative_path")[0])
            else:
                tab = ImageTab(self, self.config_dict["save_path"], logger, image_data,
                                        self.creat_image_tab, self.config_dict["use_thumbnail"])
            index = self.tabWidget.insertTab(2, tab, str(id))
        else:
            id = image_data[0]
            img_path = image_data[1]
            tab = OriginalImageTab()   # image_data[2]
            tab.open_image(self.config_dict["save_path"]+img_path)
            index = self.tabWidget.insertTab(self.tab_count - 3, tab, str(id))
        self.tabWidget.setCurrentIndex(index)
        self.tab_count += 1
        # self.tabWidget.addTab(tab, str(id))

    def close_tab(self, index):
        if index <= 1 or index >= (self.tab_count - 3):
            return
        self.tabWidget.removeTab(index)
        self.tabWidget.setCurrentIndex(index - 1)
        self.tab_count -= 1


if __name__ == "__main__":
    # 日志信息
    logging.basicConfig(level=logging.INFO)
    # logging.basicConfig(
    #     format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    #     datefmt="%Y-%m-%d %H:%M:%S",
    #     level=logging.DEBUG)
    # logger = logging.getLogger('basic_logger')
    # logger.propagate = False
    formatter = logging.Formatter("%(asctime)s : [%(levelname)s] - %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # 日志记录
    logger = MyLogging("pixiv")
    logger.init(True)
    logger.addHandler(console_handler)

    # ====================================
    logger.info("开始初始化程序......")

    # 初始化设置信息
    logger.info("读取配置文件......")
    app_path = os.path.dirname(__file__)
    default_config_save_path = os.path.join(os.path.abspath(app_path), "default_config.json")
    config_save_path = os.path.join(os.path.abspath(app_path), "config.json")
    config_dict = ConfigSetter.get_config(config_save_path, default_config_save_path)
    
    # 初始化协程事件循环
    logger.info("初始化协程事件循环......")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 初始化数据库
    logger.info("初始化数据库......")
    asyncclient = motor_asyncio.AsyncIOMotorClient('localhost', 27017, io_loop=loop)
    asyncdb = asyncclient["pixiv"]
    asyncbackupcollection = asyncclient["backup"]["backup of pixiv infos"]

    # 启动GUI界面
    logger.info("启动GUI界面")
    # 解决图片在不同分辨率显示模糊问题
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)  # 创建应用程序对象
    # 获取屏幕的缩放比例
    # list_screen = QApplication.screens()
    dpi = QApplication.primaryScreen().logicalDotsPerInch() / 96
    # scaleRate = QApplication.screens()[0].logicalDotsPerInch() / 96
    # print(scaleRate)

    # main_window = mainwindow(dpi)  # 创建主窗口
    main_window = MainWindow(dpi)
    # 设置字体
    font = QFont()
    font.setPixelSize(14)
    # font.setPointSize(10)  # 括号里的数字可以设置成自己想要的字体大小
    font.setFamily("SimHei")  # 黑体
    # font.setFamily("SimSun")  # 宋体
    main_window.setFont(font)
    # main_window = QMainWindow()
    # ui = Ui_MainWindow()
    # ui.setupUi(main_window)
    main_window.setWindowFlags(Qt.WindowType.Window)
    # 显示一个非模式的对话框，用户可以随便切窗口，.exec()是模式对话框，用户不能随便切
    # ti = TrayIcon(main_window)
    # ti.show()
    main_window.show()  # 显示主窗口
    sys.exit(app.exec())  # 在主线程中退出
