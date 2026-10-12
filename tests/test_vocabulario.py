import pytest

from src.arranjo import Grade
from src.pistas import Pista
from src.terminais import Terminal
from src.vocabulario import BASE, BRQ, CONTAGEM, PASSOS_POR_CICLO, UNI, VARIANTES_CU, VARIANTES_TB, Vocabulario

PRIMEIRO_COMPASSO = slice(0, 8)
SEGUNDO_COMPASSO = slice(8, 16)
ACENTO_UNICO = [2] + [0] * 15
SILENCIO = [0] * 16


def test_todo_padrao_base_tem_16_passos_com_valores_validos():
    for padrao in BASE.values():
        assert len(padrao) == PASSOS_POR_CICLO
        assert set(padrao) <= {0, 1, 2}


def test_todo_arranjo_cobre_todas_as_pistas_com_16_passos():
    vocabulario = Vocabulario()

    for terminal in Terminal:
        arranjo = vocabulario.arranjo(terminal)
        assert set(arranjo) == set(Pista)
        assert all(len(padrao) == PASSOS_POR_CICLO for padrao in arranjo.values())


def test_base_usa_os_padroes_base():
    arranjo = Vocabulario().arranjo(Terminal.BASE)

    assert arranjo == {pista: list(padrao) for pista, padrao in BASE.items()}


@pytest.mark.parametrize("terminal", [Terminal.TB1, Terminal.TB2, Terminal.TB3])
def test_variante_de_tamborim_so_troca_o_tamborim(terminal: Terminal):
    vocabulario = Vocabulario()
    base = vocabulario.arranjo(Terminal.BASE)

    arranjo = vocabulario.arranjo(terminal)

    assert arranjo[Pista.TB] == list(VARIANTES_TB[terminal])
    assert {p: v for p, v in arranjo.items() if p != Pista.TB} == {p: v for p, v in base.items() if p != Pista.TB}


@pytest.mark.parametrize("terminal", [Terminal.TB1, Terminal.TB2, Terminal.TB3])
def test_variante_de_tamborim_muda_no_maximo_3_casas(terminal: Terminal):
    diferencas = sum(a != b for a, b in zip(VARIANTES_TB[terminal], BASE[Pista.TB]))

    assert 0 < diferencas <= 3


def test_pd1_desloca_o_tapa_e_pd2_antecipa_o_grave():
    vocabulario = Vocabulario()
    base = vocabulario.arranjo(Terminal.BASE)

    pd1 = vocabulario.arranjo(Terminal.PD1)
    pd2 = vocabulario.arranjo(Terminal.PD2)

    assert pd1[Pista.PD_T] != base[Pista.PD_T]
    assert pd1[Pista.PD_G] == base[Pista.PD_G]
    assert pd2[Pista.PD_G] != base[Pista.PD_G]
    assert pd2[Pista.PD_T] == base[Pista.PD_T]


@pytest.mark.parametrize(("terminal", "figura"), [(Terminal.VIRADA, UNI), (Terminal.BREQUE, BRQ)])
def test_virada_e_breque_mantem_o_primeiro_compasso_e_tocam_a_figura_juntos(terminal: Terminal, figura: tuple[int, ...]):
    vocabulario = Vocabulario()
    base = vocabulario.arranjo(Terminal.BASE)

    arranjo = vocabulario.arranjo(terminal)

    for pista in Pista:
        assert arranjo[pista][PRIMEIRO_COMPASSO] == base[pista][PRIMEIRO_COMPASSO]
    for pista in (Pista.SD1, Pista.SD2, Pista.TB, Pista.PD_T, Pista.CU_A):
        assert arranjo[pista][SEGUNDO_COMPASSO] == list(figura)
    for pista in (Pista.PD_G, Pista.PD_P, Pista.CU_G):
        assert arranjo[pista][SEGUNDO_COMPASSO] == [0] * 8


def test_cont_so_tem_a_contagem_no_tamborim():
    arranjo = Vocabulario().arranjo(Terminal.CONT)

    assert arranjo[Pista.TB] == list(CONTAGEM)
    assert all(arranjo[p] == SILENCIO for p in Pista if p != Pista.TB)


