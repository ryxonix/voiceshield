"""
VoiceShield AI — Ring Buffer Unit Tests
Tests the NumPy-based ring buffer for streaming audio processing.
"""

import numpy as np
import pytest
from app.engine.ring_buffer import RingBuffer


class TestRingBuffer:
    """Tests for the streaming audio ring buffer."""

    def test_init_defaults(self):
        """Buffer initializes with correct defaults (300ms window, 100ms hop)."""
        rb = RingBuffer()
        assert rb.window_size == 4800
        assert rb.hop_size == 1600

    def test_init_custom(self):
        """Buffer initializes with custom sizes."""
        rb = RingBuffer(window_size=1000, hop_size=500)
        assert rb.window_size == 1000
        assert rb.hop_size == 500

    def test_no_output_before_window_filled(self):
        """No windows emitted before enough samples accumulated."""
        rb = RingBuffer(window_size=4800, hop_size=1600)
        # Push less than one full window
        chunk = np.zeros(3200, dtype=np.int16)
        windows = rb.push(chunk)
        assert len(windows) == 0

    def test_first_window_emitted(self):
        """First window is emitted exactly when window_size samples arrive."""
        rb = RingBuffer(window_size=4800, hop_size=1600)
        chunk = np.ones(4800, dtype=np.int16) * 100
        windows = rb.push(chunk)
        assert len(windows) == 1
        assert len(windows[0]) == 4800
        assert windows[0].dtype == np.int16

    def test_hop_emits_windows(self):
        """After first window, new windows emitted every hop_size samples."""
        rb = RingBuffer(window_size=4800, hop_size=1600)
        # Fill initial window
        rb.push(np.zeros(4800, dtype=np.int16))
        # Push exactly one hop
        windows = rb.push(np.ones(1600, dtype=np.int16) * 200)
        assert len(windows) == 1
        assert len(windows[0]) == 4800

    def test_large_chunk_multiple_windows(self):
        """A large chunk can produce multiple windows."""
        rb = RingBuffer(window_size=4800, hop_size=1600)
        # Push enough for first window + 2 more hops = 4800 + 3200 = 8000
        chunk = np.ones(8000, dtype=np.int16) * 50
        windows = rb.push(chunk)
        assert len(windows) >= 2

    def test_window_content_correctness(self):
        """Windows contain the correct sample data."""
        rb = RingBuffer(window_size=10, hop_size=5)
        data = np.arange(15, dtype=np.int16)
        windows = rb.push(data)
        # First window should be [0..9], second should be [5..14]
        assert len(windows) == 2
        np.testing.assert_array_equal(windows[0], np.arange(0, 10, dtype=np.int16))
        np.testing.assert_array_equal(windows[1], np.arange(5, 15, dtype=np.int16))

    def test_reset_clears_buffer(self):
        """Reset zeros out all buffer memory (DPDP compliance)."""
        rb = RingBuffer(window_size=4800, hop_size=1600)
        rb.push(np.ones(4800, dtype=np.int16) * 999)
        rb.reset()
        # After reset, need full window_size again
        windows = rb.push(np.zeros(1600, dtype=np.int16))
        assert len(windows) == 0

    def test_small_chunks(self):
        """Buffer works with very small input chunks."""
        rb = RingBuffer(window_size=100, hop_size=50)
        all_windows = []
        for i in range(20):
            chunk = np.full(10, i, dtype=np.int16)
            all_windows.extend(rb.push(chunk))
        # After 200 samples with window=100 hop=50, should have multiple windows
        assert len(all_windows) >= 2

    def test_dtype_preserved(self):
        """Output windows maintain int16 dtype."""
        rb = RingBuffer(window_size=100, hop_size=50)
        windows = rb.push(np.zeros(100, dtype=np.int16))
        assert windows[0].dtype == np.int16
