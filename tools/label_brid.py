import argparse
import csv
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from pathlib import Path

import numpy as np
import soundfile as sf
from sklearn.cluster import KMeans

from src.pistas import Camada
from tools.slice_brid import SELECAO_BRID, Instrumento

PICO_DA_BIBLIOTECA_DBFS = -1.0
PERCENTIL_SURDO_ABERTO = 60
FAIXA_V1 = (40, 70)
PERCENTIL_V2 = 70
POR_CAMADA = 6
NIVEL_FINAL_MAXIMO_DB: dict[Instrumento, float] = {Instrumento.CUICA: -20.0}

LICENCA_BRID = """Os arquivos desta pasta são recortes de faixas solo do
Brazilian Rhythmic Instruments Dataset (BRID), licenciado sob
Creative Commons Attribution 4.0 International (CC BY 4.0).

Maia, L. S., Tomaz Jr., P. D., Fuentes, M., Rocamora, M., Biscainho, L. W. P.,
Costa, M. V. M., & Cohen, S. (2018). A Novel Dataset of Brazilian Rhythmic
Instruments and Some Experiments in Computational Rhythm Analysis.
2018 AES Latin American Congress of Audio Engineering, pp. 53-60.
Dataset: https://doi.org/10.5281/zenodo.14051323

Modificações: recorte por onset, remoção de silêncio inicial, fade-out de
10 ms e ganho único por instrumento. A origem de cada arquivo está em
curadoria.csv.
"""


class Articulacao(StrEnum):
    ABERTO = "aberto"
    GRAVE = "grave"
    PLATINELA = "platinela"
    TAPA = "tapa"
    BATIDA = "batida"
    AGUDA = "aguda"


@dataclass(frozen=True)
class LinhaRotulavel:
    arquivo: str
    gid: int
    beat: int
    posicao: int
    rms: float
    centroide_hz: float
    razao_graves: float
    decaimento_ms: float
    f0_hz: float
    nivel_final_db: float

    @property
    def features(self) -> list[float]:
        return [self.razao_graves, float(np.log(self.centroide_hz)), self.decaimento_ms]

    @property
    def features_de_tipicidade(self) -> list[float]:
        if np.isfinite(self.f0_hz):
            return [*self.features, float(np.log(self.f0_hz))]
        return self.features

    @property
    def passo_no_compasso(self) -> int:
        return (self.beat % 2) * 4 + self.posicao

    @classmethod
    def do_manifesto(cls, linha: Mapping[str, str]) -> "LinhaRotulavel":
        return cls(
            arquivo=linha["arquivo"],
            gid=int(linha["gid"]),
            beat=int(linha["beat"]),
            posicao=int(linha["posicao"]),
            rms=float(linha["rms"]),
            centroide_hz=float(linha["centroide_hz"]),
            razao_graves=float(linha["razao_graves"]),
            decaimento_ms=float(linha["decaimento_ms"]),
            f0_hz=float(linha["f0_hz"]),
            nivel_final_db=float(linha["nivel_final_db"]),
        )


def padronizar(matriz: np.ndarray) -> np.ndarray:
    desvio = matriz.std(axis=0)
    return (matriz - matriz.mean(axis=0)) / np.where(desvio > 0, desvio, 1.0)


