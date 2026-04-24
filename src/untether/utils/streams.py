from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import anyio
from anyio.abc import ByteReceiveStream
from anyio.streams.buffered import BufferedByteReceiveStream

from ..logging import log_pipeline

_MAX_LINE_BYTES = 10 * 1024 * 1024  # 10 MB — generous for any legitimate JSONL event


async def iter_bytes_lines(stream: ByteReceiveStream) -> AsyncIterator[bytes]:
    buffered = BufferedByteReceiveStream(stream)
    while True:
        try:
            line = await buffered.receive_until(b"\n", _MAX_LINE_BYTES)
        except (anyio.IncompleteRead, anyio.ClosedResourceError):
            return
        yield line


_STDERR_CAPTURE_MAX = 20


async def drain_stderr(
    stream: ByteReceiveStream,
    logger: Any,
    tag: str,
    capture: list[str] | None = None,
) -> None:
    try:
        async for line in iter_bytes_lines(stream):
            text = line.decode("utf-8", errors="replace")
            log_pipeline(
                logger,
                "subprocess.stderr",
                tag=tag,
                line=text,
            )
            if capture is not None and len(capture) < _STDERR_CAPTURE_MAX:
                capture.append(text)
    except Exception as exc:  # noqa: BLE001
        log_pipeline(
            logger,
            "subprocess.stderr.error",
            tag=tag,
            error=str(exc),
        )
