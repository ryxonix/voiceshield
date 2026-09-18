"""
VoiceShield AI — ASVspoof Dataset Loader
Loads ASVspoof 2019/2021 LA datasets with optional augmentation.
"""

import os
import logging
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)


class ASVspoofDataset(Dataset):
    """
    PyTorch Dataset for ASVspoof LA (Logical Access) challenge data.

    Protocol file format (space-separated):
        SPEAKER_ID AUDIO_FILE_ID - ATTACK_TYPE LABEL
        LA_0001 LA_E_1000001 - - bonafide
        LA_0001 LA_E_1000002 - A01 spoof

    Labels: 0 = bonafide (genuine), 1 = spoof (synthetic/deepfake)
    """

    def __init__(
        self,
        root_dir: str,
        protocol_file: str,
        augmentor=None,
        target_length: int = 64000,
        sample_rate: int = 16000,
    ):
        self.root_dir = root_dir
        self.augmentor = augmentor
        self.target_length = target_length
        self.sample_rate = sample_rate
        self.items = []

        if not os.path.exists(protocol_file):
            logger.warning(f"Protocol file not found: {protocol_file}")
            return

        with open(protocol_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    speaker, file_id = parts[0], parts[1]
                    label_str = parts[4]
                    label = 0 if label_str.lower() == "bonafide" else 1

                    # Try .flac first, then .wav
                    file_path = os.path.join(root_dir, f"{file_id}.flac")
                    if not os.path.exists(file_path):
                        file_path = os.path.join(root_dir, f"{file_id}.wav")

                    self.items.append((file_path, label))

        logger.info(f"  Pre-loading {len(self.items)} audio files into RAM cache...")
        import soundfile as sf
        self.cache = []  # list of (audio_float32, label, actual_sr)
        for file_path, label in self.items:
            try:
                audio, actual_sr = sf.read(file_path, dtype="float32")
                if audio.ndim > 1:
                    audio = audio.mean(axis=1)
            except Exception:
                audio = np.zeros(self.target_length, dtype=np.float32)
                actual_sr = self.sample_rate
            self.cache.append((audio, label, actual_sr))

        logger.info(
            f"Loaded & cached {len(self.cache)} samples from {protocol_file} "
            f"({sum(1 for _, l, _sr in self.cache if l == 0)} bonafide, "
            f"{sum(1 for _, l, _sr in self.cache if l == 1)} spoof)"
        )

    def __len__(self) -> int:
        return len(self.cache)

    def __getitem__(self, idx: int):
        audio, label, actual_sr = self.cache[idx]

        # Apply augmentation using the file's actual sample rate
        if self.augmentor is not None:
            # Temporarily update augmentor sr for rate-adaptive filters
            old_sr = self.augmentor.sr
            self.augmentor.sr = actual_sr
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_int16 = self.augmentor.augment_sample(audio_int16)
            self.augmentor.sr = old_sr
            audio = audio_int16.astype(np.float32) / 32768.0

        # Pad or truncate to target length
        if len(audio) > self.target_length:
            # Random crop
            start = np.random.randint(0, len(audio) - self.target_length)
            audio = audio[start : start + self.target_length]
        elif len(audio) < self.target_length:
            audio = np.pad(audio, (0, self.target_length - len(audio)))

        return (
            torch.tensor(audio, dtype=torch.float32).unsqueeze(0),  # [1, T]
            torch.tensor(label, dtype=torch.float32),
        )


def create_dataloaders(config: dict):
    """
    Create train and validation dataloaders from config.

    Config keys:
        train_dir, train_protocol, val_dir, val_protocol, augmentor (optional)
    """
    from training.augmentations import StochasticAugmentor

    augmentor = config.get("augmentor") or StochasticAugmentor()

    train_dataset = ASVspoofDataset(
        config["train_dir"], config["train_protocol"],
        augmentor=augmentor,
    )
    val_dataset = ASVspoofDataset(
        config["val_dir"], config["val_protocol"],
    )

    train_loader = DataLoader(
        train_dataset, batch_size=32, shuffle=True,
        num_workers=0, pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_dataset, batch_size=32, shuffle=False,
        num_workers=0, pin_memory=torch.cuda.is_available(),
    )

    return train_loader, val_loader
