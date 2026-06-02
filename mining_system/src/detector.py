"""
硬體偵測模組
自動偵測 CPU、GPU 型號與規格
"""

import subprocess
from dataclasses import dataclass, field


@dataclass
class GPUInfo:
    index: int
    name: str
    vendor: str       # "nvidia" | "amd" | "unknown"
    vram_mb: int


@dataclass
class HardwareInfo:
    cpu_name: str
    cpu_cores: int
    cpu_threads: int
    gpus: list[GPUInfo] = field(default_factory=list)

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
        for g in self.gpus:
            lines.append(f"GPU：{g.name} ({g.vram_mb} MB VRAM) [{g.vendor}]")
        if not self.gpus:
            lines.append("GPU：未偵測到獨立顯卡")
        return "\n".join(lines)


def detect() -> HardwareInfo:
    cpu_name, cpu_cores, cpu_threads = _detect_cpu()
    gpus = _detect_gpus()
    return HardwareInfo(
        cpu_name=cpu_name,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        gpus=gpus,
    )


def _detect_cpu() -> tuple[str, int, int]:
    # PowerShell 方式最穩定，用 | 分隔避免 CPU 名稱含逗號的問題
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-WmiObject Win32_Processor | Select-Object -First 1 | "
             "ForEach-Object { \"$($_.Name)|$($_.NumberOfCores)|$($_.NumberOfLogicalProcessors)\" }"],
            capture_output=True, text=True, timeout=10
        )
        line = r.stdout.strip()
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                return parts[0].strip(), int(parts[1].strip()), int(parts[2].strip())
    except Exception:
        pass

    # Fallback：wmic
    try:
        r = subprocess.run(
            ["wmic", "cpu", "get", "Name,NumberOfCores,NumberOfLogicalProcessors", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        for line in r.stdout.strip().splitlines():
            parts = line.split(",")
            if len(parts) < 4 or parts[1].strip() in ("", "NumberOfCores"):
                continue
            try:
                return parts[3].strip(), int(parts[1].strip()), int(parts[2].strip())
            except (ValueError, IndexError):
                continue
    except Exception:
        pass

    return "Unknown CPU", 4, 4


def _detect_gpus() -> list[GPUInfo]:
    gpus = []
    nvidia = _detect_nvidia_smi()
    if nvidia:
        gpus.extend(nvidia)
    gpus.extend(_detect_wmic(skip_nvidia=bool(nvidia)))
    return gpus


def _detect_nvidia_smi() -> list[GPUInfo]:
    """nvidia-smi 是最準確的 NVIDIA 偵測方式"""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return []
        result = []
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    result.append(GPUInfo(
                        index=int(parts[0]),
                        name=parts[1],
                        vendor="nvidia",
                        vram_mb=int(parts[2]),
                    ))
                except ValueError:
                    continue
        return result
    except FileNotFoundError:
        return []


def _detect_wmic(skip_nvidia: bool = False) -> list[GPUInfo]:
    """WMI 偵測 AMD 與其他顯卡"""
    try:
        r = subprocess.run(
            ["wmic", "path", "Win32_VideoController",
             "get", "Name,AdapterRAM", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        result = []
        idx = 100  # 避免與 nvidia-smi index 衝突
        for line in r.stdout.strip().splitlines():
            parts = line.split(",")
            if len(parts) < 3:
                continue
            name = parts[2].strip()
            if not name or name == "Name":
                continue

            name_lower = name.lower()
            # 跳過整合顯卡
            if "intel" in name_lower:
                continue
            if skip_nvidia and "nvidia" in name_lower:
                continue

            vendor = "unknown"
            if "nvidia" in name_lower:
                vendor = "nvidia"
            elif "amd" in name_lower or "radeon" in name_lower:
                vendor = "amd"

            try:
                vram_mb = int(parts[1].strip()) // (1024 * 1024)
            except (ValueError, IndexError):
                vram_mb = 0

            result.append(GPUInfo(index=idx, name=name, vendor=vendor, vram_mb=vram_mb))
            idx += 1
        return result
    except Exception:
        return []
