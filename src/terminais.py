from enum import StrEnum


class Terminal(StrEnum):
    CONT = "cont"
    FINAL = "final"
    BASE = "base"
    TB1 = "tb1"
    TB2 = "tb2"
    TB3 = "tb3"
    PD1 = "pd1"
    PD2 = "pd2"
    CU1 = "cu1"
    CU2 = "cu2"
    CU3 = "cu3"
    CU4 = "cu4"
    VIRADA = "virada"
    BREQUE = "breque"


VARIANTES = frozenset(
    {
        Terminal.TB1,
        Terminal.TB2,
        Terminal.TB3,
        Terminal.PD1,
        Terminal.PD2,
        Terminal.CU1,
        Terminal.CU2,
        Terminal.CU3,
        Terminal.CU4,
    }
)
VARIANTES_DE_CUICA = frozenset({Terminal.CU1, Terminal.CU2, Terminal.CU3, Terminal.CU4})
MARCAS_DE_FORMA = frozenset({Terminal.VIRADA, Terminal.BREQUE})
