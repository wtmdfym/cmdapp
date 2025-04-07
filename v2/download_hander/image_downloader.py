# -*-coding:utf-8-*-
import os, time
from asyncio import Event, Semaphore
from logging import Logger
from common import ClientPool, MongoDBHander, ResponseHander, check_image, make_gif


class ImageDownloader:
    """
    下载图片

    Attributes:
        __event: The stop event
        semaphore: The concurrent semaphore of asyncio
        backup_collection: A collection of backup of info(async)
        logger: The instantiated object of logging.Logger

    """

    __event = Event()

    def __init__(
        self,
        clientpool: ClientPool,
        semaphore: Semaphore,
        mongoDb_hander: MongoDBHander,
        logger: Logger,
    ) -> None:
        self.logger = logger
        self.clientpool = clientpool
        self.semaphore = semaphore
        self.mongoDb_hander = mongoDb_hander
        self.__event.set()

    async def invalid_image_recorder(self, id, failcode):
        doc = await self.mongoDb_hander.set_one(
            key="id", value=id, setter={"failcode": failcode}, collection="backup"
        )
        if not doc:
            self.logger.error("error in record invaild image:" + id + "\n" + doc)

    async def download_image(
        self, work_id: str, url: str, referer_url: str, save_path: str, frames: list
    ):
        if not self.__event.is_set():
            return None
        start_time = time.time()  # 程序开始时间
        headers = self.clientpool.headers
        headers.update({"referer": referer_url})
        # GIF
        if len(frames) > 0:
            # print(info)
            zip_path = work_id + ".zip"
            image_dir = work_id + "/"

            self.logger.info(f"Download GIF......    ID: {work_id}")
            success = await self._error_hander(url, headers, zip_path, is_image=False)
            if success:
                self.logger.info("Make GIF......")
                success = make_gif(
                    zip_path=zip_path,
                    image_dir=image_dir,
                    save_path=save_path,
                    frames=frames,
                )

        # normal image
        else:
            self.logger.info(f"Download image......    ID: {work_id}")
            success = await self._error_hander(url, headers, save_path)

        if success:
            end_time = time.time()  # 程序结束时间
            run_time = end_time - start_time
            self.logger.info(
                f"Download work {work_id} [{(success/1024):.2f} kb] complete, spend time {run_time:.2f}s, save to {save_path}"
            )
        else:
            self.logger.warning("Download work failed.")

    async def _error_hander(
        self, url: str, headers: dict, save_path: str, is_image: bool = True
    ) -> int:
        response_hander = ResponseHander(self.logger, False)
        response_hander = await self.clientpool.get(
            url=url,
            response_hander=response_hander,
            headers=headers,
        )
        if response_hander.res_code:
            self.logger.warning("Request failed.")
            if response_hander.res_code == 2:
                await self.mongoDb_hander.record_error()
            elif response_hander.res_code == 3:
                self.stop()
            return 0
        response = response_hander.origin_response
        if response is None:
            return 0
        with open(save_path, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=1024):

                if not self.__event.is_set():
                    f.close()
                    os.remove(save_path)
                    return 0
                f.write(chunk)
                f.flush()
        # 检查图片是否完整
        if is_image:
            if not check_image(save_path):
                os.remove(save_path)
                return 0
        return response.num_bytes_downloaded

    def pause_downloading(self):
        pass

    def stop(self):
        self.__event.clear()
        return
