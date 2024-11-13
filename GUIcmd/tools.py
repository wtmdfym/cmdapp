# -*-coding:utf-8-*-
import pymongo
import os
from PyQt6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    Q_ARG,
    QThread,
    QRunnable,
    pyqtSignal,
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel


class ImageLoader(QRunnable):
    """
    读取图片并异步返回给主线程
    """

    def __init__(self, obj: QObject, img_width: int, img_height: int,
                 target: QLabel = None, index: tuple = None, image_path: str = None):
        super().__init__()
        self.qobject = obj
        self.img_width = img_width
        self.img_height = img_height
        self.target = target
        self.index = index
        self.image_path = image_path

    def run(self):
        if os.path.exists(self.image_path):
            image = QImage(self.image_path)
            # image = QImage.fromData(data)
            # image = image.convertToFormat(QImage.Format.Format_ARGB32)
            image = image.scaled(
                self.img_width,
                self.img_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap = QPixmap()
            if pixmap.convertFromImage(image):
                # 图片加载成功
                args = (0, pixmap)
            else:
                # 图片加载失败
                os.remove(self.image_path)
                args = (2, None)
        else:
            # 图片不存在
            args = (3, None)
        # 加载完成后异步发送
        if self.index:
            QMetaObject.invokeMethod(self.qobject, 'set_image', Qt.ConnectionType.QueuedConnection, Q_ARG(
                tuple, self.index), Q_ARG(object, args))
        elif self.target:
            QMetaObject.invokeMethod(self.qobject, 'set_image', Qt.ConnectionType.QueuedConnection, Q_ARG(
                QLabel, self.target), Q_ARG(object, args))


class Searcher():
    def __init__(self, search_criteria, client: pymongo.MongoClient) -> None:
        '''TODO series and novels'''
        self.client = client
        # {'keywords': {'all': '捆绑,R-18', 'some': '', 'no': 'ai'},
        #  'worktype': 0, 'searchtype': 0, 'integratework': False}
        # :/runoob/
        self.query = {}
        orquery = []
        # 搜索的作品类型
        # worktype [0:"插画、漫画、动图(动态漫画)", 1:"插画、动图", 2:"插画", 3:"漫画", 4:"动图"]
        worktype = search_criteria.get("worktype")
        worktypeindex = [{'type': 'illust'}, {
            'type': 'manga'}, {'type': 'ugoira'}]
        if worktype == 0:
            typequery = [worktypeindex[0], worktypeindex[1], worktypeindex[2]]
            typequery = {'$or': typequery}
        elif worktype == 1:
            typequery = [worktypeindex[0], worktypeindex[2]]
            typequery = {'$or': typequery}
        elif worktype == 2:
            typequery = worktypeindex[0]
        elif worktype == 3:
            typequery = worktypeindex[1]
        elif worktype == 3:
            typequery = worktypeindex[2]

        self.keywords = search_criteria.get("keywords")
        if isinstance(self.keywords, dict):
            keywords_type = ["AND", "OR", "NOT"]
            type_map = {"AND": ''}
            keywords = {}
            for key in keywords_type:
                _keyword = self.keywords.get(key)
                if _keyword:
                    _keyword = _keyword.split(',')
                keyword = _keyword[0]
                if len(_keyword) >= 1:
                    for one in _keyword[1:]:
                        keyword += f' {key} \"{one}\"'
                keywords.update({key: keyword})
        else:
            _keyword = self.keywords.split(',')
            keyword = _keyword[0]
            if len(_keyword) >= 1:
                for one in _keyword[1:]:
                    keyword += f' OR \"{one}\"'
        self.keywords = keywords
        self.search_type = search_criteria.get("searchtype")

    def get_result(self):
        # searchtype [0:"标签(部分一致)", 1:"标签(完全一致)", 2:"标题、说明文字"]
        if self.search_type == 0:
            result = self.search_by_tag()
        elif self.search_type == 1:
            result = self.search_by_tag(partly=False)
        elif self.search_type == 2:
            result = self.search_by_title_or_description

    def search_by_tag(self, partly=True):
        # {'$text': { '$search': }
        collection = self.client['pixiv']['All Tags']
        if partly:
            if isinstance(self.keywords, dict):
                pass
            else:
                pass
            for one in self.keywords.split(','):
                pass
            collection.find(self.query).sort("id", -1)
        else:
            pass

    def search_by_title_or_description(self):
        pass

    def search_by_userId(self):
        pass

    def search_by_content(self):
        pass
