import argparse
import csv
import re
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SR = 44100


class Estilo(StrEnum):
    SAMBA = "SA"
    PARTIDO_ALTO = "PA"
    SAMBA_ENREDO = "SE"
    MARCHA = "MA"
    CAPOEIRA = "CA"

    @property
    def bpm(self) -> float:
        return BPM_POR_ESTILO[self]


BPM_POR_ESTILO: dict[Estilo, float] = {
    Estilo.SAMBA: 80,
    Estilo.PARTIDO_ALTO: 100,
    Estilo.SAMBA_ENREDO: 130,
    Estilo.MARCHA: 120,
    Estilo.CAPOEIRA: 65,
}


class Curva(StrEnum):
    LINEAR = "linear"
    COSSENO = "cosseno"

    def descida(self, n: int) -> np.ndarray:
        if self == Curva.COSSENO:
            return 0.5 * (1 + np.cos(np.pi * np.linspace(0.0, 1.0, n)))
        return np.linspace(1.0, 0.0, n)


@dataclass(frozen=True)
class Envelope:
    fade_in_s: float
    fade_out_s: float
    curva: Curva


ENVELOPE_CURTO = Envelope(fade_in_s=0.0, fade_out_s=0.010, curva=Curva.LINEAR)


class Instrumento(StrEnum):
    SURDO1 = "surdo1"
    SURDO2 = "surdo2"
    PANDEIRO = "pandeiro"
    TAMBORIM = "tamborim"
    CUICA = "cuica"

    @property
    def duracao_max_s(self) -> float:
        return DURACAO_MAX_S[self]

    @property
    def tem_altura(self) -> bool:
        return self == Instrumento.CUICA

    @property
    def envelope(self) -> Envelope:
        return ENVELOPE_POR_INSTRUMENTO.get(self, ENVELOPE_CURTO)


DURACAO_MAX_S: dict[Instrumento, float] = {
    Instrumento.SURDO1: 0.8,
    Instrumento.SURDO2: 0.8,
    Instrumento.PANDEIRO: 0.2,
    Instrumento.TAMBORIM: 0.25,
    Instrumento.CUICA: 0.4,
}

ENVELOPE_POR_INSTRUMENTO: dict[Instrumento, Envelope] = {
    Instrumento.CUICA: Envelope(fade_in_s=0.005, fade_out_s=0.035, curva=Curva.COSSENO),
}

SELECAO_BRID: dict[Instrumento, tuple[int, ...]] = {
    Instrumento.SURDO1: (270, 180, 358),
    Instrumento.SURDO2: (279, 184, 365),
    Instrumento.PANDEIRO: (185, 101, 281),
    Instrumento.TAMBORIM: (214, 129, 302),
    Instrumento.CUICA: (245, 162),
}

PADRAO_NOME_SOLO = re.compile(r"\[(?P<gid>\d{4})\] S(?P<instrumentista>\d)-(?P<codigo>[A-Z]{2}\d)-(?P<numero>\d{2})-(?P<estilo>[A-Z]+)\.wav")


@dataclass(frozen=True)
class FaixaBrid:
    gid: int
    instrumentista: int
    codigo_instrumento: str
    numero: int
    estilo: Estilo
    caminho: Path

    @property
    def bpm(self) -> float:
        return self.estilo.bpm

    @classmethod
    def de_caminho(cls, caminho: Path) -> "FaixaBrid":
        casamento = PADRAO_NOME_SOLO.fullmatch(caminho.name)
        if casamento is None:
            raise ValueError(f"nome fora do padrão de faixa solo do BRID: {caminho.name}")
        estilos = {estilo.value: estilo for estilo in Estilo}
        codigo_estilo = casamento["estilo"]
        if codigo_estilo not in estilos:
            raise ValueError(f"estilo sem andamento fixo: {codigo_estilo} em {caminho.name}")
        return cls(
            gid=int(casamento["gid"]),
            instrumentista=int(casamento["instrumentista"]),
            codigo_instrumento=casamento["codigo"],
            numero=int(casamento["numero"]),
            estilo=estilos[codigo_estilo],
            caminho=caminho,
        )


