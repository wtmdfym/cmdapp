class BasePipeline:

    async def process_item(self, item):
        """
        Process scraped item.

        Args:
            item: spider result data

        Returns:
            item
        """
        return item


