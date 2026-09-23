"""
Shared pytest fixtures for the VoiceShield backend suite.

The NBF/Fabric external anchor is MANDATORY by default at the system level
(BLOCKCHAIN_EXTERNAL_ANCHOR=true + BLOCKCHAIN_ANCHOR_REQUIRED=true — fail
closed: no anchor, no forensic hand-off). The offline unit/engine suite has no
Fabric node, so the autouse fixture below pins a known fail-open posture for
every default test. **Mandatory-mode** coverage lives in test_mandatory_anchor
tests, which opt back in explicitly by setting the two settings themselves
(after this fixture has run).
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _default_offline_blockchain():
    """Run the default suite without requiring a live NBF/Fabric gateway.

    Saves the configured values and restores them afterwards so a developer
    who runs pytest with the mandatory posture in their environment still gets
    those values back for non-autouse reasoning (and for test sessions that
    want to inspect `settings` post-suite).
    """
    saved_external = settings.blockchain_external_anchor
    saved_required = settings.blockchain_anchor_required
    try:
        settings.blockchain_external_anchor = False
        settings.blockchain_anchor_required = False
        yield
    finally:
        settings.blockchain_external_anchor = saved_external
        settings.blockchain_anchor_required = saved_required