class CatalogoBrid:
    def __init__(self, raiz: Path):
        self._faixas: dict[int, Path] = {}
        for caminho in (raiz / "Solo Tracks").rglob("*.wav"):
            casamento = PADRAO_NOME_SOLO.fullmatch(caminho.name)
            if casamento is not None:
                self._faixas[int(casamento["gid"])] = caminho

    def faixa(self, gid: int) -> FaixaBrid:
        if gid not in self._faixas:
            raise KeyError(f"faixa {gid:04d} não encontrada no BRID")
        return FaixaBrid.de_caminho(self._faixas[gid])


@dataclass(frozen=True)
class PosicaoNaGrade:
    beat: int
    posicao: int
    desvio: float


@dataclass(frozen=True)
class GradeDeBeats:
    TOLERANCIA_PERIODO = 0.04
    CANDIDATOS_PERIODO = 4001
    MINIMO_DE_BEATS = 8

    t0: float
    periodo: float

    @property
    def delta(self) -> float:
        return self.periodo / 4

    def localizar(self, t: float) -> PosicaoNaGrade:
        passos = (t - self.t0) / self.delta
        passo = round(passos)
        return PosicaoNaGrade(beat=passo // 4, posicao=passo % 4, desvio=passos - passo)

    @classmethod
    def ajustar(cls, y: np.ndarray, sr: int, bpm: float) -> "GradeDeBeats":
        envelope = librosa.onset.onset_strength(y=y, sr=sr)
        quadros = librosa.onset.onset_detect(onset_envelope=envelope, sr=sr)
        tempos = librosa.frames_to_time(quadros, sr=sr)
        pesos = envelope[quadros]
        periodo = cls._periodo(tempos, pesos, 60 / bpm)
        delta = periodo / 4
        fase = cls._fase(tempos, pesos, delta)
        semicolcheia_do_beat = cls._semicolcheia_do_beat(envelope, sr, bpm, fase, delta)
        return cls(t0=(fase + semicolcheia_do_beat * delta) % periodo, periodo=periodo)

    @classmethod
    def _periodo(cls, tempos: np.ndarray, pesos: np.ndarray, nominal: float) -> float:
        candidatos = nominal * np.linspace(1 - cls.TOLERANCIA_PERIODO, 1 + cls.TOLERANCIA_PERIODO, cls.CANDIDATOS_PERIODO)
        angulos = 2 * np.pi * np.outer(4 / candidatos, tempos)
        coerencia = np.abs(np.exp(1j * angulos) @ pesos)
        return float(candidatos[np.argmax(coerencia)])

    @staticmethod
    def _fase(tempos: np.ndarray, pesos: np.ndarray, delta: float) -> float:
        resultante = np.sum(pesos * np.exp(2j * np.pi * tempos / delta))
        return float(np.angle(resultante) / (2 * np.pi) * delta) % delta

    @classmethod
    def _semicolcheia_do_beat(cls, envelope: np.ndarray, sr: int, bpm: float, fase: float, delta: float) -> int:
        _, beats = librosa.beat.beat_track(onset_envelope=envelope, sr=sr, bpm=bpm, units="time")
        if beats.size < cls.MINIMO_DE_BEATS:
            _, beats = librosa.beat.beat_track(onset_envelope=envelope, sr=sr, start_bpm=bpm, units="time")
        votos = np.round((beats - fase) / delta).astype(int) % 4
        return int(np.bincount(votos, minlength=4).argmax())


@dataclass(frozen=True)
class Recorte:
    indice: int
    inicio: int
    audio: np.ndarray
    nivel_final_db: float


class Fatiador:
    LIMIAR_ATAQUE_DB = -30.0
    JANELA_FINAL_S = 0.010

    def __init__(self, sr: int, envelope: Envelope = ENVELOPE_CURTO):
        self.sr = sr
        self.envelope = envelope

    def recortar(self, y: np.ndarray, duracao_max_s: float) -> list[Recorte]:
        onsets = librosa.onset.onset_detect(y=y, sr=self.sr, backtrack=True, units="samples")
        recortes = self.recortar_em(y, onsets, duracao_max_s)
        return recortes[1:-1]

    def recortar_em(self, y: np.ndarray, onsets: np.ndarray, duracao_max_s: float) -> list[Recorte]:
        limite = int(duracao_max_s * self.sr)
        fronteiras = [*onsets.tolist(), y.size]
        recortes: list[Recorte] = []
        for indice, (inicio, proximo) in enumerate(zip(fronteiras[:-1], fronteiras[1:])):
            trecho = y[inicio:proximo]
            ataque = self._ataque(trecho)
            audio = trecho[ataque : ataque + limite].astype(np.float64)
            if audio.size == 0:
                continue
            recortes.append(
                Recorte(
                    indice=indice,
                    inicio=inicio + ataque,
                    nivel_final_db=self._nivel_final_db(audio),
                    audio=self._aplicar_envelope(audio),
                )
            )
        return recortes

    def _ataque(self, trecho: np.ndarray) -> int:
        amplitude = np.abs(trecho)
        if amplitude.size == 0 or amplitude.max() == 0:
            return 0
        limiar = amplitude.max() * 10 ** (self.LIMIAR_ATAQUE_DB / 20)
        return int(np.argmax(amplitude >= limiar))

    def _nivel_final_db(self, audio: np.ndarray) -> float:
        pico = float(np.max(np.abs(audio)))
        final = audio[-max(1, int(self.JANELA_FINAL_S * self.sr)) :]
        rms = float(np.sqrt(np.mean(final**2)))
        return 20 * float(np.log10(max(rms, 1e-12) / max(pico, 1e-12)))

    def _aplicar_envelope(self, audio: np.ndarray) -> np.ndarray:
        saida = audio.copy()
        n_in = min(int(self.envelope.fade_in_s * self.sr), saida.size)
        if n_in:
            saida[:n_in] *= self.envelope.curva.descida(n_in)[::-1]
        n_out = min(int(self.envelope.fade_out_s * self.sr), saida.size)
        saida[saida.size - n_out :] *= self.envelope.curva.descida(n_out)
        return saida


@dataclass(frozen=True)
class Descritores:
    CORTE_GRAVES_HZ = 200.0
    QUEDA_DECAIMENTO_DB = -20.0
    QUADRO = 512
    SALTO = 128
    F0_MIN_HZ = 150.0
    F0_MAX_HZ = 2000.0
    QUADRO_F0 = 2048
    SALTO_F0 = 256

    duracao_ms: float
    rms: float
    centroide_hz: float
    razao_graves: float
    decaimento_ms: float
    f0_hz: float = float("nan")

    @classmethod
    def extrair(cls, audio: np.ndarray, sr: int, com_f0: bool = False) -> "Descritores":
        magnitude = np.abs(np.fft.rfft(audio))
        potencia = magnitude**2
        frequencias = np.fft.rfftfreq(audio.size, 1 / sr)
        return cls(
            duracao_ms=audio.size / sr * 1000,
            rms=float(np.sqrt(np.mean(audio**2))),
            centroide_hz=float(np.sum(frequencias * magnitude) / np.sum(magnitude)),
            razao_graves=float(np.sum(potencia[frequencias < cls.CORTE_GRAVES_HZ]) / np.sum(potencia)),
            decaimento_ms=cls._decaimento_ms(audio, sr),
            f0_hz=cls._f0_hz(audio, sr) if com_f0 else float("nan"),
        )

    @classmethod
    def _f0_hz(cls, audio: np.ndarray, sr: int) -> float:
        f0, sonoro, _ = librosa.pyin(
            audio, fmin=cls.F0_MIN_HZ, fmax=cls.F0_MAX_HZ, sr=sr, frame_length=cls.QUADRO_F0, hop_length=cls.SALTO_F0
        )
        return float(np.nanmedian(f0[sonoro])) if np.any(sonoro) else float("nan")

    @classmethod
    def _decaimento_ms(cls, audio: np.ndarray, sr: int) -> float:
        envelope = librosa.feature.rms(y=audio, frame_length=cls.QUADRO, hop_length=cls.SALTO)[0]
        pico = int(np.argmax(envelope))
        limiar = envelope[pico] * 10 ** (cls.QUEDA_DECAIMENTO_DB / 20)
        abaixo = np.flatnonzero(envelope[pico:] < limiar)
        quadros = int(abaixo[0]) if abaixo.size else envelope.size - 1 - pico
        return quadros * cls.SALTO / sr * 1000


class FiltroPercentil:
    def __init__(self, inferior: float, superior: float):
        self.inferior = inferior
        self.superior = superior

    def manter(self, itens: list[tuple[Recorte, Descritores]]) -> list[tuple[Recorte, Descritores]]:
        if not itens:
            return []
        duracoes = np.array([d.duracao_ms for _, d in itens])
        energias = np.array([d.rms for _, d in itens])
        dur_min, dur_max = np.percentile(duracoes, [self.inferior, self.superior])
        rms_min, rms_max = np.percentile(energias, [self.inferior, self.superior])
        return [
            (recorte, d)
            for recorte, d in itens
            if dur_min <= d.duracao_ms <= dur_max and rms_min <= d.rms <= rms_max
        ]


@dataclass(frozen=True)
class LinhaManifesto:
    arquivo: str
    instrumento: str
    gid: int
    origem: str
    estilo: str
    bpm: float
    onset_s: float
    beat: int
    posicao: int
    desvio: float
    duracao_ms: float
    rms: float
    centroide_hz: float
    razao_graves: float
    decaimento_ms: float
    f0_hz: float
    nivel_final_db: float


class ExtratorBrid:
    def __init__(self, catalogo: CatalogoBrid, saida: Path):
        self.catalogo = catalogo
        self.saida = saida
        self.filtro = FiltroPercentil(10, 90)

    def processar(self, instrumento: Instrumento) -> list[LinhaManifesto]:
        linhas: list[LinhaManifesto] = []
        for gid in SELECAO_BRID[instrumento]:
            linhas.extend(self._processar_faixa(instrumento, self.catalogo.faixa(gid)))
        return linhas

    def _processar_faixa(self, instrumento: Instrumento, faixa: FaixaBrid) -> list[LinhaManifesto]:
        y, _ = librosa.load(faixa.caminho, sr=SR, mono=True)
        grade = GradeDeBeats.ajustar(y, SR, faixa.bpm)
        recortes = Fatiador(SR, instrumento.envelope).recortar(y, instrumento.duracao_max_s)
        mantidos = self.filtro.manter([(r, Descritores.extrair(r.audio, SR, instrumento.tem_altura)) for r in recortes])
        pasta = self.saida / instrumento.value
        pasta.mkdir(parents=True, exist_ok=True)
        linhas: list[LinhaManifesto] = []
        for recorte, descritores in mantidos:
            destino = pasta / f"{faixa.gid:04d}_{recorte.indice:03d}.wav"
            sf.write(destino, recorte.audio, SR, subtype="PCM_16")
            onset_s = recorte.inicio / SR
            posicao = grade.localizar(onset_s)
            linhas.append(
                LinhaManifesto(
                    arquivo=str(destino.relative_to(self.saida)),
                    instrumento=instrumento.value,
                    gid=faixa.gid,
                    origem=faixa.caminho.name,
                    estilo=faixa.estilo.value,
                    bpm=faixa.bpm,
                    onset_s=round(onset_s, 5),
                    beat=posicao.beat,
                    posicao=posicao.posicao,
                    desvio=round(posicao.desvio, 4),
                    duracao_ms=round(descritores.duracao_ms, 2),
                    rms=round(descritores.rms, 6),
                    centroide_hz=round(descritores.centroide_hz, 1),
                    razao_graves=round(descritores.razao_graves, 4),
                    decaimento_ms=round(descritores.decaimento_ms, 1),
                    f0_hz=round(descritores.f0_hz, 1),
                    nivel_final_db=round(recorte.nivel_final_db, 1),
                )
            )
        return linhas

    def escrever_manifesto(self, linhas: list[LinhaManifesto]) -> Path:
        destino = self.saida / "manifest.csv"
        with destino.open("w", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=[f.name for f in fields(LinhaManifesto)])
            escritor.writeheader()
            escritor.writerows(asdict(linha) for linha in linhas)
        return destino


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Recorta one-shots das faixas solo do BRID e escreve o manifest.")
    parser.add_argument("--brid", type=Path, default=Path("brid"))
    parser.add_argument("--saida", type=Path, default=Path("samples_raw"))
    parser.add_argument(
        "--instrumentos",
        type=lambda texto: [Instrumento(nome) for nome in texto.split(",")],
        default=list(Instrumento),
    )
    args = parser.parse_args(argv)
    extrator = ExtratorBrid(CatalogoBrid(args.brid), args.saida)
    linhas: list[LinhaManifesto] = []
    for instrumento in args.instrumentos:
        linhas_do_instrumento = extrator.processar(instrumento)
        print(f"{instrumento.value}: {len(linhas_do_instrumento)} recortes")
        linhas.extend(linhas_do_instrumento)
    print(f"manifest: {extrator.escrever_manifesto(linhas)}")


if __name__ == "__main__":
    main()
