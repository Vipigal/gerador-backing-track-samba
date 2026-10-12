import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

PICO_DBFS = -1.0


class ArquivoDeAudio:
    def __init__(self, sr: int):
        self.sr = sr

    @staticmethod
    def normalizar(audio: np.ndarray, pico_dbfs: float = PICO_DBFS) -> np.ndarray:
        pico = float(np.max(np.abs(audio))) if audio.size else 0.0
        if pico == 0:
            return audio
        return audio * (10 ** (pico_dbfs / 20) / pico)

    def salvar(self, audio: np.ndarray, base: Path) -> tuple[Path, Path]:
        base.parent.mkdir(parents=True, exist_ok=True)
        wav = base.parent / f"{base.name}.wav"
        mp3 = base.parent / f"{base.name}.mp3"
        sf.write(wav, self.normalizar(audio), self.sr, subtype="PCM_16")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3)],
            check=True,
        )
        return wav, mp3
