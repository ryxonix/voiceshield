"""
VoiceShield SDK — aio gRPC client resource-ownership parity.

Locks down the fix in `VoiceShieldGrpcAioClient.aclose()`: an aio gRPC channel's
`close()` is a coroutine, so an owned aio channel must be awaited (the sync
`self.close()` path previously emitted `RuntimeWarning: coroutine 'Channel.close'
was never awaited`). Also verifies an externally-supplied channel is *not* closed
by the client (ownership stays with the caller).
"""

import asyncio
import inspect
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))          # backend/tests
BACKEND_ROOT = os.path.normpath(os.path.join(_ROOT, ".."))   # backend
SDK_ROOT = os.path.normpath(os.path.join(_ROOT, "..", "sdk"))  # backend/sdk

# voiceshield_sdk.grpc does `from app.grpc... import _pb2` at import time, so both
# `backend` (for `app`) and `backend/sdk` (for `voiceshield_sdk`) must be importable.
for _p in (BACKEND_ROOT, SDK_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_aclose_is_coroutine_and_awaits_owned_channel():
    from voiceshield_sdk.grpc import VoiceShieldGrpcAioClient

    # Self-built channel => client owns it. aclose() must be awaitable and must
    # actually await the aio channel close, or the close coroutine goes un-awaited.
    assert inspect.iscoroutinefunction(VoiceShieldGrpcAioClient.aclose)

    client = VoiceShieldGrpcAioClient()  # no channel => builds an owned aio channel
    assert client._own_channel is True
    assert inspect.iscoroutinefunction(client._channel.close), (
        "expected an aio channel, whose close() is a coroutine"
    )

    asyncio.run(client.aclose())

    assert client._own_channel is False, "owned channel should be handed back after aclose"


def test_aclose_does_not_close_caller_supplied_channel():
    import grpc.aio
    from voiceshield_sdk.grpc import VoiceShieldGrpcAioClient

    caller_channel = grpc.aio.insecure_channel("127.0.0.1:1")
    client = VoiceShieldGrpcAioClient(channel=caller_channel)

    assert client._own_channel is False, "caller-supplied channel is not owned"

    async def _run():
        await client.aclose()

    asyncio.run(_run())

    # Ownership semantics: the caller built the channel, so the client must not
    # have closed it behind the caller's back.
    assert client._own_channel is False
