import json
from httpx import Response
from parsel import Selector
from logging import Logger
from typing import Literal, Any


class ResponseHander:
    def __init__(self, logger: Logger, isjson: bool):
        self.logger: Logger = logger
        self.isjson: bool = isjson
        self.res_code: Literal[0, 1, 2, 3] = 0
        """ 
        - 0-success
        - 1-fail
        - 2-fail and record
        - 3-stop all requests
        """
        self._response = None
        self._processor: dict[Literal["GET", "REQUIRE", "SELECT"], Any] = {}
        self._processed_response = None

    def set_response(self, response: Response):
        self._response = response

    def set_processor(self, processor: dict[Literal["GET", "REQUIRE", "SELECT"], str]):
        """
        ## Set processor before send request.

        - **GET** = dict.get()
            split by `.`

        - **REQUIRE** = dict[]
            split by `.`

        - **SELECT** = Selector.param1(param2).get()
            param1 -> xpath/css(str)
            param2 -> query
            split by `..`

        - **WRITE** = wb
            `tuple`
            param1 -> path
            param2 -> `asyncio.Event`
        """
        self._processor = processor

    @property
    def origin_response(self):
        if self._response is None:
            self.logger.error("Response not setted.")
            return None
        return self._response

    @property
    def processed_response(self):
        if self._processed_response is None:
            if not self.check():
                self.logger.warning("Parsing failed.")
        return self._processed_response

    @property
    def html(self) -> str:
        if self._response is None:
            self.logger.error("Response not setted.")
            return ""
        return self._response.text

    @property
    def json(self) -> dict | None:
        if self._response is None:
            self.logger.error("Response not setted.")
            return None
        _json = self._response.json()
        if not isinstance(_json, dict):
            return None
        if _json.get("error"):
            self.logger.warning(f"Access Error------message:{_json.get('message')}")
            return None
        return _json

    def check(self) -> bool:
        return self._process()

    def _get_res(self):
        if self._processed_response is not None:
            return self._processed_response
        if self.isjson:
            return self.json
        else:
            return self.html

    def _process(self) -> bool:
        if self._response is None:
            self.logger.error("Response not setted.")
            return False
        res = self._get_res()
        for processor, value in self._processor.items():
            if processor == "GET":
                if not isinstance(res, dict):
                    raise ProcessorError(processor=processor, data_type=type(res))
                for getter in value.split("."):
                    res = res.get(getter)
                    if res is None:
                        return True
            elif processor == "REQUIRE":
                if not isinstance(res, dict):
                    raise ProcessorError(processor=processor, data_type=type(res))
                try:
                    for getter in value.split("."):
                        res = res[getter]
                except AttributeError:
                    return False
            elif processor == "SELECT":

                if not isinstance(res, str):
                    raise ProcessorError(processor=processor, data_type=type(res))
                getter = value.split("..")
                if len(getter) != 2:
                    raise ProcessorError(
                        processor=processor,
                        data_type=type(res),
                        value=value,
                    )
                select_type, query = getter
                selector = Selector(res, type="html")
                if select_type == "xpath":
                    res = selector.xpath(query=query).get()
                elif select_type == "css":
                    res = selector.css(query=query).get()
                else:
                    raise ProcessorError(
                        processor=processor,
                        data_type=type(res),
                        value=value,
                    )
                if res is None:
                    self.logger.warning(
                        "Data Not found, Check select method or resourse!"
                    )
                    return False
                res = json.loads(res, strict=False)
            elif processor == "WRITE":
                # TODO
                path, event = value
                """ 
                with open(path, "wb") as f:
                    async for chunk in self._response.aiter_bytes(chunk_size=1024):
                        if not event.is_set():
                            f.close()
                            os.remove(path)
                            return (0, None)
                        f.write(chunk)
                        f.flush()
                # 检查图片是否完整
                if isimage:
                    iscomplete = check_image(path)
                    if iscomplete:
                        return (0, None)
                    else:
                        self.logger.warning("图片下载失败")
                        os.remove(path)
                        return (1, None)
                else:
                    return (0, None)"""
                res = True
            else:
                raise ProcessorError(processor=processor)
        self._processed_response = res
        return True


class ProcessorError(Exception):
    processor: str
    data_type: type
    value: str

    def __init__(
        self, processor: str, data_type: type | None = None, value: str | None = None
    ):
        self.processor = processor
        if value is not None:
            self.value = value
            super().__init__(f"Illegal Value: {value}")
        elif data_type is not None:
            self.data_type = data_type
            super().__init__(
                f"Processor not support for the data: {processor} for date type {data_type}"
            )
        else:
            super().__init__(f"Processor not support: {processor}")
