"""
Scheduler module for managing prioritized asynchronous task execution.

This module provides a Scheduler class that maintains a priority queue for handling
requests with different priority levels and automatically avoids duplicate requests.
Lower priority values are processed first, and tasks with the same
priority are processed in FIFO order.
"""

import asyncio
from data import Request


class Scheduler:
    """
    A priority-based task scheduler using `asyncio.PriorityQueue`.

    This scheduler manages incoming requests by priority (lower values = higher priority)
    and submission order, while avoiding duplicate requests.\n
    It supports synchronous submission and retrieval, and graceful shutdown capabilities.

    Attributes:
        _queue: A priority queue storing tuples of (priority, counter, request).
        _task_counter: Monotonically increasing counter for FIFO ordering of same-priority tasks.
    """

    def __init__(self, queue_maxsize: int = 200):
        """
        Initialize the Scheduler with an empty priority queue.

        The maximum capacity of the queue depends on the value of queue_maxsize.\n
        The queue stores tuples of: (priority: `int`, task_counter: `int`, request: `Request`)

        Args:
            queue_maxsize: The maximum capacity of the `asyncio.PriorityQueue`.
        """
        self._queue = asyncio.PriorityQueue[tuple[int, int, Request]](
            maxsize=queue_maxsize
        )
        self._task_counter = 0
        self._finished_request: set[bytes] = set()

    def submit(self, request: Request) -> bool:
        """
        Submit a request to the scheduler's priority queue.

        The request will be fingerprinted to avoid making duplicate requests to the same URL.

        The request is queued based on its priority (lower values processed first).
        If multiple requests have the same priority, they are processed in FIFO order
        based on submission time.

        Args:
            request: The Request object to be scheduled, containing a priority attribute.

        Returns:
            True: If the request was successfully added to the queue.
            False: If the request has already added to the queue (duplicate request).

        Raises:
            asyncio.QueueFull: If the queue has reached its maximum capacity.
            asyncio.QueueShutDown: If the queue has been shut down.
        """
        fp = request.fingerprint
        if fp in self._finished_request:
            return False

        # lowest first, earliest first
        self._task_counter += 1
        self._queue.put_nowait((request.priority, self._task_counter, request))
        return True

    def get(self) -> Request | None:
        """
        Retrieve and remove the highest priority request from the queue.

        This is a non-blocking operation that immediately returns the next available
        request or None if the queue is empty.

        Returns:
            Request  if a request is available, or None if the queue is empty.

        Raises:
            asyncio.QueueShutDown: If the queue has been shut down.
        """
        try:
            if self._queue.empty():
                return None
            _, _, request = self._queue.get_nowait()
            return request
        except asyncio.QueueShutDown:
            raise
        except asyncio.QueueEmpty:
            return None

    def mark_done(self, request_fp: bytes):
        self._finished_request.add(request_fp)

    async def shutdown(self) -> None:
        """
        Gracefully shut down the scheduler queue.

        This prevents new items from being added to the queue and signals
        that the scheduler is being terminated.
        """
        self._queue.shutdown()

    @property
    def blocked(self) -> bool:
        """
        Check if the scheduler queue has reached its maximum capacity.

        Returns:
            True if the queue is full, False otherwise.
        """
        return self._queue.full()

    @property
    def empty(self) -> bool:
        """
        Check if the scheduler queue is empty.

        Returns:
            True if the queue is empty, False otherwise.
        """
        return self._queue.empty()