def test_final_e_um_acento_unico_com_a_aguda_da_cuica():
    arranjo = Vocabulario().arranjo(Terminal.FINAL)

    for pista in (Pista.SD1, Pista.SD2, Pista.PD_T, Pista.TB, Pista.CU_A):
        assert arranjo[pista] == ACENTO_UNICO
    for pista in (Pista.PD_G, Pista.PD_P, Pista.CU_G):
        assert arranjo[pista] == SILENCIO


def test_cuica_nao_toca_na_levada():
    vocabulario = Vocabulario()

    for terminal in (Terminal.CONT, Terminal.BASE, Terminal.TB1, Terminal.TB2, Terminal.TB3, Terminal.PD1, Terminal.PD2):
        arranjo = vocabulario.arranjo(terminal)
        assert arranjo[Pista.CU_G] == SILENCIO
        assert arranjo[Pista.CU_A] == SILENCIO


def sons_da_cuica(aguda: tuple[int, ...] | list[int], grave: tuple[int, ...] | list[int]) -> str:
    return " ".join("a" if a else "G" if g else "." for a, g in zip(aguda, grave))


CUICAS = (Terminal.CU1, Terminal.CU2, Terminal.CU3, Terminal.CU4)


@pytest.mark.parametrize("terminal", CUICAS)
def test_variante_de_cuica_so_mexe_na_cuica(terminal: Terminal):
    vocabulario = Vocabulario()
    base = vocabulario.arranjo(Terminal.BASE)

    arranjo = vocabulario.arranjo(terminal)

    for pista in (Pista.CU_G, Pista.CU_A):
        assert arranjo[pista] == list(VARIANTES_CU[terminal][pista])
    assert not any(a and g for a, g in zip(arranjo[Pista.CU_A], arranjo[Pista.CU_G]))
    assert {p: v for p, v in arranjo.items() if p not in (Pista.CU_G, Pista.CU_A)} == {
        p: v for p, v in base.items() if p not in (Pista.CU_G, Pista.CU_A)
    }


def test_variantes_de_cuica_sao_todas_diferentes():
    frases = {sons_da_cuica(VARIANTES_CU[t][Pista.CU_A], VARIANTES_CU[t][Pista.CU_G]) for t in CUICAS}

    assert len(frases) == len(CUICAS)


def test_frases_das_variantes_de_cuica():
    frases = {t: sons_da_cuica(VARIANTES_CU[t][Pista.CU_A], VARIANTES_CU[t][Pista.CU_G]) for t in CUICAS}

    assert frases[Terminal.CU1] == ". . . a G G G . . . . a G . a ."
    assert frases[Terminal.CU2] == ". a . G . a . G . a G G G . . ."
    assert frases[Terminal.CU3] == "a . G . a a . G . G . . a a a ."
    assert frases[Terminal.CU4] == ". a G . G . G . . a G G G G G ."


def test_acentos_das_frases_de_cuica():
    acentos = {
        t: [i for i in range(16) if 2 in (VARIANTES_CU[t][Pista.CU_A][i], VARIANTES_CU[t][Pista.CU_G][i])] for t in CUICAS
    }

    assert acentos == {Terminal.CU1: [11], Terminal.CU2: [10], Terminal.CU3: [], Terminal.CU4: []}


def test_grade_concatena_os_ciclos_na_ordem_da_derivacao():
    vocabulario = Vocabulario()
    derivacao = [Terminal.CONT, Terminal.BASE, Terminal.TB2, Terminal.FINAL]

    grade = Grade.de_derivacao(derivacao, vocabulario)

    assert grade.passos == 4 * PASSOS_POR_CICLO
    assert grade.pistas[Pista.TB][0:16] == list(CONTAGEM)
    assert grade.pistas[Pista.TB][32:48] == list(VARIANTES_TB[Terminal.TB2])
    assert grade.pistas[Pista.SD1][16:32] == list(BASE[Pista.SD1])
    assert grade.pistas[Pista.SD1][48] == 2