class Rotulador:
    INICIALIZACOES = 10

    def rotular(self, instrumento: Instrumento, linhas: Sequence[LinhaRotulavel]) -> dict[str, Articulacao]:
        match instrumento:
            case Instrumento.SURDO1 | Instrumento.SURDO2:
                return self._surdo(linhas)
            case Instrumento.PANDEIRO:
                return self._pandeiro(linhas)
            case Instrumento.TAMBORIM:
                return {linha.arquivo: Articulacao.BATIDA for linha in linhas}
            case Instrumento.CUICA:
                return self._cuica(linhas)

    def _surdo(self, linhas: Sequence[LinhaRotulavel]) -> dict[str, Articulacao]:
        limiar = np.percentile([l.decaimento_ms for l in linhas], PERCENTIL_SURDO_ABERTO)
        return {l.arquivo: Articulacao.ABERTO for l in linhas if l.decaimento_ms >= limiar}

    def _pandeiro(self, linhas: Sequence[LinhaRotulavel]) -> dict[str, Articulacao]:
        grupos = self._agrupar(np.array([l.features for l in linhas]), 3)
        graves_por_grupo = {g: np.mean([l.razao_graves for l, k in zip(linhas, grupos) if k == g]) for g in range(3)}
        grave, tapa, platinela = sorted(graves_por_grupo, key=lambda g: -graves_por_grupo[g])
        nomes = {grave: Articulacao.GRAVE, tapa: Articulacao.TAPA, platinela: Articulacao.PLATINELA}
        return {l.arquivo: nomes[int(k)] for l, k in zip(linhas, grupos)}

    def _cuica(self, linhas: Sequence[LinhaRotulavel]) -> dict[str, Articulacao]:
        com_altura = [l for l in linhas if np.isfinite(l.f0_hz)]
        grupos = self._agrupar(np.array([[np.log(l.f0_hz)] for l in com_altura]), 2)
        f0_medio = {g: np.mean([l.f0_hz for l, k in zip(com_altura, grupos) if k == g]) for g in range(2)}
        aguda = max(f0_medio, key=lambda g: f0_medio[g])
        return {l.arquivo: Articulacao.AGUDA if k == aguda else Articulacao.GRAVE for l, k in zip(com_altura, grupos)}

    def _agrupar(self, matriz: np.ndarray, k: int) -> np.ndarray:
        padronizada = padronizar(matriz)
        modelos = [KMeans(n_clusters=k, n_init="auto", random_state=s).fit(padronizada) for s in range(self.INICIALIZACOES)]
        return np.asarray(max(modelos, key=lambda m: m.score(padronizada)).labels_)


def histograma_no_compasso(rotulos: Mapping[str, Articulacao], linhas: Sequence[LinhaRotulavel]) -> dict[Articulacao, list[int]]:
    contagem: dict[Articulacao, list[int]] = {}
    for linha in linhas:
        if linha.arquivo in rotulos:
            contagem.setdefault(rotulos[linha.arquivo], [0] * 8)[linha.passo_no_compasso] += 1
    return contagem


@dataclass(frozen=True)
class LinhaCuradoria:
    destino: str
    origem: str
    instrumento: str
    articulacao: str
    camada: str
    rms: float


class BibliotecaProvisoria:
    def __init__(self, origem: Path, destino: Path, quantidade: int = POR_CAMADA):
        self.origem = origem
        self.destino = destino
        self.quantidade = quantidade

    @staticmethod
    def separar_camadas(linhas: Sequence[LinhaRotulavel]) -> dict[Camada, list[LinhaRotulavel]]:
        energias = [l.rms for l in linhas]
        v1_min, v1_max = np.percentile(energias, FAIXA_V1)
        v2_min = np.percentile(energias, PERCENTIL_V2)
        return {
            Camada.V1: [l for l in linhas if v1_min <= l.rms < v1_max],
            Camada.V2: [l for l in linhas if l.rms >= v2_min],
        }

    @staticmethod
    def mais_tipicos(linhas: Sequence[LinhaRotulavel], quantidade: int) -> list[LinhaRotulavel]:
        if not linhas:
            return []
        padronizadas = padronizar(np.array([l.features_de_tipicidade for l in linhas]))
        distancias = np.linalg.norm(padronizadas - np.median(padronizadas, axis=0), axis=1)
        ordem = sorted(range(len(linhas)), key=lambda i: (distancias[i], linhas[i].arquivo))
        return [linhas[i] for i in ordem[:quantidade]]

    def montar(
        self, instrumento: Instrumento, rotulos: Mapping[str, Articulacao], linhas: Sequence[LinhaRotulavel]
    ) -> list[LinhaCuradoria]:
        escolhas: list[tuple[Articulacao, Camada, LinhaRotulavel]] = []
        nivel_maximo = NIVEL_FINAL_MAXIMO_DB.get(instrumento, float("inf"))
        inteiras = [l for l in linhas if l.nivel_final_db <= nivel_maximo]
        for articulacao in sorted(set(rotulos.values())):
            da_articulacao = [l for l in inteiras if rotulos.get(l.arquivo) == articulacao]
            for camada, candidatas in self.separar_camadas(da_articulacao).items():
                escolhas.extend((articulacao, camada, l) for l in self.mais_tipicos(candidatas, self.quantidade))
        audios = [sf.read(self.origem / linha.arquivo)[0] for _, _, linha in escolhas]
        if not audios:
            return []
        ganho = 10 ** (PICO_DA_BIBLIOTECA_DBFS / 20) / max(float(np.max(np.abs(a))) for a in audios)
        curadoria: list[LinhaCuradoria] = []
        for (articulacao, camada, linha), audio in zip(escolhas, audios):
            pasta = self.destino / instrumento.value / articulacao.value / camada.value
            pasta.mkdir(parents=True, exist_ok=True)
            destino = pasta / Path(linha.arquivo).name
            sf.write(destino, audio * ganho, sf.info(self.origem / linha.arquivo).samplerate, subtype="PCM_16")
            curadoria.append(
                LinhaCuradoria(
                    destino=str(destino.relative_to(self.destino)),
                    origem=linha.arquivo,
                    instrumento=instrumento.value,
                    articulacao=articulacao.value,
                    camada=camada.value,
                    rms=linha.rms,
                )
            )
        return curadoria


