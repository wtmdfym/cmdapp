"""
Downloader module for handling asynchronous HTTP requests with concurrency control.

This module provides a Downloader class that manages HTTP request execution using
a client pool, with support for pausing/resuming operations and limiting concurrent
requests via semaphore-based flow control.
"""

import asyncio
from data import Request, Response
from .clientpool import ClientPool


class Downloader:
    """
    An asynchronous HTTP downloader with concurrency control and pause/resume capabilities.

    This downloader manages HTTP request execution using a client pool, limiting
    the number of concurrent requests through a semaphore. It supports pausing
    all ongoing operations and resuming them later.

    Attributes:
        client_pool: The ClientPool instance used to execute HTTP requests.
        _pause_event: An asyncio.Event controlling pause/resume state. When cleared,
                      workers will block at pause points until the event is set again.
        _semaphore: An asyncio.Semaphore limiting concurrent request execution.
    """

    def __init__(self, client_pool: ClientPool, max_concurrency=5):
        """
        Initialize the Downloader with a client pool and concurrency limit.

        Args:
            client_pool: The ClientPool instance for executing HTTP requests.
            max_concurrency: Maximum number of concurrent requests allowed (default: 5).
                             Higher values increase throughput but consume more resources.
        """
        self.client_pool = client_pool

        # Event for pause/resume control. Set = running, Clear = paused
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._semaphore = asyncio.Semaphore(max_concurrency)

    def submit(
        self,
        request: Request,
    ) -> asyncio._CoroutineLike:
        return self._worker(request)

    async def _worker(self, request: Request) -> Response | None:
        """
        Worker coroutine that executes a single HTTP request.

        This method handles the actual request execution, including:
        - Waiting for any pause condition to clear
        - Acquiring semaphore slot for concurrency control
        - Executing the HTTP request via client_pool
        - Constructing and returning the Response object

        future will set a result `Response` if request successful, otherwise
        set the failed `Request`

        Args:
            request: The Request object with all HTTP parameters.
            future: The asyncio.Future to resolve with the Response.

        Raises:
            RuntimeError: If the client pool request fails at runtime.
                          This exception is re-raised for upstream handling.
        """

        # Pause point2: blocks here if pause() has been called, until resume() is called
        await self._pause_event.wait()

        async with self._semaphore:
            try:
                resp = await self.client_pool.request(
                    method=request.method,
                    url=request.url,
                    params=request.params,
                    data=request.data,
                    headers=request.headers,
                    use_primary=request.use_primary,
                )

                if resp is None:
                    # future.set_result(request)
                    return

                response = Response(
                    request=request,
                    status=resp.status_code,
                    headers=dict(resp.headers),
                    content=resp.content,
                    elapsed=resp.elapsed.total_seconds(),
                    raw=resp,
                )

                # Resolve the future with successful response
                # future.set_result(response)
                return response

            except RuntimeError as e:
                # Re-raise RuntimeError for upstream error handling
                # future.set_exception(e)
                raise e

    def pause(self):
        """
        Pause all pending and future download operations.

        Clears the internal pause event, causing all current and future workers
        to block at their pause points until resume() is called. Workers already
        inside the semaphore (actively downloading) will continue until completion.
        """
        self._pause_event.clear()

    def resume(self):
        """
        Resume paused download operations.

        Sets the internal pause event, unblocking all workers waiting at pause
        points and allowing new submissions to proceed normally.
        """
        self._pause_event.set()
