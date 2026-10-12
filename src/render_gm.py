from pathlib import Path

import numpy as np
import pretty_midi

SR = 44100
SOUNDFONTS_GM = (
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
)


class RenderizadorGM:
    def __init__(self, soundfont: Path | None = None):
        self.soundfont = soundfont or self.soundfont_do_sistema()

    @staticmethod
    def soundfont_do_sistema() -> Path | None:
        return next((s for s in SOUNDFONTS_GM if s.exists()), None)

    def renderizar(self, midi: pretty_midi.PrettyMIDI) -> np.ndarray:
        sintetizador = str(self.soundfont) if self.soundfont else None
        return midi.fluidsynth(fs=SR, synthesizer=sintetizador)