def ler_manifesto(caminho: Path) -> list[dict[str, str]]:
    with caminho.open() as arquivo:
        return list(csv.DictReader(arquivo))


def ler_curadoria_preservada(caminho: Path, refeitos: Sequence[Instrumento]) -> list[LinhaCuradoria]:
    if not caminho.exists():
        return []
    nomes_refeitos = {i.value for i in refeitos}
    with caminho.open() as arquivo:
        return [
            LinhaCuradoria(
                destino=l["destino"],
                origem=l["origem"],
                instrumento=l["instrumento"],
                articulacao=l["articulacao"],
                camada=l["camada"],
                rms=float(l["rms"]),
            )
            for l in csv.DictReader(arquivo)
            if l["instrumento"] not in nomes_refeitos
        ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rotula os recortes do BRID e monta a biblioteca provisória em samples/.")
    parser.add_argument("--recortes", type=Path, default=Path("samples_raw"))
    parser.add_argument("--saida", type=Path, default=Path("samples"))
    parser.add_argument("--por-camada", type=int, default=POR_CAMADA)
    parser.add_argument(
        "--instrumentos",
        type=lambda texto: [Instrumento(nome) for nome in texto.split(",")],
        default=list(Instrumento),
    )
    args = parser.parse_args(argv)
    instrumentos: list[Instrumento] = args.instrumentos

    manifesto = ler_manifesto(args.recortes / "manifest.csv")
    curadoria = ler_curadoria_preservada(args.saida / "curadoria.csv", instrumentos)
    biblioteca = BibliotecaProvisoria(args.recortes, args.saida, args.por_camada)
    rotulador = Rotulador()
    for instrumento in instrumentos:
        pasta = args.saida / instrumento.value
        if pasta.exists():
            shutil.rmtree(pasta)
        gid = SELECAO_BRID[instrumento][0]
        linhas = [
            LinhaRotulavel.do_manifesto(l) for l in manifesto if l["instrumento"] == instrumento.value and int(l["gid"]) == gid
        ]
        rotulos = rotulador.rotular(instrumento, linhas)
        escolhidos = biblioteca.montar(instrumento, rotulos, linhas)
        curadoria.extend(escolhidos)
        print(f"{instrumento.value} (gid {gid}): {len(linhas)} recortes, {len(escolhidos)} na biblioteca")
        for articulacao, contagem in sorted(histograma_no_compasso(rotulos, linhas).items()):
            print(f"  {articulacao.value:10} passo no compasso 0-7: {contagem}")

    args.saida.mkdir(parents=True, exist_ok=True)
    with (args.saida / "curadoria.csv").open("w", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=[f.name for f in fields(LinhaCuradoria)])
        escritor.writeheader()
        escritor.writerows(asdict(c) for c in curadoria)
    (args.saida / "LICENSE-BRID.txt").write_text(LICENCA_BRID)


if __name__ == "__main__":
    main()
