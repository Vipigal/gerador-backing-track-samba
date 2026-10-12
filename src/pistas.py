from dataclasses import dataclass
from enum import StrEnum


class Camada(StrEnum):
    V1 = "v1"
    V2 = "v2"


class Grupo(StrEnum):
    SURDO = "surdo"
    PANDEIRO = "pandeiro"
    TAMBORIM = "tamborim"
    CUICA = "cuica"


@dataclass(frozen=True)
class EspecificacaoDaPista:
    grupo: Grupo
    nota_gm: int
    pasta: str
    ganho: float


class Pista(StrEnum):
    SD1 = "sd1"
    SD2 = "sd2"
    PD_G = "pd_g"
    PD_P = "pd_p"
    PD_T = "pd_t"
    TB = "tb"
    CU_G = "cu_g"
    CU_A = "cu_a"

    @property
    def especificacao(self) -> EspecificacaoDaPista:
        return ESPECIFICACOES[self]

    @classmethod
    def da_nota(cls, nota: int) -> "Pista":
        for pista, especificacao in ESPECIFICACOES.items():
            if especificacao.nota_gm == nota:
                return pista
        raise ValueError(f"nota MIDI sem pista: {nota}")


ESPECIFICACOES: dict[Pista, EspecificacaoDaPista] = {
    Pista.SD1: EspecificacaoDaPista(Grupo.SURDO, 41, "surdo1/aberto", 1.0),
    Pista.SD2: EspecificacaoDaPista(Grupo.SURDO, 43, "surdo2/aberto", 0.8),
    Pista.PD_G: EspecificacaoDaPista(Grupo.PANDEIRO, 64, "pandeiro/grave", 0.6),
    Pista.PD_P: EspecificacaoDaPista(Grupo.PANDEIRO, 54, "pandeiro/platinela", 0.6),
    Pista.PD_T: EspecificacaoDaPista(Grupo.PANDEIRO, 62, "pandeiro/tapa", 0.6),
    Pista.TB: EspecificacaoDaPista(Grupo.TAMBORIM, 65, "tamborim/batida", 0.7),
    Pista.CU_G: EspecificacaoDaPista(Grupo.CUICA, 78, "cuica/grave", 0.5),
    Pista.CU_A: EspecificacaoDaPista(Grupo.CUICA, 79, "cuica/aguda", 0.5),
}
