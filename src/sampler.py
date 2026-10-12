import random
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf

from src.pistas import Camada, Pista

SR = 44100
VELOCIDADE_V2 = 95
EXPOENTE_DO_GANHO = 1.7


class BibliotecaDeSamples:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self._amostras: dict[tuple[Pista, Camada], list[np.ndarray]] = {
            (pista, camada): self._carregar(raiz / pista.especificacao.pasta / camada.value)
            for pista in Pista
            for camada in Camada
        }

    @staticmethod
    def existe(raiz: Path) -> bool:
        return raiz.is_dir() and any(raiz.rglob("*.wav"))

    def amostras(self, pista: Pista, camada: Camada) -> list[np.ndarray]:
        outra = Camada.V1 if camada == Camada.V2 else Camada.V2
        amostras = self._amostras[(pista, camada)] or self._amostras[(pista, outra)]
        if not amostras:
            raise ValueError(f"sem amostras para {pista.value} em {self.raiz / pista.especificacao.pasta}")
        return amostras

    @staticmethod
    def _carregar(pasta: Path) -> list[np.ndarray]:
        amostras: list[np.ndarray] = []
        for caminho in sorted(pasta.glob("*.wav")):
            audio, sr = sf.read(caminho, dtype="float64", always_2d=True)
            if sr != SR:
                raise ValueError(f"{caminho} está a {sr} Hz, esperado {SR} Hz")
            amostras.append(audio.mean(axis=1))
        return amostras


class Sampler:
    def __init__(self, biblioteca: BibliotecaDeSamples, seed: int):
        self.biblioteca = biblioteca
        self.rng = random.Random(seed + 2)
        self._ultima: dict[tuple[Pista, Camada], int] = {}

    def renderizar(self, midi: pretty_midi.PrettyMIDI) -> np.ndarray:
        notas = sorted(
            (nota for instrumento in midi.instruments for nota in instrumento.notes),
            key=lambda n: (n.start, n.pitch),
        )
        disparos = [(int(round(nota.start * SR)), self._escolher(nota), self._ganho(nota)) for nota in notas]
        tamanho = max((inicio + amostra.size for inicio, amostra, _ in disparos), default=0)
        buffer = np.zeros(tamanho)
        for inicio, amostra, ganho in disparos:
            buffer[inicio : inicio + amostra.size] += amostra * ganho
        return buffer

    def _escolher(self, nota: pretty_midi.Note) -> np.ndarray:
        pista = Pista.da_nota(nota.pitch)
        camada = Camada.V2 if nota.velocity >= VELOCIDADE_V2 else Camada.V1
        amostras = self.biblioteca.amostras(pista, camada)
        ultima = self._ultima.get((pista, camada))
        candidatas = [i for i in range(len(amostras)) if i != ultima] or [0]
        escolhida = self.rng.choice(candidatas)
        self._ultima[(pista, camada)] = escolhida
        return amostras[escolhida]

    @staticmethod
    def _ganho(nota: pretty_midi.Note) -> float:
        return (nota.velocity / 127) ** EXPOENTE_DO_GANHO * Pista.da_nota(nota.pitch).especificacao.ganho
