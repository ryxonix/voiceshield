"""
VoiceShield AI — gRPC Server Bootstrap (A1)

Async (aio) gRPC server so a bank / operator can place the VoiceShield
integration on its own port (default `settings.grpc_port` = 50051) without
touching the REST app. The servicer registered here is the exact
`VoiceShield` RPC surface from `backend/sdk/voiceshield.proto`, backed by the
same engine / context / risk / mitigation / ledger / store modules as REST.

Run standalone:
    python -m app.grpc.server            # serves on settings.grpc_port
    python -m app.grpc.server --port 5051 --host 127.0.0.1

Or wire it into the FastAPI lifespan (see `app/main.py`) which starts and
stops the server automatically alongside the REST app:
    from app.grpc.server import create_server, serve
    server = await create_server(settings.grpc_port, settings.grpc_host)
    await server.start(); await server.wait_for_termination()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import grpc

logger = logging.getLogger("voiceshield.grpc.server")


def create_server(
    port: Optional[int] = None,
    host: Optional[str] = None,
) -> grpc.aio.Server:
    """Build a configured `grpc.aio.Server` with the VoiceShield servicer.

    :param port: bind port (default `settings.grpc_port` = 50051)
    :param host: bind host (default `settings.grpc_host` = 0.0.0.0)
    Returns an unstarted server; callers decide whether to `.start()` it
    directly or add it as a real-server TLS/intercept layer.

    The server carries a ``_vs_bound`` int attribute set to the port actually
    bound (0 when the requested port was already in use / could not be bound)
    so an app lifecycle can start it only when the bind succeeded and fail
    gracefully otherwise.
    """
    from app.config import settings
    from app.grpc.servicer import register

    port = port or settings.grpc_port
    host = host or settings.grpc_host

    server = grpc.aio.server(
        maximum_concurrent_rpcs=50,
        options=[
            ("grpc.max_send_message_length", 64 * 1024 * 1024),     # 64 MB audio
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),   # 64 MB audio
            ("grpc.keepalive_time_ms", 30000),
            ("grpc.keepalive_timeout_ms", 10000),
        ],
    )
    register(server)
    try:
        server._vs_bound = server.add_insecure_port(f"{host}:{port}")
    except Exception as e:  # pragma: no cover - bind errors are platform quirks
        logger.warning(f"gRPC bind to {host}:{port} failed: {e}")
        server._vs_bound = 0
    if not server._vs_bound:
        logger.warning(
            f"gRPC port {port} is already in use on {host} — the standalone "
            f"VoiceShield gRPC listener will not be started here."
        )
    else:
        logger.info(f"gRPC server prepared: listening on {host}:{port}")
    return server


async def serve(port: Optional[int] = None, host: Optional[str] = None) -> None:
    """Run the gRPC server until the process is stopped (for `python -m`)."""
    server = create_server(port=port, host=host)
    await server.start()
    logger.info("gRPC server started (VoiceShield AI).")
    await server.wait_for_termination()


async def stop(server: grpc.aio.Server, grace: float = 5.0) -> None:
    """Gracefully stop an aio gRPC server (drain in-flight RPCs)."""
    await server.stop(grace)
    logger.info("gRPC server stopped.")
    # Ensure the asyncio event loop refunds its pollers.
    await asyncio.sleep(0.01)


if __name__ == "__main__":  # pragma: no cover
    import argparse

    from app.config import settings

    ap = argparse.ArgumentParser(description="Run the VoiceShield AI gRPC server.")
    ap.add_argument("--host", default=settings.grpc_host)
    ap.add_argument("--port", type=int, default=settings.grpc_port)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve(port=args.port, host=args.host))
