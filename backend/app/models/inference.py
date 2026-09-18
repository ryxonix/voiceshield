"""
VoiceShield AI — ONNX Runtime Inference Wrapper
Thread-safe singleton for AASIST-L model inference with latency monitoring.
"""

import os
import time
import logging
import threading
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


class AASISTInference:
    """
    Thread-safe singleton wrapper around ONNX Runtime InferenceSession.

    Configured for CPU execution with:
        - CPUExecutionProvider
        - intra_op_num_threads=2
        - graph_optimization_level=ORT_ENABLE_ALL

    If the ONNX model file is not found, returns a fallback probability of 0.5
    to allow the system to function without a trained model.
    """

    _instance: Optional["AASISTInference"] = None
    _lock = threading.Lock()

    def __init__(self, model_path: str, num_threads: int = 2):
        self._session = None
        self._model_path = model_path
        self._num_threads = num_threads
        self._input_name = "audio_input"
        self._fallback = True

        try:
            import onnxruntime as ort

            if not os.path.exists(model_path):
                logger.warning(
                    f"ONNX model not found at '{model_path}'. "
                    "Using fallback probability (0.5). "
                    "Run `python -m app.models.export_onnx` to generate."
                )
                return

            # Configure session options
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = num_threads
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.log_severity_level = 3  # Suppress verbose ONNX Runtime logs

            self._session = ort.InferenceSession(
                model_path,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            self._fallback = False
            logger.info(
                f"ONNX model loaded: {model_path} "
                f"(threads={num_threads}, provider=CPU)"
            )

        except ImportError:
            logger.warning("onnxruntime not installed. Using fallback inference.")
        except Exception as e:
            logger.warning(f"Failed to load ONNX model: {e}. Using fallback.")

    @classmethod
    def get_instance(cls, model_path: str = None, num_threads: int = 2) -> "AASISTInference":
        """Get or create the singleton inference instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if model_path is None:
                        from app.config import settings
                        model_path = settings.onnx_model_path
                        num_threads = settings.onnx_threads
                    cls._instance = cls(model_path, num_threads)
        return cls._instance

    def predict(self, audio_window: np.ndarray) -> float:
        """
        Run AASIST-L inference on an audio window.

        Args:
            audio_window: 1D numpy array of int16 PCM samples
                          (typically 4800 samples = 300ms @ 16kHz).

        Returns:
            Probability score ∈ [0.0, 1.0] where 1.0 = synthetic/spoof.
        """
        t_start = time.perf_counter()

        if self._fallback:
            # Return neutral probability when no model is available
            return 0.5

        try:
            # Normalize int16 → float32 [-1, 1]
            audio_float = audio_window.astype(np.float32) / 32768.0

            # Reshape to [1, 1, N] (batch=1, channel=1, samples)
            input_tensor = audio_float.reshape(1, 1, -1)

            # Run inference
            output = self._session.run(None, {self._input_name: input_tensor})
            probability = float(output[0].flatten()[0])

            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.debug(f"AASIST inference: {elapsed_ms:.1f}ms, prob={probability:.4f}")

            return float(np.clip(probability, 0.0, 1.0))

        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return 0.5
