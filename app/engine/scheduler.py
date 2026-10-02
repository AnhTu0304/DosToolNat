"""Rate scheduler for controlling request pacing and test duration."""

import asyncio
from typing import AsyncIterator


class RateScheduler:
    """Generates paced ticks at the requested rate (requests/sec) up to duration limit."""

    def __init__(self, rate: float, duration: float) -> None:
        self.rate = max(float(rate), 0.1)
        self.duration = float(duration)
        self.interval = 1.0 / self.rate
        self._stopped = False

    def stop(self) -> None:
        """Signal the scheduler to cease generating ticks immediately."""
        self._stopped = True

    async def generate_ticks(self) -> AsyncIterator[float]:
        """Asynchronously yield ticks at steady intervals with drift compensation."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        end_time = start_time + self.duration
        tick_index = 0

        while not self._stopped:
            now = loop.time()
            if now >= end_time:
                break

            yield now

            if self._stopped:
                break

            tick_index += 1
            target_next_time = start_time + (tick_index * self.interval)
            sleep_duration = target_next_time - loop.time()

            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            else:
                # Slight yield to avoid blocking the event loop on overruns
                await asyncio.sleep(0)
