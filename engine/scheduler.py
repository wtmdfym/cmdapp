"""
Scheduler module for managing prioritized asynchronous task execution.

This module provides a Scheduler class that maintains a priority queue for handling
requests with different priority levels and automatically avoids duplicate requests.
Lower priority values are processed first, and tasks with the same
priority are processed in FIFO order.
"""

import asyncio
from typing import Iterable
from data import Request


class Scheduler:
    """
    A priority-based task scheduler using `asyncio.PriorityQueue`.

    This scheduler manages incoming requests by priority (lower values = higher priority)
    and submission order, while avoiding duplicate requests.

    It supports synchronous submission and retrieval, and graceful shutdown capabilities.

    Attributes:
        _queue: A priority queue storing tuples of (priority, counter, request).
        _task_counter: Monotonically increasing counter for FIFO ordering of same-priority tasks.
        _scheduled_request: A set of fingerprints for requests currently in the queue.
        _finished_request: A set of fingerprints for completed requests to prevent re-processing.
    """

    def __init__(self, logger, queue_maxsize: int = 200):
        """
        Initialize the Scheduler with an empty priority queue.

        Creates a new scheduler instance with an empty priority queue and tracking sets
        for managing request lifecycle and deduplication.

        Args:
            queue_maxsize: The maximum capacity of the `asyncio.PriorityQueue`.
                          Defaults to 200 if not specified.

        Note:
            The queue stores tuples of: (priority: `int`, task_counter: `int`, request: `Request`)
        """
        self.logger = logger
        self._queue = asyncio.PriorityQueue[tuple[int, int, Request]](
            maxsize=queue_maxsize
        )
        self._task_counter = 0
        self._scheduled_request: set[bytes] = set()
        self._finished_request: set[bytes] = set()

    async def submit(self, request: Request) -> bool:
        fp = request.fingerprint
        if fp in self._scheduled_request or fp in self._finished_request:
            self.logger.warning(
                "The target URL for this request has been scheduled for execution."
            )
            return False

        self._task_counter += 1
        await self._queue.put((request.priority, self._task_counter, request))
        self._scheduled_request.add(fp)
        self.logger.debug("Schedule request: %s" % request.fingerprint)
        return True

    async def submit_requests(self, requests: Iterable[Request]):
        for request in requests:
            await self.submit(request)

    def get_nowait(self) -> Request | None:
        """
        Retrieve and remove the highest priority request from the queue.

        This is a non-blocking operation that immediately returns the next available
        request with the highest priority. The request is removed from the scheduled
        set but not yet marked as finished.

        Returns:
            Request: The highest priority request if available.
            None: If the queue is empty.

        Raises:
            asyncio.QueueShutDown: If the queue has been shut down.

        Note:
            After processing the returned request, call `mark_done()` to prevent
            the same request from being scheduled again.
        """
        try:
            if self._queue.empty():
                return None

            _, _, request = self._queue.get_nowait()

            self._scheduled_request.remove(request.fingerprint)
            return request

        except asyncio.QueueShutDown:
            raise
        except asyncio.QueueEmpty:
            return None

    async def get(self) -> Request:
        """
        Retrieve and remove the highest priority request from the queue.

        This is a non-blocking operation that immediately returns the next available
        request with the highest priority. The request is removed from the scheduled
        set but not yet marked as finished.

        Returns:
            Request: The highest priority request if available.

        Raises:
            asyncio.QueueShutDown: If the queue has been shut down.

        Note:
            After processing the returned request, call `mark_done()` to prevent
            the same request from being scheduled again.
        """
        try:
            _, _, request = await self._queue.get()

            self._scheduled_request.remove(request.fingerprint)
            return request

        except asyncio.QueueShutDown:
            raise

    def mark_done(self, request_fp: bytes) -> None:
        """
        Mark a request as completed and add it to the finished set.

        This method records the request fingerprint to prevent duplicate processing
        of the same request in the future. Once marked as done, the request cannot
        be resubmitted to the scheduler.

        Args:
            request_fp: The fingerprint (bytes) of the completed request.
                       Typically obtained from `request.fingerprint`.

        Returns:
            None

        Note:
            This should be called after successfully processing a request retrieved
            via `get()`. The fingerprint is permanently stored in `_finished_request`
            for the lifetime of the scheduler instance.

        Example:
            >>> request = scheduler.get()
            >>> if request:
            ...     # Process the request...
            ...     scheduler.mark_done(request.fingerprint)
        """
        self._finished_request.add(request_fp)

    async def shutdown(self) -> None:
        """
        Gracefully shut down the scheduler queue.

        Initiates an orderly shutdown of the scheduler by preventing new items
        from being added to the queue. Existing items in the queue remain available
        for retrieval via `get()` until exhausted.

        Returns:
            None

        Raises:
            asyncio.QueueShutDown: Propagated from the underlying queue shutdown.

        Note:
            After shutdown, `submit()` will raise `asyncio.QueueShutDown`.
            Call this method when the application is terminating or when no more
            requests should be accepted.
        """
        self._queue.shutdown()

    @property
    def blocked(self) -> bool:
        """
        Check if the scheduler queue has reached its maximum capacity.

        Indicates whether the queue is currently full and cannot accept new
        requests without first removing existing ones.

        Returns:
            bool: True if the queue is at maximum capacity, False otherwise.

        Note:
            When blocked, `submit()` will raise `asyncio.QueueFull` until space
            becomes available.
        """
        return self._queue.full()

    @property
    def empty(self) -> bool:
        """
        Check if the scheduler queue contains no pending requests.

        Provides a quick check for queue emptiness without modifying the queue state.

        Returns:
            bool: True if the queue has no pending requests, False otherwise.

        Note:
            An empty queue does not indicate that all requests are processed;
            some may be in progress or marked as finished. Use in combination with
            `_scheduled_request` and `_finished_request` for complete state assessment.
        """
        return self._queue.empty()
