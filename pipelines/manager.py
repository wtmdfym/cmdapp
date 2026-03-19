from typing import Iterable
from .base import BasePipeline
from data import Item
from collections import defaultdict

SCHEMAS = {
    "print": {
        "required": [],
        "optional": [],
    },
    "db": {
        "required": ["collection", "backup", "op"],
        "optional": ["document", "filter", "update", "new_name"],
    },
}


class PipelineManager:

    def __init__(self, logger):
        self.logger = logger
        self.pipelines: list[BasePipeline] = []
        self._routes: dict[str, list[BasePipeline]] = defaultdict(list)

    def add_pipeline(self, pipeline: BasePipeline):
        self.pipelines.append(pipeline)

    def register(self, item_type: str, pipeline: BasePipeline):
        self._routes[item_type].append(pipeline)

    def set_routes(self, registry: dict[str, str]):
        self._routes.clear()
        for item_type, name in registry.items():
            pipeline = self.get_pipeline(name)
            if pipeline is None:
                raise ValueError(f"Spider asked pipeline-{name} not exist.")

            self.register(item_type, pipeline)

    def validate_item(self, item: Item):
        schemas = SCHEMAS[item.type]
        for field in schemas["required"]:
            if field not in item.data:
                raise ValueError(f"Missing field: {field}")

    async def process(self, items: Iterable[Item]):
        for item in items:
            pipelines = self._routes.get(item.type)

            if not pipelines:
                raise ValueError(f"No pipeline for item type: {item.type}")

            self.validate_item(item)

            for pipeline in pipelines:
                await pipeline.process_item(item.data)

    def get_pipeline(self, name: str) -> BasePipeline | None:
        for pipeline in self.pipelines:
            if pipeline.name == name:
                return pipeline
