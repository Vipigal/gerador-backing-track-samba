from src.pistas import Pista
from src.terminais import Terminal

Padrao = tuple[int, ...]

PASSOS_POR_CICLO = 16
PASSOS_POR_COMPASSO = 8

SD1: Padrao = (0, 0, 0, 0, 2, 0, 0, 0,  0, 0, 0, 0, 2, 0, 0, 0)
SD2: Padrao = (1, 0, 0, 0, 0, 0, 0, 0,  1, 0, 0, 0, 0, 0, 0, 0)

TB_BASE: Padrao = (1, 0, 1, 0, 1, 1, 0,  1, 0, 1, 0, 1, 1, 0, 1, 0)

PD_P: Padrao = (1, 1, 1, 2, 1, 1, 1, 2,  1, 1, 1, 2, 1, 1, 1, 2)
PD_G: Padrao = (1, 0, 0, 0, 1, 0, 0, 0,  1, 0, 0, 0, 1, 0, 0, 0)
PD_T: Padrao = (0, 0, 0, 0, 0, 0, 0, 1,  0, 0, 0, 0, 0, 0, 0, 1)

TB_V1: Padrao = (1, 0, 1, 0, 1, 1, 0, 1,  0, 1, 1, 0, 1, 0, 1, 1)
TB_V2: Padrao = (1, 0, 1, 0, 1, 1, 0, 1,  0, 1, 0, 1, 1, 1, 1, 1)
TB_V3: Padrao = (1, 0, 1, 1, 0, 1, 0, 1,  0, 1, 0, 1, 1, 0, 1, 0)

PD_T_V1: Padrao = (0, 0, 0, 1, 0, 0, 0, 0,  0, 0, 0, 1, 0, 0, 0, 1)
PD_G_V2: Padrao = (1, 0, 0, 1, 1, 0, 0, 0,  1, 0, 0, 1, 1, 0, 0, 0)

CU_A_V1: Padrao = (0, 0, 0, 1, 0, 0, 0, 0,  0, 0, 0, 2, 0, 0, 1, 0)
CU_G_V1: Padrao = (0, 0, 0, 0, 1, 1, 1, 0,  0, 0, 0, 0, 1, 0, 0, 0)
CU_A_V2: Padrao = (0, 1, 0, 0, 0, 1, 0, 0,  0, 1, 0, 0, 0, 0, 0, 0)
CU_G_V2: Padrao = (0, 0, 0, 1, 0, 0, 0, 1,  0, 0, 2, 1, 1, 0, 0, 0)
CU_A_V3: Padrao = (1, 0, 0, 0, 1, 1, 0, 0,  0, 0, 0, 0, 1, 1, 1, 0)
CU_G_V3: Padrao = (0, 0, 1, 0, 0, 0, 0, 1,  0, 1, 0, 0, 0, 0, 0, 0)
CU_A_V4: Padrao = (0, 1, 0, 0, 0, 0, 0, 0,  0, 1, 0, 0, 0, 0, 0, 0)
CU_G_V4: Padrao = (0, 0, 1, 0, 1, 0, 1, 0,  0, 0, 1, 1, 1, 1, 1, 0)

CONTAGEM: Padrao = (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
ACENTO_FINAL: Padrao = (2,) + (0,) * 15
SILENCIO: Padrao = (0,) * PASSOS_POR_CICLO

UNI: Padrao = (2, 0, 0, 2, 0, 0, 2, 0)
BRQ: Padrao = (2, 0, 0, 0, 0, 0, 0, 0)

BASE: dict[Pista, Padrao] = {
    Pista.SD1: SD1,
    Pista.SD2: SD2,
    Pista.PD_G: PD_G,
    Pista.PD_P: PD_P,
    Pista.PD_T: PD_T,
    Pista.TB: TB_BASE,
    Pista.CU_G: SILENCIO,
    Pista.CU_A: SILENCIO,
}

VARIANTES_TB: dict[Terminal, Padrao] = {
    Terminal.TB1: TB_V1,
    Terminal.TB2: TB_V2,
    Terminal.TB3: TB_V3,
}

VARIANTES_PD: dict[Terminal, dict[Pista, Padrao]] = {
    Terminal.PD1: {Pista.PD_T: PD_T_V1},
    Terminal.PD2: {Pista.PD_G: PD_G_V2},
}

VARIANTES_CU: dict[Terminal, dict[Pista, Padrao]] = {
    Terminal.CU1: {Pista.CU_A: CU_A_V1, Pista.CU_G: CU_G_V1},
    Terminal.CU2: {Pista.CU_A: CU_A_V2, Pista.CU_G: CU_G_V2},
    Terminal.CU3: {Pista.CU_A: CU_A_V3, Pista.CU_G: CU_G_V3},
    Terminal.CU4: {Pista.CU_A: CU_A_V4, Pista.CU_G: CU_G_V4},
}

PISTAS_DA_FIGURA = frozenset({Pista.SD1, Pista.SD2, Pista.TB, Pista.PD_T, Pista.CU_A})


class Vocabulario:
    def arranjo(self, terminal: Terminal) -> dict[Pista, list[int]]:
        padroes = self._padroes(terminal)
        return {pista: list(padroes[pista]) for pista in Pista}

    def _padroes(self, terminal: Terminal) -> dict[Pista, Padrao]:
        match terminal:
            case Terminal.CONT:
                return {pista: CONTAGEM if pista == Pista.TB else SILENCIO for pista in Pista}
            case Terminal.FINAL:
                return {pista: ACENTO_FINAL if pista in PISTAS_DA_FIGURA else SILENCIO for pista in Pista}
            case Terminal.VIRADA:
                return self._fim_de_frase(UNI)
            case Terminal.BREQUE:
                return self._fim_de_frase(BRQ)
            case Terminal.TB1 | Terminal.TB2 | Terminal.TB3:
                return BASE | {Pista.TB: VARIANTES_TB[terminal]}
            case Terminal.PD1 | Terminal.PD2:
                return BASE | VARIANTES_PD[terminal]
            case Terminal.CU1 | Terminal.CU2 | Terminal.CU3 | Terminal.CU4:
                return BASE | VARIANTES_CU[terminal]
            case Terminal.BASE:
                return dict(BASE)

    def _fim_de_frase(self, figura: Padrao) -> dict[Pista, Padrao]:
        return {
            pista: padrao[:PASSOS_POR_COMPASSO] + (figura if pista in PISTAS_DA_FIGURA else SILENCIO[:PASSOS_POR_COMPASSO])
            for pista, padrao in BASE.items()
        }
