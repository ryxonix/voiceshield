"""
VoiceShield AI — Ring Buffer for Streaming Audio
Pre-allocated NumPy ring buffer with sliding window emission.
DPDP Compliant: all memory is overwritten in-place, never copied to disk.
"""

import numpy as np
from typing import List


class RingBuffer:
    """
    Circular buffer that accumulates PCM int16 audio samples and emits
    fixed-size overlapping windows at a configurable hop interval.

    Args:
        window_size: Number of samples per output window (default 4800 = 300ms @ 16kHz).
        hop_size: Number of new samples between consecutive windows (default 1600 = 100ms).
    """

    def __init__(self, window_size: int = 4800, hop_size: int = 1600):
        self.window_size = window_size
        self.hop_size = hop_size
        # Pre-allocated buffer — never dynamically resized
        self.buffer = np.zeros(window_size, dtype=np.int16)
        self.write_pos = 0
        self.samples_since_last_emit = 0
        self._buffer_filled = False  # First window requires full window_size

    def push(self, samples: np.ndarray) -> List[np.ndarray]:
        """
        Push incoming PCM samples into the buffer.

        Args:
            samples: 1D numpy array of int16 PCM samples (any length).

        Returns:
            List of complete windows (each is a copy of window_size int16 samples).
            Usually 0 or 1 windows per push, possibly more for large chunks.
        """
        windows: List[np.ndarray] = []
        n_samples = len(samples)
        read_idx = 0

        while read_idx < n_samples:
            # How many samples we can write before buffer is full
            space_left = self.window_size - self.write_pos
            write_count = min(n_samples - read_idx, space_left)

            # Write into pre-allocated buffer (in-place)
            self.buffer[self.write_pos:self.write_pos + write_count] = \
                samples[read_idx:read_idx + write_count]

            self.write_pos += write_count
            self.samples_since_last_emit += write_count
            read_idx += write_count

            # Check if we have a complete window to emit
            if self.write_pos == self.window_size:
                if not self._buffer_filled:
                    # First window: emit when buffer is fully filled
                    self._buffer_filled = True
                    self.samples_since_last_emit = 0
                    windows.append(self.buffer.copy())
                    # Shift buffer by hop_size for overlap
                    self.buffer[:-self.hop_size] = self.buffer[self.hop_size:]
                    self.write_pos = self.window_size - self.hop_size
                elif self.samples_since_last_emit >= self.hop_size:
                    # Subsequent windows: emit every hop_size new samples
                    self.samples_since_last_emit -= self.hop_size
                    windows.append(self.buffer.copy())
                    # Shift buffer for next window (66% overlap)
                    self.buffer[:-self.hop_size] = self.buffer[self.hop_size:]
                    self.write_pos = self.window_size - self.hop_size

        return windows

    def reset(self) -> None:
        """
        Zero out all buffer memory and reset state.
        DPDP compliance: ensures no audio data persists in RAM.
        """
        self.buffer.fill(0)
        self.write_pos = 0
        self.samples_since_last_emit = 0
        self._buffer_filled = False
