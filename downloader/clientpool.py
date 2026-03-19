"""
ClientPool module for managing multiple HTTP client accounts with rate limiting and health tracking.

This module provides a ClientPool class that manages a pool of Pixiv accounts for making
HTTP requests. It handles account initialization, health monitoring, rate limiting, automatic
failover between accounts, and graceful shutdown. The pool supports a primary account plus
multiple backup accounts for load distribution.
"""

import asyncio
import random
from typing import Optional
from time import time
import httpx
from data import PixivAccount, AccountStatus


class ClientPool:
    """
    A connection pool manager for multiple Pixiv HTTP client accounts.

    This class manages a collection of `httpx.AsyncClient` instances backed by different
    Pixiv accounts. It provides automatic account health monitoring, rate limiting
    protection, request interval management, and failover capabilities. The pool
    maintains one primary account and multiple secondary accounts for distribution.

    Attributes:
        BASE_HEADERS: Default HTTP headers used for all requests.
        config: Configuration handler for reading/updating settings.
        logger: Logger instance for operational logging.
        request_interval: Minimum time between requests to the same account (seconds).
        _limits: httpx.Limits for connection pooling configuration.
        _timeout: httpx.Timeout for request timeout settings.
        _proxy: Optional httpx.Proxy for routing requests through a proxy.
        _primary: The primary PixivAccount used for critical operations.
        _accounts: List of secondary PixivAccount instances for load distribution.
        _lock: asyncio.Lock for thread-safe initialization and shutdown.
        _shutdown_event: asyncio.Event signaling pool shutdown status.
        _initialized: Boolean flag indicating if initialize() has completed.
        _closed: Boolean flag indicating if shutdown() has completed.
    """

    BASE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Referer": "https://www.pixiv.net/",
    }

    def __init__(self, config_handler, logger):
        """
        Initialize the ClientPool with configuration and logging dependencies.

        This constructor sets up the basic configuration but does not initialize
        accounts. Call initialize() to create and validate account clients.

        Args:
            config_handler: Configuration object with require() and get() methods
                           for accessing clientpool_config settings.
            logger: Logger object with info() and warning() methods for logging.
        """
        self.config = config_handler
        self.logger = logger
        self.request_interval: float = config_handler.require(
            "clientpool_config.request_interval"
        )

        self._limits = httpx.Limits(
            max_connections=config_handler.require("clientpool_config.max_connections"),
        )
        self._timeout = httpx.Timeout(10, read=25)

        # Configure proxy if enabled in settings
        if config_handler.require("clientpool_config.proxy.enable"):
            self._proxy = httpx.Proxy(
                config_handler.require("clientpool_config.proxy.url")
            )
        else:
            self._proxy = None

        self._primary: Optional[PixivAccount] = None
        self._accounts: list[PixivAccount] = []

        self._lock = asyncio.Lock()
        self._acc_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()

        self._initialized = False
        self._closed = False

    async def initialize(self):
        """
        Initialize all account clients and validate their availability.

        This method creates `httpx.AsyncClient` instances for the primary account
        and all pool accounts, tests their validity by making a test request,
        and stores valid accounts for later use. Must be called before making
        any requests. Thread-safe via _lock.

        Raises:
            RuntimeError: If the primary account is not available or invalid.
        """
        async with self._lock:

            if self._initialized:
                return

            self.logger.info("Initializing ClientPool...")

            primary_cfg = self.config.require("clientpool_config.primary_account")
            pool_cfg = self.config.get("clientpool_config.client_pool", [])

            if primary_cfg:
                self._primary = await self._build_account(primary_cfg)

            for cfg in pool_cfg:
                account = await self._build_account(cfg)
                if account:
                    self._accounts.append(account)

            if not self._primary:
                raise RuntimeError("Primary account not available")

            self._initialized = True
            self.logger.info("ClientPool initialized.")

    async def _build_account(self, cfg) -> Optional[PixivAccount]:
        """
        Build and validate a PixivAccount from configuration.

        Creates an `httpx.AsyncClient` with the configured cookies and settings,
        tests the account validity by making a request to Pixiv settings page,
        and returns a PixivAccount object if valid.

        Args:
            cfg: Configuration dictionary containing 'cookies' and optionally 'email'.

        Returns:
            Optional[PixivAccount]: A validated PixivAccount instance, or None if the account is invalid.
        """

        cookies = cfg["cookies"]

        client = httpx.AsyncClient(
            headers=self.BASE_HEADERS,
            cookies=cookies,
            proxy=self._proxy,
            timeout=self._timeout,
            limits=self._limits,
        )

        if not await self._test_account(client):
            self.logger.warning(f"Invalid account: {cfg.get('email')}")
            return None

        return PixivAccount(
            email=cfg.get("email"),
            cookies=cookies,
            client=client,
            last_request_time=0,
        )

    async def _test_account(self, client: httpx.AsyncClient) -> bool:
        """
        Test if an account is valid by making a request to Pixiv settings page.

        A valid account should return HTTP 200 when accessing the account settings.
        This indicates the cookies are valid and the session is active.

        Args:
            client: The h`ttpx.AsyncClient` instance to test, configured with account cookies.

        Returns:
            True if the account returns HTTP 200, False otherwise.
        """
        try:
            resp = await client.get("https://www.pixiv.net/settings/account")
        except httpx.HTTPError as e:
            if isinstance(e, httpx.ConnectError):
                self.logger.warning("Proxy error. Please check your proxy!")
            else:
                self.logger.exception(e)
            return False
        return resp.status_code == 200

    async def _get_account(self, use_primary: bool) -> tuple[PixivAccount, float]:
        """
        Select an available account for making a request.

        This method implements the account selection logic:
        - If use_primary is True, returns the primary account (if healthy)
        - Otherwise, selects the healthy pool account with the earliest last_request_time
        - Automatically resumes rate-limited accounts after their cooldown period
        - Enforces request_interval by sleeping if necessary
        - Use primary account if no healthy pool account available

        Args:
            use_primary: If True, force using the primary account. If False, select
                        from the pool of secondary accounts.

        Returns:
            A PixivAccount ready to make a request (rate limiting wait already applied).

        Raises:
            RuntimeError: If ClientPool is not initialized, or if primary
                        account is unavailable or unhealthy.
        """
        async with self._acc_lock:

            if not self._initialized:
                raise RuntimeError("ClientPool not initialized")

            now = time()

            if use_primary:
                if not self._primary:
                    raise RuntimeError("Primary account not configured")
                if self._primary.status != AccountStatus.HEALTHY:
                    raise RuntimeError("Primary account unuseable")
                account = self._primary
            else:
                healthy: list[PixivAccount] = []
                for acc in self._accounts:
                    if acc.status == AccountStatus.HEALTHY:
                        healthy.append(acc)
                    elif acc.status == AccountStatus.RATE_LIMITED:
                        # Resume rate limited account
                        if now > acc.wait_until:
                            acc.status = AccountStatus.HEALTHY
                            healthy.append(acc)

                if len(healthy) == 0:
                    self.logger.warning(
                        "No healthy pool accounts, use primary account instead!"
                    )
                    account, _ = await self._get_account(use_primary=True)
                    # raise RuntimeError("No healthy pool accounts")

                else:
                    account = min(healthy, key=lambda a: a.last_request_time)

            # Waiting for the necessary time to avoid Pixiv rate limit
            wait = max(0, self.request_interval - (now - account.last_request_time))
            account.last_request_time = now + wait

            return account, wait

    async def request(
        self,
        method: str,
        url: str,
        use_primary: bool = False,
        retries=3,
        **kwargs,
    ) -> Optional[httpx.Response]:
        """
        Make an HTTP request using an available account from the pool.

        This method handles account selection, request execution, response handling,
        and automatic error recovery. It monitors account health status, handles
        rate limiting (429), authentication failures (401/403), and implements
        automatic retry with backoff for transient failures.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Target URL for the request.
            use_primary: If True, use the primary account instead of pool accounts.
            **kwargs: Additional arguments passed to httpx.AsyncClient.request().

        Returns:
            Optional[httpx.Response]: The httpx.Response object from the
            successful request, or None if any error raised.

        Raises:
            RuntimeError: If the ClientPool is closed or shutting down.
        """

        if self._closed:
            raise RuntimeError("ClientPool already closed")

        while not self._shutdown_event.is_set():
            if retries == 0:
                return

            account, wait = await self._get_account(use_primary)
            if wait > 0:
                # Sleep during the request step to avoid
                # get_account being suspended due to acc_lock.
                await asyncio.sleep(wait)

            try:
                response = await account.client.request(
                    method, url, **kwargs, cookies=account.cookies
                )

                if response.is_success:
                    account.fail_count = 0

                if response.status_code in (401, 403):
                    account.status = AccountStatus.INVALID
                    self.logger.warning(
                        "Account %s now invalid. Check cookies!" % account.email
                    )
                    # raise RuntimeError(f"Account invalid: {account.email}")

                if response.status_code == 429:
                    account.status = AccountStatus.RATE_LIMITED
                    self.logger.warning(
                        """Account %s has reached Pixiv request rate limit. Please increase 
                        the request_interval in config file or add a new account!"""
                        % account.email
                    )
                    await self.update_request_interval(1)
                    cooldown = random.randint(80, 180)
                    account.wait_until = time() + cooldown

                return response

            except httpx.HTTPError as e:
                retries -= 1
                account.fail_count += 1
                if account.fail_count >= 5:
                    account.status = AccountStatus.INVALID

                if isinstance(e, httpx.ConnectError):
                    self.logger.warning("Proxy error. Please check your proxy!")
                elif isinstance(e, httpx.ConnectTimeout):
                    self.logger.warning(
                        "Connection timed out, please check your network connection!"
                    )

        raise RuntimeError("ClientPool shutting down")

    async def update_request_interval(self, add_interval: float):
        # Auto-adjust request interval to prevent further rate limiting
        async with self._lock:
            self.request_interval += add_interval
            self.config.update(
                "clientpool_config.request_interval", self.request_interval
            )
            self.logger.info(
                "The configuration request_interval has been automatically increased."
            )

    async def shutdown(self):
        """
        Gracefully shut down the ClientPool and close all HTTP clients.

        Sets the shutdown event to stop new requests, closes all httpx.AsyncClient
        instances for both primary and pool accounts, and marks the pool as closed.
        Thread-safe via _lock. Idempotent - safe to call multiple times.
        """
        async with self._lock:
            if self._closed:
                return

            self.logger.info("Shutting down ClientPool...")

            self._shutdown_event.set()

            # Close all client connections
            if self._primary:
                await self._primary.client.aclose()
            for account in self._accounts:
                await account.client.aclose()

            self._closed = True
            self.logger.info("ClientPool closed.")
