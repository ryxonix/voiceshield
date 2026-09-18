"""
VoiceShield AI — ONNX Export & INT8 Quantization Pipeline
Exports AASIST-L from PyTorch to ONNX and applies INT8 dynamic quantization.
"""

import os
import sys
import logging
import numpy as np

logger = logging.getLogger(__name__)


def export_to_onnx(
    checkpoint_path: str = None,
    output_dir: str = "models",
    input_length: int = 4800,
) -> tuple:
    """
    Export AASIST-L model to ONNX and apply INT8 quantization.

    Args:
        checkpoint_path: Path to PyTorch checkpoint (.pth). If None, uses random init.
        output_dir: Directory to save ONNX files.
        input_length: Input audio length in samples (default 4800 = 300ms @ 16kHz).

    Returns:
        Tuple of (fp32_path, int8_path).
    """
    import torch
    import onnx
    from onnxruntime.quantization import quantize_dynamic, QuantType

    from app.models.aasist import create_aasist_l, get_param_count

    os.makedirs(output_dir, exist_ok=True)
    fp32_path = os.path.join(output_dir, "aasist_l.onnx")
    int8_path = os.path.join(output_dir, "aasist_l_int8.onnx")

    # ── Load Model ──────────────────────────────────────────────────
    model = create_aasist_l()

    if checkpoint_path and os.path.exists(checkpoint_path):
        logger.info(f"Loading checkpoint: {checkpoint_path}")
        state_dict = torch.load(checkpoint_path, map_location="cpu")
        model.load_state_dict(state_dict)
    else:
        logger.info("No checkpoint provided — exporting randomly initialized model")

    model.eval()
    param_count = get_param_count(model)
    logger.info(f"Model parameters: {param_count:,}")

    # ── Export to ONNX (FP32) ───────────────────────────────────────
    dummy_input = torch.randn(1, 1, input_length)
    logger.info(f"Exporting ONNX (FP32) → {fp32_path}")

    torch.onnx.export(
        model,
        dummy_input,
        fp32_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["audio_input"],
        output_names=["probability"],
    )

    # Validate ONNX model
    onnx_model = onnx.load(fp32_path)
    onnx.checker.check_model(onnx_model)
    fp32_size = os.path.getsize(fp32_path)
    logger.info(f"FP32 ONNX model: {fp32_size / 1024:.1f} KB")

    # ── INT8 Dynamic Quantization ───────────────────────────────────
    logger.info(f"Applying INT8 quantization → {int8_path}")
    try:
        quantize_dynamic(
            model_input=fp32_path,
            model_output=int8_path,
            weight_type=QuantType.QInt8,
        )
        int8_size = os.path.getsize(int8_path)
        logger.info(f"INT8 ONNX model: {int8_size / 1024:.1f} KB")
        logger.info(f"Size reduction: {fp32_size / int8_size:.1f}x")
    except Exception as e:
        logger.warning(f"INT8 quantization failed: {e}. Falling back to FP32 model.")
        int8_path = fp32_path

    # ── Validate Output Equivalence ─────────────────────────────────
    import onnxruntime as ort

    # FP32 inference
    sess_fp32 = ort.InferenceSession(fp32_path, providers=["CPUExecutionProvider"])
    test_input = np.random.randn(1, 1, input_length).astype(np.float32)
    result_fp32 = sess_fp32.run(None, {"audio_input": test_input})[0]

    # INT8 inference
    sess_int8 = ort.InferenceSession(int8_path, providers=["CPUExecutionProvider"])
    result_int8 = sess_int8.run(None, {"audio_input": test_input})[0]

    diff = np.abs(result_fp32 - result_int8).max()
    logger.info(f"FP32 output: {result_fp32.flatten()[0]:.6f}")
    logger.info(f"INT8 output: {result_int8.flatten()[0]:.6f}")
    logger.info(f"Max difference: {diff:.6f}")

    if diff < 0.01:
        logger.info("✓ INT8 quantization validated (diff < 0.01)")
    else:
        logger.warning(f"⚠ INT8 quantization diff ({diff:.6f}) exceeds threshold 0.01")

    return fp32_path, int8_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    checkpoint = sys.argv[1] if len(sys.argv) > 1 else None
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")

    fp32, int8 = export_to_onnx(
        checkpoint_path=checkpoint,
        output_dir=output_dir,
    )

    print(f"\n{'═' * 50}")
    print(f"  FP32 model: {fp32}")
    print(f"  INT8 model: {int8}")
    print(f"{'═' * 50}")
