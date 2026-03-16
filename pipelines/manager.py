from data import SpiderResult
from .base import BasePipeline


class PipelineManager:

    def __init__(self):
        self.pipelines: list[BasePipeline] = []

    def add_pipelines(self, pipelines: list[BasePipeline]):
        self.pipelines.extend(pipelines)

    async def process_item(self, result: SpiderResult) -> bool:

        for pipeline in self.pipelines:
            if not await pipeline.process_item(result):
                return False

        return True
