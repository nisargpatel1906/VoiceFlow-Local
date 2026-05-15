"""
VoiceFlow Local - GPU Detection Utility

Detects available GPU hardware using nvidia-smi, PyTorch/CUDA, and (on Windows)
WMI Win32_VideoController so the user can see exactly which device will be used
for Whisper inference before the model loads.
"""

from __future__ import annotations

import subprocess
import sys
from typing import List


# ---------------------------------------------------------------------------
# Public data-class
# ---------------------------------------------------------------------------

class GPUInfo:
    """Describes a single detected GPU."""

    def __init__(
        self,
        name: str,
        driver_version: str = "",
        vram_mb: int = 0,
        cuda_index: int = -1,
        cuda_available: bool = False,
    ):
        self.name = name
        self.driver_version = driver_version
        self.vram_mb = vram_mb
        self.cuda_index = cuda_index
        self.cuda_available = cuda_available

    def __repr__(self) -> str:  # pragma: no cover
        parts = [self.name]
        if self.vram_mb:
            parts.append(f"{self.vram_mb} MiB")
        if self.driver_version:
            parts.append(f"driver {self.driver_version}")
        if self.cuda_available:
            parts.append(f"CUDA:{self.cuda_index}")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_nvidia_smi() -> List[GPUInfo]:
    """Query nvidia-smi for NVIDIA GPUs (returns empty list if unavailable)."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        gpus: List[GPUInfo] = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            name, driver, vram_str = parts[0], parts[1], parts[2]
            try:
                vram_mb = int(vram_str)
            except ValueError:
                vram_mb = 0
            gpus.append(GPUInfo(name=name, driver_version=driver, vram_mb=vram_mb))
        return gpus
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _detect_torch_cuda() -> List[GPUInfo]:
    """Query PyTorch for CUDA-capable devices."""
    try:
        import torch  # type: ignore

        if not torch.cuda.is_available():
            return []
        gpus: List[GPUInfo] = []
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            gpus.append(
                GPUInfo(
                    name=props.name,
                    vram_mb=props.total_memory // (1024 * 1024),
                    cuda_index=i,
                    cuda_available=True,
                )
            )
        return gpus
    except Exception:
        return []


def _detect_wmi_display() -> List[GPUInfo]:
    """
    Query Win32_VideoController via WMI (Windows only).

    Returns all display adapters including integrated GPU adapters that
    nvidia-smi and CUDA would miss.
    """
    if sys.platform != "win32":
        return []
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "Get-CimInstance Win32_VideoController"
                    " | Select-Object -ExpandProperty Name"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return []
        gpus: List[GPUInfo] = []
        for line in result.stdout.strip().splitlines():
            name = line.strip()
            if name:
                gpus.append(GPUInfo(name=name))
        return gpus
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_gpus() -> List[GPUInfo]:
    """
    Return a list of all detected GPUs in priority order (CUDA-capable first).

    Combines results from nvidia-smi (NVIDIA-specific, includes VRAM/driver)
    and CUDA PyTorch enumeration (marks which devices are CUDA-ready).  WMI is
    used as a fallback on Windows to surface integrated/non-CUDA adapters.
    """
    smi_gpus = _detect_nvidia_smi()
    cuda_gpus = _detect_torch_cuda()

    # Merge nvidia-smi entries with matching torch CUDA entries (by name).
    # Use a minimum word-overlap heuristic: split names into tokens and require
    # at least two tokens to match, reducing false positives from short shared
    # substrings like "RTX" or "GTX".
    def _names_match(a: str, b: str) -> bool:
        tokens_a = set(a.lower().split())
        tokens_b = set(b.lower().split())
        common = tokens_a & tokens_b
        # Require at least 2 tokens in common, or one token that is at least
        # 6 characters (avoids matching on generic words like "nvidia").
        return sum(1 for t in common if len(t) >= 6) >= 1 or len(common) >= 2

    merged: List[GPUInfo] = []
    for smi in smi_gpus:
        for cuda in cuda_gpus:
            if _names_match(smi.name, cuda.name):
                smi.cuda_index = cuda.cuda_index
                smi.cuda_available = True
                if not smi.vram_mb:
                    smi.vram_mb = cuda.vram_mb
                break
        merged.append(smi)

    # Add any torch CUDA devices not already covered by nvidia-smi.
    existing_names = {g.name.lower() for g in merged}
    for cuda in cuda_gpus:
        if cuda.name.lower() not in existing_names:
            merged.append(cuda)

    # If we found nothing so far, fall back to WMI (Windows) display adapters.
    if not merged and sys.platform == "win32":
        merged = _detect_wmi_display()

    return merged


def best_device() -> str:
    """
    Return the recommended compute device string ('cuda' or 'cpu').

    Prefers the first CUDA-capable GPU; falls back to 'cpu'.
    """
    for gpu in detect_gpus():
        if gpu.cuda_available:
            return "cuda"
    return "cpu"


def print_gpu_summary() -> None:
    """Print a human-readable GPU summary to stdout."""
    gpus = detect_gpus()
    if not gpus:
        print("[GPU] No dedicated GPU detected — will run on CPU.")
        return

    print(f"[GPU] Detected {len(gpus)} display adapter(s):")
    for gpu in gpus:
        tag = " [CUDA ready]" if gpu.cuda_available else ""
        vram = f"  {gpu.vram_mb} MiB VRAM" if gpu.vram_mb else ""
        driver = f"  driver {gpu.driver_version}" if gpu.driver_version else ""
        print(f"       • {gpu.name}{vram}{driver}{tag}")

    cuda_gpus = [g for g in gpus if g.cuda_available]
    if cuda_gpus:
        print(f"[GPU] Using CUDA ({cuda_gpus[0].name}) for Whisper inference.")
    else:
        print("[GPU] No CUDA device available — Whisper will run on CPU.")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_gpu_summary()
