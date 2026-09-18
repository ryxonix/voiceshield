"""
VoiceShield AI — AASIST-L Model Architecture
Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Network.
Lightweight variant (~85K parameters) for real-time CPU inference.

Reference: Jung et al., "AASIST: Audio Anti-Spoofing using Integrated
Spectro-Temporal Graph Attention Networks" (ICASSP 2022).
"""

import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class SincConv(nn.Module):
    """
    Learnable sinc-function bandpass filterbank operating on raw waveform.
    Parameterized by center frequencies and bandwidths, initialized with
    mel-scale spacing from 50 Hz to 7000 Hz.
    """

    def __init__(self, num_filters: int = 70, kernel_size: int = 129,
                 sample_rate: int = 16000, min_freq: float = 50.0,
                 max_freq: float = 7000.0):
        super().__init__()
        self.num_filters = num_filters
        self.kernel_size = kernel_size
        self.sample_rate = sample_rate

        # Initialize center frequencies on mel scale
        mel_min = 2595 * math.log10(1 + min_freq / 700)
        mel_max = 2595 * math.log10(1 + max_freq / 700)
        mel_points = torch.linspace(mel_min, mel_max, num_filters + 2)
        hz_points = 700 * (10 ** (mel_points / 2595) - 1)

        # Learnable parameters: low and high cutoff frequencies
        self.low_hz = nn.Parameter(hz_points[:-2].clone())
        self.band_hz = nn.Parameter((hz_points[2:] - hz_points[:-2]).clone())

        # Hamming window (fixed)
        n = torch.arange(0, kernel_size).float()
        self.register_buffer(
            'window',
            0.54 - 0.46 * torch.cos(2 * math.pi * n / (kernel_size - 1))
        )
        # Time axis for sinc computation
        n_ = (kernel_size - 1) / 2.0
        self.register_buffer('n', 2 * math.pi * (torch.arange(0, kernel_size).float() - n_) / sample_rate)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, 1, T] raw waveform
        Returns:
            [B, num_filters, T'] filtered output
        """
        low = torch.abs(self.low_hz) + 1.0
        high = low + torch.abs(self.band_hz)
        high = torch.maximum(high, low + 1.0)
        high = torch.minimum(high, torch.tensor(self.sample_rate / 2.0, device=high.device))

        # Sinc bandpass: sinc(2f_high t) - sinc(2f_low t)
        f_low = low.unsqueeze(1) * self.n.unsqueeze(0)   # [F, K]
        f_high = high.unsqueeze(1) * self.n.unsqueeze(0)

        # sinc function with epsilon to avoid division by zero
        bp_low = torch.sin(f_low) / (f_low + 1e-7)
        bp_high = torch.sin(f_high) / (f_high + 1e-7)

        # Bandpass = highpass - lowpass
        band_pass = bp_high - bp_low
        band_pass = band_pass * self.window.unsqueeze(0)

        # Normalize energy
        band_pass = band_pass / (2 * (high - low).unsqueeze(1) + 1e-7)

        # Conv1d with sinc filters
        filters = band_pass.unsqueeze(1)  # [F, 1, K]
        return F.conv1d(x, filters, padding=self.kernel_size // 2)


class ResidualBlock(nn.Module):
    """Lightweight residual block with BatchNorm and LeakyReLU."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.skip = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()
        self.act = nn.LeakyReLU(0.2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.skip(x)
        out = self.act(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return self.act(out + residual)


class GraphAttention(nn.Module):
    """
    Single-head graph attention layer for modeling inter-node relationships.
    Used for both spectral (band-to-band) and temporal (frame-to-frame) attention.
    """

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.W = nn.Linear(in_dim, out_dim, bias=False)
        self.a = nn.Linear(2 * out_dim, 1, bias=False)
        self.act = nn.LeakyReLU(0.2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, N, D] — N nodes with D features each
        Returns:
            [B, N, out_dim] — attention-updated node features
        """
        B, N, D = x.shape
        h = self.W(x)  # [B, N, out_dim]

        # Compute pairwise attention scores
        hi = h.unsqueeze(2).expand(-1, -1, N, -1)  # [B, N, N, out_dim]
        hj = h.unsqueeze(1).expand(-1, N, -1, -1)  # [B, N, N, out_dim]
        e = self.act(self.a(torch.cat([hi, hj], dim=-1)).squeeze(-1))  # [B, N, N]

        alpha = F.softmax(e, dim=-1)  # [B, N, N]
        out = torch.bmm(alpha, h)     # [B, N, out_dim]

        return self.act(out)


class AASIST_L(nn.Module):
    """
    AASIST-L: Lightweight Audio Anti-Spoofing with Integrated
    Spectro-Temporal Graph Attention Network.

    Target: ~85K parameters for sub-50ms CPU inference.

    Architecture:
        1. SincConv front-end → learnable bandpass filters on raw waveform
        2. Residual encoder → compact feature maps
        3. Parallel GAT: Spectral (band-to-band) + Temporal (frame-to-frame)
        4. Heterogeneous pooling → merged representation
        5. Readout MLP → sigmoid probability
    """

    def __init__(
        self,
        num_sinc_filters: int = 70,
        sinc_kernel: int = 129,
        encoder_width: int = 32,
        gat_dim: int = 32,
        sample_rate: int = 16000,
    ):
        super().__init__()

        # Stage 1: SincConv front-end
        self.sinc = SincConv(
            num_filters=num_sinc_filters,
            kernel_size=sinc_kernel,
            sample_rate=sample_rate,
        )

        # Stage 2: Residual encoder
        self.encoder = nn.Sequential(
            ResidualBlock(num_sinc_filters, encoder_width),
            nn.MaxPool1d(4),
            ResidualBlock(encoder_width, encoder_width),
            nn.AdaptiveAvgPool1d(64),  # Fix temporal dim to 64
        )

        # Stage 3a: Spectral GAT (band-to-band)
        # Reshape encoder output [B, C, T] → [B, C, T] → treat C as nodes
        self.spectral_gat = GraphAttention(64, gat_dim)  # 64 = temporal dim

        # Stage 3b: Temporal GAT (frame-to-frame)
        # Treat T as nodes
        self.temporal_gat = GraphAttention(encoder_width, gat_dim)

        # Stage 4: Heterogeneous pooling
        # Spectral: [B, C, gat_dim] → pool over C → [B, gat_dim]
        # Temporal: [B, T, gat_dim] → pool over T → [B, gat_dim]
        self.het_pool = nn.Linear(gat_dim * 2, gat_dim)

        # Stage 5: Readout MLP
        self.readout = nn.Sequential(
            nn.Linear(gat_dim, gat_dim),
            nn.LeakyReLU(0.2),
            nn.Linear(gat_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, 1, T] raw waveform (T can vary, e.g. 4800 for 300ms @ 16kHz)
        Returns:
            [B, 1] probability score where 1 = synthetic/spoof
        """
        # Stage 1: SincConv → [B, 70, T]
        h = self.sinc(x)

        # Stage 2: Encoder → [B, 32, 64]
        h = self.encoder(h)
        B, C, T = h.shape

        # Stage 3a: Spectral GAT — treat channels (freq bands) as graph nodes
        # [B, C, T] → [B, C, T] (C nodes, T features each)
        h_spec = self.spectral_gat(h)           # [B, C, gat_dim]
        h_spec = h_spec.mean(dim=1)              # [B, gat_dim] — pool over freq

        # Stage 3b: Temporal GAT — treat time frames as graph nodes
        # [B, C, T] → [B, T, C] (T nodes, C features each)
        h_temp = self.temporal_gat(h.transpose(1, 2))  # [B, T, gat_dim]
        h_temp = h_temp.mean(dim=1)              # [B, gat_dim] — pool over time

        # Stage 4: Heterogeneous pooling
        h_fused = torch.cat([h_spec, h_temp], dim=-1)  # [B, gat_dim*2]
        h_fused = F.leaky_relu(self.het_pool(h_fused), 0.2)  # [B, gat_dim]

        # Stage 5: Readout
        return self.readout(h_fused)  # [B, 1]


def create_aasist_l(sample_rate: int = 16000) -> AASIST_L:
    """Factory function to create an AASIST-L model."""
    return AASIST_L(sample_rate=sample_rate)


def get_param_count(model: nn.Module) -> int:
    """Count total trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    model = create_aasist_l()
    print(f"AASIST-L Parameter Count: {get_param_count(model):,}")

    # Test forward pass
    dummy = torch.randn(1, 1, 4800)  # 300ms @ 16kHz
    output = model(dummy)
    print(f"Input shape:  {dummy.shape}")
    print(f"Output shape: {output.shape}")
    print(f"Output value: {output.item():.4f}")
