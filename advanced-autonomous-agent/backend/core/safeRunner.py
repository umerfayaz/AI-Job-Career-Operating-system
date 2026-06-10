import asyncio
import traceback
from typing import Callable, Any, Awaitable, Optional


class SafeRunner:
    def __init__(self, event_bus, max_concurrent_task: int =10):
        self.event_bus = event_bus
        self.max_concurrent_task = max_concurrent_task
        self._semaphore = None
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def run(
        self,
        name: str,
        func: Callable[..., Awaitable[Any]],
        *args,
        severity: str = "warning",
        issue: Optional[str] = None,
        source: Optional[str] = None,
        **kwargs
    ):
        """Runs any async function safely and emits SYSTEM_ERROR on failure."""
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            tb = traceback.format_exc()
            await self.event_bus.emit_error(
                source= source or name,
                issue = issue or f"{name}_crash",
                error=e,
                severity=severity,
                payload={"traceback": tb, "args": str(args), "kwrags": str(kwargs)}
            )
            return None
    
    def _get_semaphore(self):
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_task)
        return self._semaphore

    def create_task(self, name: str, coro: Awaitable[Any], severity= "warning", issue: Optional[str] = None, source: str = "system"):
        if name in self._active_tasks:
            existing =self._active_tasks[name]
            if not existing.done():
                self.event_bus.emit_error(
                    source=source,
                    issue=f"{name}_duplicate_skipped",
                    error=Exception(f"Task {name} already running"),
                    severity="warning",
                    payload={"name": name}
                )
                return existing
            
        async def _wrapped():
            async with self._get_semaphore():
                return await coro
            
        task = asyncio.create_task(_wrapped())
        self._active_tasks[name] = task

        def _done_callback(t: asyncio.Task):
            self._active_tasks.pop(name, None)
            try:
                exc = t.exception()
                if exc:
                    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                    asyncio.create_task(
                        self.event_bus.emit_error(
                            source=source or name,
                            issue=issue or f"{name}_background_crash",
                            error=exc,
                            severity=severity,
                            payload={"traceback": tb},
                        )
                    )
            except asyncio.CancelledError:

                return
            except Exception:
                return

        task.add_done_callback(_done_callback)
        return task



