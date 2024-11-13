# -*-coding:utf-8-*-
import os
import re
from PyQt6.QtCore import (
    QCoreApplication,
    QRect,
    Qt,
    pyqtSlot,
    QThread,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from GUIcmd.widgets import (
    ImageTableWidget,
    UserTableWidget,
    ScrollArea,
    ExtendedComboBox,
    ImageBox,
    SearchDialog
)
from GUIcmd.tools import Searcher
from cmd_app import AsyncThreadingManager
from Tool import ConfigSetter, format_cookie


class MainTab(QWidget):
    def __init__(self, parent, config_dict: dict,  config_save_path, loop, asyncdb, asyncbackupcollection, logger) -> None:
        super().__init__(parent)
        self.config_dict = config_dict
        self.config_save_path = config_save_path
        self.loop = loop
        self.asyncdb = asyncdb
        self.asyncbackupcollection = asyncbackupcollection
        self.logger = logger
        self.default_width = 1240
        self.default_height = 700
        self.initUI()
        self.startButton.clicked.connect(self.start_download)
        self.download_method = "followings"
        # self.inpuEdit.textEdited['QString'].connect() # type: ignore

    def initUI(self):
        self.setObjectName("tab")
        self.setGeometry(QRect(0, 0, self.default_width, self.default_height))
        self.gridLayout_5 = QGridLayout(self)
        self.gridLayout_5.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.inputEdit = QLineEdit(parent=self)
        self.inputEdit.setObjectName("inputEdit")
        self.gridLayout_5.addWidget(self.inputEdit, 0, 0, 1, 1)  # 位置0,0占1行2列
        self.checkButton = QPushButton(parent=self)
        self.checkButton.setObjectName("checkButton")
        self.gridLayout_5.addWidget(self.checkButton, 0, 1, 1, 1)
        self.startButton = QPushButton(parent=self)
        self.startButton.setObjectName("startButton")
        self.gridLayout_5.addWidget(self.startButton, 0, 2, 1, 1)
        self.radioButton = QRadioButton(parent=self)
        self.radioButton.setObjectName("radioButton")
        self.radioButton.toggled.connect(self.buttonStateRadio)
        self.gridLayout_5.addWidget(self.radioButton, 1, 0, 1, 1)
        self.radioButton_2 = QRadioButton(parent=self)
        self.radioButton_2.setObjectName("radioButton_2")
        self.radioButton_2.toggled.connect(self.buttonStateRadio)
        self.gridLayout_5.addWidget(self.radioButton_2, 1, 1, 1, 1)
        self.radioButton_3 = QRadioButton(parent=self)
        self.radioButton_3.setObjectName("radioButton_3")
        self.radioButton_3.setChecked(True)
        self.radioButton_3.toggled.connect(self.buttonStateRadio)
        self.gridLayout_5.addWidget(self.radioButton_3, 1, 2, 1, 1)
        self.progressBarLabellist = []
        self.progressBarlist = []
        for a in range(1, 2+1):  # config_dict['download_thread_number']+
            progressBarinfo = QLabel(parent=self)
            progressBarinfo.setText("No Process")
            self.gridLayout_5.addWidget(progressBarinfo, 0+a*2, 0, 1, 3)
            self.progressBarLabellist.append(progressBarinfo)
            self.progressBarlist.append(QProgressBar(parent=self))
            # self.progressBar.setMinimum(0)
            # self.progressBar.setMaximum(0)
            # self.progressBar.setTextVisible(False)
            # self.progressBar.setProperty("value", 99)
            # self.progressBar.setObjectName("progressBar")
            self.gridLayout_5.addWidget(
                self.progressBarlist[a-1], 1+a*2, 0, 1, 3)
        self.infodisplayer = QTextBrowser(parent=self)
        self.gridLayout_5.addWidget(
            self.infodisplayer, 6, 0, 1, 3)  # +(download_thread_number+1)*2

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.inputEdit.setPlaceholderText(
            _translate("MainWindow", "输入要下载的作品id或标签"))
        self.checkButton.setText(_translate("MainWindow", "check image"))
        self.startButton.setText(_translate("MainWindow", "start"))
        self.radioButton.setText(_translate("MainWindow", "Onework"))
        self.radioButton_2.setText(_translate("MainWindow", "Tags"))
        self.radioButton_3.setText(_translate("MainWindow", "Followings"))

    def buttonStateRadio(self):
        radioButton = self.sender()
        if radioButton.isChecked():
            self.download_method = radioButton.text()

    @pyqtSlot(list)
    def update_progressBar(self, infolist):
        for a in range(len(infolist)):
            info = infolist[a]
            if info:
                self.progressBarLabellist[a].setText(info[0])
                self.progressBarlist[a].setValue(info[1])

    def start_download(self):
        self.startButton.setDisabled(True)
        if self.download_method == "work":
            pass
            """
            downloader = pixiv_pyqt_tools.Downloader(
                config_dict["save_path"],
                config_dict["cookies"],
                config_dict["download_type"],
                config_dict["download_thread_number"],
                backup_collection,
                logger,
            )
            downloader.start_work_download(id=self.inputEdit.text())
            """
        elif self.download_method == "followings":
            # 实例化爬虫管理类
            self.manager = AsyncThreadingManager(self.config_dict, self.config_save_path, self.loop, self.asyncdb,
                                                self.asyncbackupcollection, self.logger)
            # 启动爬虫
            self.manager.run()
            '''
            self.t = AsyncDownloadThreadingManger(
                self.config_dict, self.config_save_path,    # self.loop,
                self.db, self.backup_collection, self.asyncdb,
                self.asyncbackup_collection, self.logger)
            self.t.progress_signal.connect(self.update_progressBar)
            self.t.break_signal.connect(self.stop_download)
            self.t.start()
            '''
            self.startButton.setText("stop")
            self.startButton.clicked.disconnect(self.start_download)
            self.startButton.clicked.connect(self.stop_download)
            
        self.startButton.setEnabled(True)

    def stop_download(self):
        """
        调用线程管理器方法,停止所有线程
        """
        self.startButton.setDisabled(True)
        try:
            self.manager.stop()
            del self.manager
            self.startButton.setText("start")
            self.startButton.clicked.disconnect(self.stop_download)
            self.startButton.clicked.connect(self.start_download)
        except Exception:
            pass
        finally:
            self.startButton.setEnabled(True)


class SearchTab(QWidget):
    def __init__(self, parent, save_path: str, logger, backupcollection, show_image_callback, usethumbnail: bool = False):
        super().__init__(parent)
        self.page = 1
        self.total_page = 1
        self.save_path = save_path
        self.logger = logger
        self.image_url = "https://www.pixiv.net/"
        self.image_path = self.save_path + "picture/"
        self.default_width = 1220
        self.default_height = 700
        self.backup_collection = backupcollection
        self.initUI(show_image_callback, usethumbnail)

    def initUI(self, show_image_callback, usethumbnail):
        self.setGeometry(QRect(0, 0, self.default_width, self.default_height))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout_2")
        # 搜索控件
        self.searchEdit = QLineEdit(parent=self)
        self.searchEdit.setObjectName("searchEdit")
        self.gridLayout.addWidget(self.searchEdit, 0, 0, 1, 1)
        self.search_imageButton = QPushButton(parent=self)
        self.search_imageButton.setObjectName("search_imageButton")
        self.search_imageButton.clicked.connect(self.search)
        self.gridLayout.addWidget(self.search_imageButton, 0, 1, 1, 1)
        self.search_typeButton = QPushButton(parent=self)
        self.search_typeButton.setObjectName("search_typeButton")
        self.search_typeButton.clicked.connect(self.set_search_type)
        self.gridLayout.addWidget(self.search_typeButton, 0, 2, 1, 1)
        # 在浏览器和资源管理器中显示
        self.show_in_browserButton = QPushButton(parent=self)
        self.show_in_browserButton.setObjectName("show_in_browserButton")
        self.show_in_browserButton.clicked.connect(self.show_in_browser)
        self.gridLayout.addWidget(self.show_in_browserButton, 1, 0, 1, 3)
        self.show_in_resourceButton = QPushButton(parent=self)
        self.show_in_resourceButton.setObjectName("show_in_resourceButton")
        self.show_in_resourceButton.clicked.connect(self.show_in_resource)
        self.gridLayout.addWidget(self.show_in_resourceButton, 2, 0, 1, 3)
        # 显示控件
        self.imageinfoDisplayer = QTextBrowser(parent=self)
        self.imageinfoDisplayer.setObjectName("imageinfoDisplayer")
        # 禁止打开链接
        self.imageinfoDisplayer.setOpenLinks(False)
        self.imageinfoDisplayer.setOpenExternalLinks(False)
        # self.imageinfoDisplayer.setFixedHeight(600)
        self.gridLayout.addWidget(self.imageinfoDisplayer, 3, 0, 1, 3)
        self.imagedisplatLayout = QVBoxLayout()
        self.images_tableWidget = ImageTableWidget(
            self, self.save_path, self.logger, show_image_callback,
            usethumbnail, update_info_callback=self.update_image_info
        )
        self.imagedisplatLayout.addWidget(self.images_tableWidget, 0)
        # self.gridLayout.addWidget(self.images_tableWidget, 0, 3, 2, 1)
        # 翻页控件
        self.pageLayout = QHBoxLayout()
        self.prev_pageButton = QPushButton(parent=self)
        self.prev_pageButton.setObjectName("prev_pageButton")
        self.prev_pageButton.setMaximumWidth(100)
        self.prev_pageButton.clicked.connect(
            lambda: self.change_page(page=self.page - 1)
        )
        self.pageLayout.addWidget(self.prev_pageButton, 0)
        self.pageEdit = QSpinBox(parent=self)
        self.pageEdit.setMaximumWidth(100)
        self.pageEdit.setMinimum(1)
        self.pageEdit.setMaximum(self.total_page)
        self.pageLayout.addWidget(self.pageEdit, 1)
        self.pageLabel = QLabel(parent=self)
        self.pageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pageLabel.setObjectName("pageLabel")
        self.pageLabel.setMaximumWidth(100)
        self.pageLayout.addWidget(self.pageLabel, 2)
        self.jump_pageButton = QPushButton(parent=self)
        self.jump_pageButton.setObjectName("jump_pageButton")
        self.jump_pageButton.setMaximumWidth(100)
        self.jump_pageButton.clicked.connect(
            lambda: self.change_page(page=self.pageEdit.value())
        )
        self.pageLayout.addWidget(self.jump_pageButton, 3)
        self.next_pageButton = QPushButton(parent=self)
        self.next_pageButton.setObjectName("next_pageButton")
        self.next_pageButton.setMaximumWidth(100)
        self.next_pageButton.clicked.connect(
            lambda: self.change_page(page=self.page + 1)
        )
        self.pageLayout.addWidget(self.next_pageButton, 4)
        self.imagedisplatLayout.addLayout(self.pageLayout, 1)
        self.gridLayout.addLayout(self.imagedisplatLayout, 0, 3, 5, 1)
        # self.gridLayout.addLayout(self.pageLayout, 3, 3, 1, 1)

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.searchEdit.setPlaceholderText(
            _translate("MainWindow", "输入要搜索的标签"))
        self.imageinfoDisplayer.setPlaceholderText(
            _translate("MainWindow", "单击图片获取图片信息\n双击查看大图"))
        self.jump_pageButton.setText(_translate("MainWindow", "Jump"))
        self.pageLabel.setText(_translate("MainWindow", "1/1"))
        self.next_pageButton.setText(_translate("MainWindow", "Next Page"))
        self.prev_pageButton.setText(_translate("MainWindow", "Prev Page"))
        self.search_imageButton.setText(_translate("MainWindow", "Search"))
        self.show_in_browserButton.setText(
            _translate("MainWindow", "Show in browser"))
        self.show_in_resourceButton.setText(
            _translate("MainWindow", "Show in resource")
        )

    def search(self):
        work_number = 0
        self.images_tableWidget.image_datas.clear()
        self.images_tableWidget.total_page = 1
        # self.results = None
        search_info = self.searchEdit.text()
        if re.findall(r"\+", search_info):
            and_search = []
            for one_search in search_info.split("+"):
                if re.search(r"\d{4,}", one_search):
                    and_search.append({"userId": one_search})
                else:
                    and_search.append(
                        {"tags." + one_search: {"$exists": "true"}})
            self.results = self.backup_collection.find(
                {"$and": and_search}).sort("id", -1)

        elif re.findall(r"\,", search_info):
            or_search = []
            for one_search in search_info.split(","):
                if re.search(r"\d{4,}", one_search):
                    or_search.append({"userId": one_search})
                else:
                    or_search.append(
                        {"tags." + one_search: {"$exists": "true"}})
                self.results = self.backup_collection.find(
                    {"$or": or_search}).sort("id", -1)

        elif search_info:
            one_search = {}
            if re.search(r"\d{4,}", search_info):
                one_search.update({"userId": search_info})
            else:
                one_search.update({"tags." + search_info: {"$exists": "true"}})
            self.results = self.backup_collection.find(
                one_search).sort("id", -1)

        else:
            self.results = self.backup_collection.find(
                {'id': {"$exists": "true"}}).sort("id", -1)

        for row in self.results:
            self.images_tableWidget.image_datas.append(row)
            work_number += 1

        self.total_page = (
            work_number - 1) // (self.images_tableWidget.rows * self.images_tableWidget.columns) + 1
        self.pageEdit.setMaximum(self.total_page)
        self.images_tableWidget.page = 1
        self.change_page(1)

        # self.page, self.total_page = self.images_tableWidget.search(
        #     self.searchEdit.text()
        # )
        self.pageLabel.setText(str(self.page) + "/" + str(self.total_page))

    @pyqtSlot(dict)
    def make_search_criteria(self, search_criteria: dict):
        work_number = 0
        self.images_tableWidget.image_datas.clear()
        self.images_tableWidget.total_page = 1
        print(search_criteria)
        searcher = Searcher(search_criteria)
        self.results = searcher.get_result()

        for row in self.results:
            self.images_tableWidget.image_datas.append(row)
            work_number += 1

        self.total_page = (
            work_number - 1) // (self.images_tableWidget.rows * self.images_tableWidget.columns) + 1
        self.pageEdit.setMaximum(self.total_page)
        self.images_tableWidget.page = 1
        self.change_page(1)
        self.pageLabel.setText(str(self.page) + "/" + str(self.total_page))

    def set_search_type(self):
        self.set_search_criteria_win = SearchDialog(self.parent())
        self.set_search_criteria_win.get_search_criteria_singal.connect(
            self.make_search_criteria)
        self.set_search_criteria_win.show()

    def update_image_info(self, result):
        self.imageinfoDisplayer.clear()
        id = result.get("id")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> ID:</font></b>%d' % id)
        type = result.get("type")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Type:</font></b>%s' % type)
        title = result.get("title")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Title:</font></b><br />%s' % title)
        userid = result.get("userId")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> UserID:</font></b>%s' % userid)
        username = result.get("username")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> UserName:</font></b>%s' % username)
        tags = result.get("tags")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Tags:</font></b><br />%s' % tags)
        description = result.get("description")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Description:</font></b><br />%s' % description)
        self.image_url = "https://www.pixiv.net/artworks/" + str(id)
        self.image_path = result.get("relative_path")[0]

    def show_in_browser(self):
        import webbrowser

        webbrowser.open(self.image_url)

    def show_in_resource(self):
        file = self.save_path + self.image_path
        file = os.path.realpath(file)
        # print(file)
        if os.path.exists(file):
            self.logger.info("文件路径:%s" % file)
            os.system(f"explorer /select, {file}")
        else:
            # print("文件不存在:%s"%(file))
            self.logger.warning("文件不存在:%s" % (file))

    def change_page(self, page):
        if page == 0:
            return
        elif page > self.total_page:
            return
        self.page = page
        self.pageEdit.setValue(self.page)
        self.pageLabel.setText(str(page) + "/" + str(self.total_page))
        self.images_tableWidget.change_page(page)

    def resizeEvent(self, a0) -> None:
        new_width = self.width()
        new_height = self.height()
        width_ratio = new_width / self.default_width
        height_ratio = new_height / self.default_height
        self.images_tableWidget.img_width = int(
            self.images_tableWidget.default_img_width * width_ratio
        )
        self.images_tableWidget.img_height = int(
            self.images_tableWidget.default_img_height * height_ratio
        )
        self.images_tableWidget.resize(
            self.images_tableWidget.img_width * self.images_tableWidget.columns + 10,
            self.images_tableWidget.img_height * self.images_tableWidget.rows + 10,
        )
        return super().resizeEvent(a0)


class TagsTab(QWidget):
    def __init__(self, parent, db, changetab, settext):
        super().__init__(parent)
        self.tags_collection = db["All Tags"]
        self.like_tag_collection = db["Like Tag"]
        self.dislike_tag_collection = db["Dislike Tag"]
        self.finded_tags_count = 0
        self.changetab = changetab
        self.settext = settext
        self.default_width = 1220
        self.default_height = 700
        self.initUI()
        # 加载标签
        self.load_tags()
        # 事件绑定
        self.tags_tableWidget.itemSelectionChanged.connect(self.fill_comboBox)
        self.search_tagComboBox.lineEdit().textEdited.connect(self.search_tag)
        # self.search_tagButton.clicked.connect(self.search_tag)
        self.select_tagButton.clicked.connect(self.select_tag)
        self.addlikeButton.clicked.connect(self.addlike)
        self.adddislikeButton.clicked.connect(self.adddislike)
        self.delete_tagButton.clicked.connect(self.delete_tag)

    def initUI(self):
        self.setGeometry(QRect(0, 0, self.default_width, self.default_height))
        self.gridLayout_3 = QGridLayout(self)
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_3.setObjectName("gridLayout_3")
        # self.search_tagEdit = QLineEdit(parent=self)
        # self.search_tagEdit.setObjectName("search_tagEdit")
        # self.gridLayout_3.addWidget(self.search_tagEdit, 0, 0, 1, 1)
        self.search_tagComboBox = ExtendedComboBox(parent=self)
        self.search_tagComboBox.setObjectName("search_tagComboBox")
        self.gridLayout_3.addWidget(self.search_tagComboBox, 0, 0, 1, 2)
        # self.search_tagButton = QPushButton(parent=self)
        # self.search_tagButton.setObjectName("search_tagButton")
        # self.gridLayout_3.addWidget(self.search_tagButton, 0, 1, 1, 1)
        self.select_tagButton = QPushButton(parent=self)
        self.select_tagButton.setObjectName("select_tagButton")
        self.gridLayout_3.addWidget(self.select_tagButton, 0, 2, 1, 1)
        self.addlikeButton = QPushButton(parent=self)
        self.addlikeButton.setObjectName("addlikeButton")
        self.gridLayout_3.addWidget(self.addlikeButton, 0, 3, 1, 1)
        self.adddislikeButton = QPushButton(parent=self)
        self.adddislikeButton.setObjectName("adddislikeButton")
        self.gridLayout_3.addWidget(self.adddislikeButton, 0, 4, 1, 1)
        self.delete_tagButton = QPushButton(parent=self)
        self.delete_tagButton.setObjectName("delete_tagButton")
        self.gridLayout_3.addWidget(self.delete_tagButton, 0, 5, 1, 1)
        self.tags_tableWidget = QTableWidget(parent=self)
        self.tags_tableWidget.setObjectName("tags_tableWidget")
        self.tags_tableWidget.setColumnCount(3)
        self.tags_tableWidget.setColumnWidth(0, 300)
        self.tags_tableWidget.setColumnWidth(1, 300)
        self.tags_tableWidget.setColumnWidth(2, 300)
        # 禁止编辑
        self.tags_tableWidget.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        # 选择方式
        self.tags_tableWidget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        # 自定义第一行内容
        self.tags_tableWidget.setHorizontalHeaderLabels(
            ["All", "Like", "Dislike"])
        self.gridLayout_3.addWidget(self.tags_tableWidget, 1, 0, 1, 6)

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        # self.search_tagButton.setText(_translate("MainWindow", "search"))
        self.search_tagComboBox.setPlaceholderText(
            _translate("MainWindow", "输入要搜索的标签"))
        self.select_tagButton.setText(_translate("MainWindow", "select"))
        self.addlikeButton.setText(_translate("MainWindow", "addlike"))
        self.adddislikeButton.setText(_translate("MainWindow", "adddislike"))
        self.delete_tagButton.setText(_translate("MainWindow", "delete"))

    def load_tags(self):
        tags = (
            self.tags_collection.find({"works_count": {"$gt": 5}}, {"_id": 0})
            .sort("works_count", -1)
            .limit(500)
        )
        count = self.tags_collection.count_documents(
            {"works_count": {"$gt": 5}}, limit=500
        )
        self.tags_tableWidget.setRowCount(count)
        row = 0
        for tag in tags:
            table_data = str((tag.get("name"), tag.get("translate")))
            self.tags_tableWidget.setItem(row, 0, QTableWidgetItem(table_data))
            row += 1
        tags.close()
        tags = self.like_tag_collection.find(
            {"name": {"$exists": "true"}}, {"_id": 0})
        self.likerow = 0
        for tag in tags:
            table_data = str((tag.get("name"), tag.get("translate")))
            self.tags_tableWidget.setItem(
                self.likerow, 1, QTableWidgetItem(table_data))
            self.likerow += 1
        tags.close()
        tags = self.dislike_tag_collection.find(
            {"name": {"$exists": "true"}}, {"_id": 0}
        )
        self.dislikerow = 0
        for tag in tags:
            table_data = str((tag.get("name"), tag.get("translate")))
            self.tags_tableWidget.setItem(
                self.dislikerow, 2, QTableWidgetItem(table_data)
            )
            self.dislikerow += 1
        tags.close()

    def fill_comboBox(self):
        try:
            text = self.tags_tableWidget.selectedItems()[0].text()
        except IndexError:
            text = ""
        self.search_tagComboBox.setEditText(text)

    def select_tag(self):
        selected_tag = self.search_tagComboBox.currentText()
        selected_tag = eval(selected_tag)
        self.changetab(1)
        self.settext(selected_tag[0])

    def delete_tag(self):
        selected_tag = self.tags_tableWidget.selectedItems()[0]
        selection = eval(selected_tag.text())
        name, a = selection
        if selected_tag.column() == 1:
            selected_tag.setText("")
            self.like_tag_collection.find_one_and_delete({"name": name})
        elif selected_tag.column() == 2:
            selected_tag.setText("")
            self.dislike_tag_collection.find_one_and_delete({"name": name})
        elif selected_tag.column() == 0:
            # print("Don't delete tag in All tags!")
            # logger.info("Don't delete tag in All tags!")
            pass

    def addlike(self):
        selected = self.tags_tableWidget.selectedItems()[0].text()
        selected_tag = eval(selected)
        earlier = self.like_tag_collection.find_one({"name": selected_tag[0]})
        if earlier:
            if earlier != {"name": selected_tag[0], "translate": selected_tag[1]}:
                self.like_tag_collection.find_one_and_update(
                    {"name": selected_tag[0]}, {
                        "$set": {"translate": selected_tag[1]}}
                )
        else:
            self.like_tag_collection.insert_one(
                {"name": selected_tag[0], "translate": selected_tag[1]}
            )
            self.tags_tableWidget.setItem(
                self.likerow, 1, QTableWidgetItem(selected))
            self.likerow += 1

    def adddislike(self):
        selected = self.tags_tableWidget.selectedItems()[0].text()
        selected_tag = eval(selected)
        earlier = self.dislike_tag_collection.find_one(
            {"name": selected_tag[0]})
        if earlier:
            if earlier != {"name": selected_tag[0], "translate": selected_tag[1]}:
                self.dislike_tag_collection.find_one_and_update(
                    {"name": selected_tag[0]}, {
                        "$set": {"translate": selected_tag[1]}}
                )
        else:
            self.dislike_tag_collection.insert_one(
                {"name": selected_tag[0], "translate": selected_tag[1]}
            )
            self.tags_tableWidget.setItem(
                self.dislikerow, 2, QTableWidgetItem(selected)
            )
            self.dislikerow += 1

    def search_tag(self, text):
        # text = self.search_tagEdit.text()
        for a in range(self.finded_tags_count):
            self.search_tagComboBox.removeItem(a)
        # print(text)
        if text:
            findeditems = self.tags_tableWidget.findItems(
                text, Qt.MatchFlag.MatchContains
            )
            findedtags = []
            for findeditem in findeditems:
                findedtags.append(findeditem.text())
            self.finded_tags_count = len(findedtags)
            self.search_tagComboBox.addItems(findedtags)
        else:
            self.finded_tags_count = 0
        self.search_tagComboBox.setEditText(text)
        self.search_tagComboBox.pFilterModel.setFilterFixedString(text)
        # print(findedtags)


class UserTab1(QWidget):
    def __init__(self, parent, logger, db, savepath, usethumbnail):
        super().__init__(parent)
        self.default_width = 1220
        self.default_height = 700
        self.initUI(logger, db, savepath, usethumbnail)

    def initUI(self, logger, db, savepath, usethumbnail):
        self.scrollArea = ScrollArea(self, logger, db, savepath, usethumbnail)
        self.scrollArea.setGeometry(
            QRect(0, 0, self.default_width, self.default_height)
        )
        self.scrollArea.setObjectName("scrollArea")


class UserTab(QWidget):
    def __init__(self, parent, logger, db, savepath, usethumbnail):
        super().__init__(parent)
        self.default_width = 1220
        self.default_height = 700
        # 设置页码
        self.pagesize = 4  # 每页显示四个作者的信息
        self.page = 1
        self.initUI(logger, db, savepath, usethumbnail)
        # 获取作者信息
        user_datas = []
        following = db["All Followings"]
        for one in following.find(
            {"userId": {"$exists": "true"}}, {"_id": 0}
        ):
            user_datas.append(one)
        self.total_page = (
            following.count_documents(
                {"userId": {"$exists": "true"}})
            // self.pagesize
            + 1
        )
        self.pageEdit.setMaximum(self.total_page)
        self.user_tableWidget.user_datas = user_datas
        self.change_page(1)

    def initUI(self, logger, db, savepath, usethumbnail):
        self.setGeometry(QRect(0, 0, self.default_width, self.default_height))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        # 作者信息显示控件
        self.user_tableWidget = UserTableWidget(
            self, savepath, logger, db, usethumbnail=usethumbnail)
        self.gridLayout.addWidget(
            self.user_tableWidget, 0, 0, Qt.AlignmentFlag.AlignHCenter)
        # 翻页控件
        self.pageLayout = QHBoxLayout()
        self.prev_pageButton = QPushButton(parent=self)
        self.prev_pageButton.setMaximumWidth(100)
        self.prev_pageButton.clicked.connect(
            lambda: self.change_page(page=self.page - 1)
        )
        self.pageLayout.addWidget(self.prev_pageButton, 0)
        self.pageEdit = QSpinBox(parent=self)
        self.pageEdit.setMaximumWidth(100)
        self.pageEdit.setMinimum(1)
        self.pageLayout.addWidget(self.pageEdit, 1)
        self.pageLabel = QLabel(parent=self)
        self.pageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pageLabel.setMaximumWidth(100)
        self.pageLayout.addWidget(self.pageLabel, 2)
        self.jump_pageButton = QPushButton(parent=self)
        self.jump_pageButton.setMaximumWidth(100)
        self.jump_pageButton.clicked.connect(
            lambda: self.change_page(page=self.pageEdit.value())
        )
        self.pageLayout.addWidget(self.jump_pageButton, 3)
        self.next_pageButton = QPushButton(parent=self)
        self.next_pageButton.setMaximumWidth(100)
        self.next_pageButton.clicked.connect(
            lambda: self.change_page(page=self.page + 1)
        )
        self.pageLayout.addWidget(self.next_pageButton, 4)
        self.gridLayout.addLayout(
            self.pageLayout, 1, 0, Qt.AlignmentFlag.AlignHCenter)

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.jump_pageButton.setText(_translate("MainWindow", "Jump"))
        # self.pageLabel.setText(_translate("MainWindow", "1/1"))
        self.next_pageButton.setText(_translate("MainWindow", "Next Page"))
        self.prev_pageButton.setText(_translate("MainWindow", "Prev Page"))

    def update_info(self):
        pass

    def resizeEvent(self, a0) -> None:
        # self.user_tableWidget.setFixedSize(self.width(), self.height() - 20)
        return super().resizeEvent(a0)

    def change_page(self, page):
        if page == 0:
            return
        elif page > self.total_page:
            return
        self.page = page
        self.pageEdit.setValue(self.page)
        self.pageLabel.setText(str(page) + "/" + str(self.total_page))
        self.user_tableWidget.change_page(page)


class ConfigTab(QWidget):
    def __init__(self, parent, logger, config_dict: dict, config_save_path, db, reloadUI):
        super().__init__(parent)
        self.config_dict = config_dict
        self.config_save_path = config_save_path
        self.db = db
        self.logger = logger
        self.default_width = 1220
        self.default_height = 700
        self.reloadUIcall = reloadUI
        self.initUI()
        # 显示设置信息
        self.savepathEdit.setText(config_dict.get("save_path"))
        self.cookiesEdit.setPlainText(str(config_dict.get("cookies")))
        self.http_proxiesEdit.setText(config_dict.get("http_proxies"))
        self.https_proxiesEdit.setText(config_dict.get("https_proxies"))
        self.enable_console_outputCheckBox.setChecked(
            config_dict.get("enable_console_output"))
        self.enable_thumbnailCheckBox.setChecked(
            config_dict.get("use_thumbnail"))
        self.semaphoreComboBox.setCurrentIndex(
            config_dict.get("semaphore") - 1
        )
        self.download_thread_numberComboBox.setCurrentIndex(
            config_dict.get("download_thread_number") - 1
        )
        download_type = config_dict.get("download_type")
        for a in download_type.items():
            if a[0] == "illust" and a[1]:
                self.getillustsCheckBox.setChecked(True)
            elif a[0] == "manga" and a[1]:
                self.getmangaCheckBox.setChecked(True)
            elif a[0] == "ugoira" and a[1]:
                self.getugoiraCheckBox.setChecked(True)    
            elif a[0] == "mangaSeries" and a[1]:
                self.getmangaSeriesCheckBox.setChecked(True)
            elif a[0] == "novelSeries" and a[1]:
                self.getnovelSeriesCheckBox.setChecked(True)
            elif a[0] == "novel" and a[1]:
                self.getnovelsCheckBox.setChecked(True)

        # 设置事件绑定
        self.save_configsButton.clicked.connect(self.save_configs)
        self.reloadUIButton.clicked.connect(self.reloadUIcall)
        self.database_backupButton.clicked.connect(self.mongoDB_manual_backup)
        self.generate_thumbnailButton.clicked.connect(self.generate_thumbnail)
        # self.generate =self.GenerateThumbnail(self.update_progressBar)
        # self.generate_thumbnailButton.clicked.connect(self.generate.run)

    def initUI(self):
        self.setGeometry(QRect(0, 0, self.default_width, self.default_height))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        # 保存路径
        self.pathLabel = QLabel(parent=self)
        self.pathLabel.setObjectName("pathLabel")
        self.gridLayout.addWidget(self.pathLabel, 0, 0, 1, 1)
        self.savepathEdit = QLineEdit(parent=self)
        self.savepathEdit.setObjectName("savepathEdit")
        self.gridLayout.addWidget(self.savepathEdit, 0, 1, 1, 2)
        # cookie
        self.cookieLabel = QLabel(parent=self)
        self.cookieLabel.setObjectName("cookieLabel")
        self.gridLayout.addWidget(self.cookieLabel, 1, 0, 1, 1)
        self.cookiesEdit = QPlainTextEdit(parent=self)
        self.cookiesEdit.setObjectName("cookiesEdit")
        self.gridLayout.addWidget(self.cookiesEdit, 1, 1, 1, 2)
        # 代理
        self.http_proxiesLabel = QLabel(parent=self)
        self.gridLayout.addWidget(self.http_proxiesLabel, 2, 0, 1, 1)
        self.http_proxiesEdit = QLineEdit(parent=self)
        self.gridLayout.addWidget(self.http_proxiesEdit, 2, 1, 1, 2)
        self.https_proxiesLabel = QLabel(parent=self)
        self.gridLayout.addWidget(self.https_proxiesLabel, 3, 0, 1, 1)
        self.https_proxiesEdit = QLineEdit(parent=self)
        self.gridLayout.addWidget(self.https_proxiesEdit, 3, 1, 1, 2)
        # 启用控制台输出
        self.enable_console_outputCheckBox = QCheckBox(parent=self)
        self.gridLayout.addWidget(
            self.enable_console_outputCheckBox, 4, 0, 1, 3)
        # 缩略图
        self.enable_thumbnailCheckBox = QCheckBox(parent=self)
        self.gridLayout.addWidget(self.enable_thumbnailCheckBox, 5, 0, 1, 1)
        self.generate_thumbnailButton = QPushButton(parent=self)
        self.gridLayout.addWidget(self.generate_thumbnailButton, 5, 1, 1, 2)
        # 最大并发数
        self.semaphoreLabel = QLabel(parent=self)
        self.gridLayout.addWidget(self.semaphoreLabel, 6, 0, 1, 1)
        self.semaphoreComboBox = QComboBox(parent=self)
        self.semaphoreComboBox.setObjectName(
            "download_t_numberComboBox")
        self.semaphoreComboBox.addItem("")
        self.semaphoreComboBox.addItem("")
        self.semaphoreComboBox.addItem("")
        self.semaphoreComboBox.addItem("")
        self.semaphoreComboBox.addItem("")
        self.semaphoreComboBox.addItem("")
        self.gridLayout.addWidget(
            self.semaphoreComboBox, 6, 1, 1, 2)
        # 下载线程数
        self.download_t_numberLabel = QLabel(parent=self)
        self.download_t_numberLabel.setObjectName("download_t_numberLabel")
        self.gridLayout.addWidget(self.download_t_numberLabel, 7, 0, 1, 1)
        self.download_thread_numberComboBox = QComboBox(parent=self)
        self.download_thread_numberComboBox.setObjectName(
            "download_t_numberComboBox")
        self.download_thread_numberComboBox.addItem("")
        self.download_thread_numberComboBox.addItem("")
        self.download_thread_numberComboBox.addItem("")
        self.download_thread_numberComboBox.addItem("")
        self.gridLayout.addWidget(
            self.download_thread_numberComboBox, 7, 1, 1, 2)
        # 下载作品类型
        self.download_typeLabel = QLabel(parent=self)
        self.download_typeLabel.setObjectName("download_typeLabel")
        self.gridLayout.addWidget(self.download_typeLabel, 8, 0, 1, 3)
        self.getillustsCheckBox = QCheckBox(parent=self)
        self.getillustsCheckBox.setObjectName("getillustsCheckBox")
        self.gridLayout.addWidget(self.getillustsCheckBox, 9, 0, 1, 3)
        self.getmangaCheckBox = QCheckBox(parent=self)
        self.getmangaCheckBox.setObjectName("getmangaCheckBox")
        self.gridLayout.addWidget(self.getmangaCheckBox, 10, 0, 1, 3)
        self.getugoiraCheckBox  = QCheckBox(parent=self)
        self.getugoiraCheckBox.setObjectName("getugoiraCheckBox")
        self.gridLayout.addWidget(self.getugoiraCheckBox, 11, 0, 1, 3)
        self.getmangaSeriesCheckBox = QCheckBox(parent=self)
        self.getmangaSeriesCheckBox.setObjectName("getmangaSeriesCheckBox")
        self.gridLayout.addWidget(self.getmangaSeriesCheckBox, 12, 0, 1, 3)
        self.getnovelSeriesCheckBox = QCheckBox(parent=self)
        self.getnovelSeriesCheckBox.setObjectName("getnovelSeriesCheckBox")
        self.gridLayout.addWidget(self.getnovelSeriesCheckBox, 13, 0, 1, 3)
        self.getnovelsCheckBox = QCheckBox(parent=self)
        self.getnovelsCheckBox.setObjectName("getnovelsCheckBox")
        self.gridLayout.addWidget(self.getnovelsCheckBox, 14, 0, 1, 3)
        # 保存按钮
        self.save_configsButton = QPushButton(parent=self)
        self.save_configsButton.setObjectName("save_configsButton")
        self.gridLayout.addWidget(self.save_configsButton, 15, 0, 1, 1)
        # 重载GUI界面按钮
        self.reloadUIButton = QPushButton(parent=self)
        self.reloadUIButton.setObjectName("reloadUIButton")
        self.gridLayout.addWidget(self.reloadUIButton, 15, 1, 1, 1)
        # 数据库备份按钮
        self.database_backupButton = QPushButton(parent=self)
        self.database_backupButton.setObjectName("database_backupButton")
        self.gridLayout.addWidget(self.database_backupButton, 15, 2, 1, 1)

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.pathLabel.setText(_translate("MainWindow", "save path:"))
        self.cookieLabel.setText(_translate("MainWindow", "cookies:"))
        self.http_proxiesLabel.setText(
            _translate("MainWindow", "http proxies:"))
        self.http_proxiesEdit.setPlaceholderText(
            _translate("MainWindow", "eg:http://localhost:1111"))
        self.https_proxiesLabel.setText(
            _translate("MainWindow", "https proxies:"))
        self.https_proxiesEdit.setPlaceholderText(
            _translate("MainWindow", "eg:https://162.144.1.241:1111"))
        self.enable_console_outputCheckBox.setText(
            _translate("MainWindow", "启用控制台输出"))
        self.enable_thumbnailCheckBox.setText(
            _translate("MainWindow", "使用缩略图"))
        self.generate_thumbnailButton.setText(
            _translate("MainWindow", "生成缩略图"))
        self.semaphoreLabel.setText(_translate(
            "MainWindow", "最大并发数(若过高可能被封IP,封号......)"))
        self.semaphoreComboBox.setItemText(
            0, _translate("MainWindow", "1")
        )
        self.semaphoreComboBox.setItemText(
            1, _translate("MainWindow", "2")
        )
        self.semaphoreComboBox.setItemText(
            2, _translate("MainWindow", "3")
        )
        self.semaphoreComboBox.setItemText(
            3, _translate("MainWindow", "4")
        )
        self.semaphoreComboBox.setItemText(
            4, _translate("MainWindow", "5")
        )
        self.semaphoreComboBox.setItemText(
            5, _translate("MainWindow", "6")
        )
        self.download_t_numberLabel.setText(_translate("MainWindow", "下载线程数"))
        self.download_thread_numberComboBox.setItemText(
            0, _translate("MainWindow", "1")
        )
        self.download_thread_numberComboBox.setItemText(
            1, _translate("MainWindow", "2")
        )
        self.download_thread_numberComboBox.setItemText(
            2, _translate("MainWindow", "3")
        )
        self.download_thread_numberComboBox.setItemText(
            3, _translate("MainWindow", "4")
        )
        self.download_typeLabel.setText(_translate("MainWindow", "下载作品类型"))
        self.getillustsCheckBox.setText(_translate("MainWindow", "Getillusts"))
        self.getmangaCheckBox.setText(_translate("MainWindow", "Getmanga"))
        self.getugoiraCheckBox.setText(_translate("MainWindow", "Getugoira"))
        self.getmangaSeriesCheckBox.setText(
            _translate("MainWindow", "GetmangaSeries"))
        self.getnovelSeriesCheckBox.setText(
            _translate("MainWindow", "GetnovelSeries"))
        self.getnovelsCheckBox.setText(_translate("MainWindow", "Getnovels"))
        self.save_configsButton.setText(_translate("MainWindow", "save"))
        self.reloadUIButton.setText(_translate("MainWindow", "reloadUI"))
        self.database_backupButton.setText(
            _translate("MainWindow", "backup database"))

    def save_configs(self):
        new_config_dict = {}
        new_config_dict["save_path"] = self.savepathEdit.text()
        cookies = self.cookiesEdit.toPlainText()
        new_config_dict["cookies"] = self.config_dict.get("cookies")
        if not re.search("{.*}", cookies):
            new_config_dict["cookies"] = format_cookie(cookies)
            self.cookiesEdit.setPlainText(str(new_config_dict["cookies"]))
        new_config_dict["http_proxies"] = self.http_proxiesEdit.text()
        new_config_dict["https_proxies"] = self.https_proxiesEdit.text()
        new_config_dict["enable_console_output"] = self.enable_console_outputCheckBox.isChecked()
        new_config_dict["use_thumbnail"] = self.enable_thumbnailCheckBox.isChecked()
        new_config_dict["semaphore"] = (
            self.semaphoreComboBox.currentIndex() + 1
        )
        new_config_dict["download_thread_number"] = (
            self.download_thread_numberComboBox.currentIndex() + 1
        )
        download_type = {}
        download_type["getillusts"] = self.getillustsCheckBox.isChecked()
        download_type["getmanga"] = self.getmangaCheckBox.isChecked()
        download_type["getmangaSeries"] = self.getmangaSeriesCheckBox.isChecked()
        download_type["getnovelSeries"] = self.getnovelSeriesCheckBox.isChecked()
        download_type["getnovels"] = self.getnovelsCheckBox.isChecked()
        new_config_dict["download_type"] = download_type
        new_config_dict["last_record_time"] = self.config_dict["last_record_time"]
        if new_config_dict != self.config_dict:
            ConfigSetter.set_config(
                self.config_save_path, new_config_dict)
            msgBox = QMessageBox.information(
                self, "INFO", "重新加载窗口以应用设置?", buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if msgBox == QMessageBox.StandardButton.Ok:
                self.reloadUIcall()

    def mongoDB_manual_backup(self):
        pass
        """
        # print("开始手动备份,请勿关闭程序!!!")
        self.logger.info("开始手动备份,请勿关闭程序!!!")
        now = 1
        all = len(self.db.list_collection_names())
        for name in self.db.list_collection_names():
            print("正在备份第%d/%d个数据库" % (now, all))
            collection = db[name]
            a = collection.find({"id": {"$exists": True}}, {"_id": 0})
            for docs in a:
                if len(docs) == 9:
                    b = backup_collection.find_one({"id": docs.get("id")})
                    if b:
                        if b.get("failcode"):
                            del b["failcode"]
                        if b == docs:
                            continue
                        else:
                            c = backup_collection.find_one_and_update(
                                {"id": docs.get("id")}, {"$set": docs}
                            )
                        if c:
                            pass
                        else:
                            print("cao")
                            print(docs)
                    else:
                        backup_collection.insert_one(docs)
            done = int(50 * now / all)
            sys.stdout.write(
                "\r[%s%s] %d%%" % ("█" * done, " " *
                                   (50 - done), 100 * now / all)
            )
            sys.stdout.flush()
            now += 1
        # print("手动备份完成")
        self.logger.info("手动备份完成")
        """

    def generate_thumbnail(self):
        self.progressDialog = QProgressDialog("准备读取数据库......", "取消", 0, 101)
        self.progressDialog.setWindowTitle("生成缩略图......")
        self.progressDialog.setFixedSize(500, 100)
        self.progressDialog.show()
        self.t = self.GenerateThumbnail(
            self.config_dict["save_path"], self.db, self.logger)
        self.t.progress_signal.connect(self.updateProgressDialog)
        self.progressDialog.canceled.connect(self.t.stop)
        self.progressDialog.destroyed.connect(self.t.stop)
        self.t.start()

    def updateProgressDialog(self, text, value):
        self.progressDialog.setLabelText(text)
        self.progressDialog.setValue(value)

    class GenerateThumbnail(QThread):
        progress_signal = pyqtSignal(str, int)

        def __init__(self, savepath, db, logger) -> None:
            super().__init__()
            self.ifstop = False
            self.save_path = savepath
            self.db = db
            self.logger = logger

        def run(self) -> None:
            from PIL import Image, UnidentifiedImageError
            now = 1
            collist = self.db.list_collection_names()
            all = len(collist) - 4
            for name in collist:
                if name == "All Followings":
                    continue
                elif name == "All Tags":
                    continue
                elif name == "Like Tag":
                    continue
                elif name == "Dislike Tag":
                    continue
                # print("\n正在读取第%d/%d个数据库:%s"%(now,all,name))
                self.logger.debug("正在读取第%d/%d个数据库:%s" % (now, all, name))
                # progressDialog.setLabelText("正在读取数据库:%s" % name)
                now1 = 1
                collection = self.db[name]
                docs = collection.find({"id": {"$exists": True}}, {"_id": 0})
                all1 = collection.count_documents({"id": {"$exists": True}})
                for doc in docs:
                    uid = doc.get("userId")
                    if not uid:
                        continue
                    paths = doc.get("relative_path")
                    if not os.path.exists(self.save_path + "thumbnail/" + uid):
                        os.mkdir(self.save_path + "thumbnail/" + uid)
                    for path in paths:
                        if self.ifstop:
                            break
                        picture_path = self.save_path + path
                        thumbnail_path = (
                            self.save_path
                            + "thumbnail/"
                            + re.search("(?<=picture/).*", path).group()
                        )
                        if os.path.exists(picture_path):
                            if not os.path.exists(thumbnail_path):
                                try:
                                    loaded_image = Image.open(picture_path)
                                    loaded_image.load()
                                except UnidentifiedImageError:
                                    os.remove(picture_path)
                                    continue
                                except OSError:
                                    loaded_image.close()
                                    os.remove(picture_path)
                                    continue
                                original_width, original_height = loaded_image.size
                                aspect_ratio = original_width / original_height
                                if aspect_ratio > 1:
                                    new_width = min(original_width, 320)
                                    new_height = int(new_width / aspect_ratio)
                                else:
                                    new_height = min(original_height, 360)
                                    new_width = int(new_height * aspect_ratio)
                                resized_image = loaded_image.resize(
                                    (new_width, new_height))
                                resized_image.save(thumbnail_path)
                    if self.ifstop:
                        break
                    self.progress_signal.emit(
                        "正在读取数据库:%s" % name, int(100 * now1 / all1))
                    now1 += 1
                if self.ifstop:
                    self.logger.info("停止生成缩略图")
                    return
                now += 1
            self.logger.info("生成缩略图完成")
            self.progress_signal.emit("生成缩略图完成", 100)

        def stop(self):
            self.ifstop = True


class ImageTab(QWidget):
    def __init__(self, parent, save_path: str, logger, image_info: dict, show_image_callback, usethumbnail: bool = False):
        '''
            image_data -> eg:{'_id': ObjectId('6569f5118b962c95d51e3cf9'),\
                'type': 'illusts', 'id': 113867483, 'title': 'あさひに蟹縛り',\
                'description': '(蟹縛りは)初投稿です。', 'tags': {'R-18': None, 'お兄ちゃんはおしまい': '别当欧尼酱了',\
                '桜花あさひ': '樱花朝日', '猿轡': '猿辔', '拘束': '束缚', '緊縛': '紧缚', 'おもらし': '失禁', 'bondage': None,\
                'gagged': None}, 'original_url': ['https://i.pximg.net/img-original/img/2023/12/01/21/30/47/113867483_p0.png',\
                'https://i.pximg.net/img-original/img/2023/12/01/21/30/47/113867483_p1.png',\
                'https://i.pximg.net/img-original/img/2023/12/01/21/30/47/113867483_p2.png'], 'userId': '17259031',\
                'username': 'moegi', 'relative_path': ['picture/17259031/113867483_p0.png','picture/17259031/113867483_p1.png]}
        '''
        super().__init__(parent)
        self.page = 1
        self.logger = logger
        self.default_width = 1220
        self.default_height = 700
        self.initUI(save_path, show_image_callback, usethumbnail)
        self.retranslateUi()
        self.total_page = (len(image_info.get("relative_path")) -
                           1) // (self.images_tableWidget.rows * self.images_tableWidget.columns) + 1
        self.pageEdit.setMaximum(self.total_page)
        self.pageLabel.setText(str(self.page) + "/" + str(self.total_page))
        self.images_tableWidget.image_datas = image_info
        # 作品信息
        id = image_info.get("id")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> ID:</font></b>%d' % id)
        type = image_info.get("type")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Type:</font></b>%s' % type)
        title = image_info.get("title")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Title:</font></b><br />%s' % title)
        userid = image_info.get("userId")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> UserID:</font></b>%s' % userid)
        username = image_info.get("username")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> UserName:</font></b>%s' % username)
        tags = image_info.get("tags")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Tags:</font></b><br />%s' % tags)
        description = image_info.get("description")
        self.imageinfoDisplayer.append(
            '<b><font color=DeepSkyBlue> Description:</font></b><br />%s' % description)
        self.image_url = "https://www.pixiv.net/{}/{}".format(
            image_info.get("type"), image_info.get("id"))
        self.image_path = save_path + image_info.get("relative_path")[0]
        # 显示图片
        self.images_tableWidget.update_image_new()

    def initUI(self, save_path, show_image_callback, usethumbnail):
        self.setGeometry(QRect(0, 0, self.default_width, self.default_height))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        # 在浏览器和资源管理器中显示
        self.show_in_browserButton = QPushButton(parent=self)
        self.show_in_browserButton.clicked.connect(self.show_in_browser)
        self.gridLayout.addWidget(self.show_in_browserButton, 0, 0, 1, 3)
        self.show_in_resourceButton = QPushButton(parent=self)
        self.show_in_resourceButton.clicked.connect(self.show_in_resource)
        self.gridLayout.addWidget(self.show_in_resourceButton, 1, 0, 1, 3)
        # 显示控件
        self.imageinfoDisplayer = QTextBrowser(parent=self)
        # self.imageinfoDisplayer.setObjectName("imageinfoDisplayer")
        # self.imageinfoDisplayer.setFixedHeight(600)
        self.gridLayout.addWidget(self.imageinfoDisplayer, 2, 0, 1, 3)
        self.imagedisplatLayout = QVBoxLayout()
        self.images_tableWidget = ImageTableWidget(
            self, save_path, self.logger, show_image_callback, usethumbnail, one_work=True
        )
        self.imagedisplatLayout.addWidget(self.images_tableWidget, 0)
        # self.gridLayout.addWidget(self.images_tableWidget, 0, 3, 2, 1)
        # 翻页控件
        self.pageLayout = QHBoxLayout()
        self.prev_pageButton = QPushButton(parent=self)
        self.prev_pageButton.setMaximumWidth(100)
        self.prev_pageButton.clicked.connect(
            lambda: self.change_page(page=self.page - 1)
        )
        self.pageLayout.addWidget(self.prev_pageButton, 0)
        self.pageEdit = QSpinBox(parent=self)
        self.pageEdit.setMaximumWidth(100)
        self.pageEdit.setMinimum(1)
        self.pageLayout.addWidget(self.pageEdit, 1)
        self.pageLabel = QLabel(parent=self)
        self.pageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pageLabel.setMaximumWidth(100)
        self.pageLayout.addWidget(self.pageLabel, 2)
        self.jump_pageButton = QPushButton(parent=self)
        self.jump_pageButton.setMaximumWidth(100)
        self.jump_pageButton.clicked.connect(
            lambda: self.change_page(page=self.pageEdit.value())
        )
        self.pageLayout.addWidget(self.jump_pageButton, 3)
        self.next_pageButton = QPushButton(parent=self)
        self.next_pageButton.setMaximumWidth(100)
        self.next_pageButton.clicked.connect(
            lambda: self.change_page(page=self.page + 1)
        )
        self.pageLayout.addWidget(self.next_pageButton, 4)
        self.imagedisplatLayout.addLayout(self.pageLayout, 1)
        self.gridLayout.addLayout(self.imagedisplatLayout, 0, 3, 5, 1)
        # self.gridLayout.addLayout(self.pageLayout, 3, 3, 1, 1)

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.jump_pageButton.setText(_translate("MainWindow", "Jump"))
        self.pageLabel.setText(_translate("MainWindow", "No Page"))
        self.next_pageButton.setText(_translate("MainWindow", "Next Page"))
        self.prev_pageButton.setText(_translate("MainWindow", "Prev Page"))
        self.show_in_browserButton.setText(
            _translate("MainWindow", "Show in browser"))
        self.show_in_resourceButton.setText(
            _translate("MainWindow", "Show in resource")
        )

    def show_in_browser(self):
        import webbrowser
        webbrowser.open(self.image_url)

    def show_in_resource(self):
        file = os.path.realpath(self.image_path)
        # print(file)
        if os.path.exists(file):
            self.logger.info("文件路径:%s" % file)
            os.system(f"explorer /select, {file}")
        else:
            # print("文件不存在:%s"%(file))
            self.logger.warning("文件不存在:%s" % (file))

    def change_page(self, page):
        if page == 0:
            return
        elif page > self.total_page:
            return
        self.page = page
        self.pageEdit.setValue(self.page)
        self.pageLabel.setText(str(page) + "/" + str(self.total_page))
        self.images_tableWidget.change_page(page)

    def resizeEvent(self, a0) -> None:
        new_width = self.width()
        new_height = self.height()
        width_ratio = new_width / self.default_width
        height_ratio = new_height / self.default_height
        self.images_tableWidget.img_width = int(
            self.images_tableWidget.default_img_width * width_ratio
        )
        self.images_tableWidget.img_height = int(
            self.images_tableWidget.default_img_height * height_ratio
        )
        self.images_tableWidget.resize(
            self.images_tableWidget.img_width * self.images_tableWidget.columns + 10,
            self.images_tableWidget.img_height * self.images_tableWidget.rows + 10,
        )
        return super().resizeEvent(a0)


class OriginalImageTab(QWidget):
    def __init__(self, image_info=None) -> None:
        super().__init__()
        self.info = image_info
        self.initUI()
        if isinstance(image_info, str):
            self.imageinfoDisplayer.setPlainText(self.info)
        elif image_info:
            # 作品信息
            id = image_info.get("id")
            self.imageinfoDisplayer.append(
                '<b><font color=DeepSkyBlue> ID:</font></b>%d' % id)
            type = image_info.get("type")
            self.imageinfoDisplayer.append(
                '<b><font color=DeepSkyBlue> Type:</font></b>%s' % type)
            title = image_info.get("title")
            self.imageinfoDisplayer.append(
                '<b><font color=DeepSkyBlue> Title:</font></b><br />%s' % title)
            userid = image_info.get("userId")
            self.imageinfoDisplayer.append(
                '<b><font color=DeepSkyBlue> UserID:</font></b>%s' % userid)
            username = image_info.get("username")
            self.imageinfoDisplayer.append(
                '<b><font color=DeepSkyBlue> UserName:</font></b>%s' % username)
            tags = image_info.get("tags")
            self.imageinfoDisplayer.append(
                '<b><font color=DeepSkyBlue> Tags:</font></b><br />%s' % tags)
            description = image_info.get("description")
            self.imageinfoDisplayer.append(
                '<b><font color=DeepSkyBlue> Description:</font></b><br />%s' % description)

    def initUI(self):
        self.hboxLayout = QHBoxLayout(self)
        if self.info:
            self.imageinfoDisplayer = QTextBrowser(self)
            self.hboxLayout.addWidget(self.imageinfoDisplayer, 0)
        self.box = ImageBox()
        self.hboxLayout.addWidget(self.box, 1)

    def open_image(self, img_name):
        """
        open image file
        :return:
        """
        self.box.set_image(img_name)
