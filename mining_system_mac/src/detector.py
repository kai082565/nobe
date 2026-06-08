"""
硬體偵測模組 (macOS)
使用 sysctl 取得 CPU 資訊；Apple Silicon 整合顯卡不用於挖礦
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field


@dataclass
class GPUInfo:
    index:   int
    name:    str
    vendor:  str
    vram_mb: int


@dataclass
class HardwareInfo:
    cpu_name:    str
    cpu_cores:   int
    cpu_threads: int
    gpus:        list[GPUInfo] = field(default_factory=list)

    @property
    def has_nvidia(self) -> bool:
        return any(g.vendor == "nvidia" for g in self.gpus)

    @property
    def has_amd(self) -> bool:
        return any(g.vendor == "amd" for g in self.gpus)

    @property
    def best_gpu(self) -> GPUInfo | None:
        mining_gpus = [g for g in self.gpus if g.vendor in ("nvidia", "amd")]
        if not mining_gpus:
            return None
        return max(mining_gpus, key=lambda g: g.vram_mb)

    def summary(self) -> str:
        lines = [f"CPU：{self.cpu_name} ({self.cpu_cores}核{self.cpu_threads}緒)"]
        lines.append("GPU：Apple 整合顯卡（不用於挖礦，改用 CPU）")
        return "\n".join(lines)


def detect() -> HardwareInfo:
    cpu_name, cpu_cores, cpu_threads = _detect_cpu()
    return HardwareInfo(
        cpu_name=cpu_name,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        gpus=[],
    )


def _detect_cpu() -> tuple[str, int, int]:
    try:
        name = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()

        # Apple Silicon 上 brand_string 可能為空，改用 system_profiler
        if not name:
            out = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True, text=True, timeout=10
            ).stdout
            for line in out.splitlines():
                if "Chip" in line or "Processor Name" in line:
                    name = line.split(":", 1)[-1].strip()
                    break

        cores = int(subprocess.run(
            ["sysctl", "-n", "hw.physicalcpu"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip() or "8")

        threads = int(subprocess.run(
            ["sysctl", "-n", "hw.logicalcpu"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip() or "8")

        return name or "Apple Silicon", cores, threads

    except Exception:
        return "Apple M2", 8, 8
