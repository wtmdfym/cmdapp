from typing import TypeVar, Generic
from data import BaseItem

T = TypeVar("T", bound=BaseItem)


class BasePipeline(Generic[T]):
    name = "base"

    async def process_items(self, items: list[T]) -> bool:
        """
        Process scraped items.
        """
        success = True
        for item in items:
            item_success = await self._process_item(item)
            success = success and item_success

        return success

    async def process_item(self, item: T) -> bool:
        success = await self._process_item(item)
        return success

    async def _process_item(self, item: T) -> bool:
        print(item)
        return True
