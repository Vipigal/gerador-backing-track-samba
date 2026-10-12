import json
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pretty_midi

from src.arranjo import Grade
from src.hiperparametros import Hiperparametros
from src.pistas import Grupo, Pista
from src.terminais import Terminal

VELOCIDADE_POR_VALOR = {1: 78, 2: 108}
FRACAO_DA_DURACAO = 0.9
COMPASSO = (2, 4)


@dataclass(frozen=True)
class ParametrosDeRender:
    bpm: float = 90.0
    balanco: float = 0.0
    microtiming: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    sigma_tempo_s: float = 0.004
    sigma_velocidade: float = 6.0

    @property
    def delta(self) -> float:
        return 60 / (4 * self.bpm)


@dataclass(frozen=True)
class Evento:
    tempo_s: float
    pista: Pista
    velocidade: int


class Sequenciador:
    def __init__(self, parametros: ParametrosDeRender, seed: int):
        self.parametros = parametros
        self.rng = random.Random(seed + 1)

    def eventos(self, grade: Grade) -> list[Evento]:
        eventos: list[Evento] = []
        for passo in range(grade.passos):
            for pista in Pista:
                valor = grade.pistas[pista][passo]
                if valor:
                    eventos.append(Evento(self._tempo(passo), pista, self._velocidade(valor)))
        return eventos

    def _tempo(self, passo: int) -> float:
        p = self.parametros
        microtiming = p.balanco * p.microtiming[passo % 4] * p.delta
        return max(0.0, passo * p.delta + microtiming + self.rng.gauss(0.0, p.sigma_tempo_s))

    def _velocidade(self, valor: int) -> int:
        velocidade = round(VELOCIDADE_POR_VALOR[valor] + self.rng.gauss(0.0, self.parametros.sigma_velocidade))
        return min(127, max(1, velocidade))


class ArquivoMidi:
    def __init__(self, parametros: ParametrosDeRender):
        self.parametros = parametros

    def montar(self, eventos: Sequence[Evento]) -> pretty_midi.PrettyMIDI:
        midi = pretty_midi.PrettyMIDI(initial_tempo=self.parametros.bpm)
        midi.time_signature_changes.append(pretty_midi.TimeSignature(*COMPASSO, 0.0))
        instrumentos = {grupo: pretty_midi.Instrument(program=0, is_drum=True, name=grupo.value) for grupo in Grupo}
        duracao = self.parametros.delta * FRACAO_DA_DURACAO
        for evento in eventos:
            especificacao = evento.pista.especificacao
            instrumentos[especificacao.grupo].notes.append(
                pretty_midi.Note(
                    velocity=evento.velocidade,
                    pitch=especificacao.nota_gm,
                    start=evento.tempo_s,
                    end=evento.tempo_s + duracao,
                )
            )
        midi.instruments.extend(i for i in instrumentos.values() if i.notes)
        return midi

    def salvar(self, midi: pretty_midi.PrettyMIDI, destino: Path) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        midi.write(str(destino))


@dataclass(frozen=True)
class RegistroDaMusica:
    seed: int
    hiperparametros: Hiperparametros | None
    render: ParametrosDeRender
    derivacao: Sequence[Terminal]
    arvore: object = field(default=None)

    def salvar(self, destino: Path) -> None:
        registro = {
            "seed": self.seed,
            "hiperparametros": asdict(self.hiperparametros) if self.hiperparametros else None,
            "render": asdict(self.render),
            "ciclos": len(self.derivacao),
            "derivacao": [terminal.value for terminal in self.derivacao],
            "arvore": self.arvore,
        }
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(registro, ensure_ascii=False, indent=2))
