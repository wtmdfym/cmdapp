class BasePipeline:
    name = "base"

    async def process_items(self, items: list[dict]) -> bool:
        """
        Process scraped item.
        """
        success = False
        for item in items:
            success = False or await self._process_item(item)

        return success

    async def process_item(self, item: dict) -> bool:
        success = False or await self._process_item(item)
        return success

    async def _process_item(self, item: dict) -> bool:
        print(item)
        return True
