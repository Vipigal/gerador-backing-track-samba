from collections import Counter

import pytest

from src import gramatica
from src.hiperparametros import Hiperparametros
from src.terminais import MARCAS_DE_FORMA, VARIANTES_DE_CUICA, Terminal

CICLOS_POR_BLOCO = 8
FIM_DE_FRASE_A = 3
FIM_DE_FRASE_B = 7
SEEDS = range(300)


def derivar(hiper: Hiperparametros, seed: int) -> list[Terminal]:
    try:
        return gramatica.derivar(hiper, seed)
    except NotImplementedError:
        pytest.skip("gramatica.derivar ainda não foi implementada")


def blocos(derivacao: list[Terminal]) -> list[list[Terminal]]:
    miolo = derivacao[1:-1]
    return [miolo[i : i + CICLOS_POR_BLOCO] for i in range(0, len(miolo), CICLOS_POR_BLOCO)]


VARIANTES_TB_PD = frozenset({Terminal.TB1, Terminal.TB2, Terminal.TB3, Terminal.PD1, Terminal.PD2})


def fracao(derivacao: list[Terminal], terminais: frozenset[Terminal]) -> float:
    miolo = derivacao[1:-1]
    return sum(t in terminais for t in miolo) / len(miolo)


def media_da_fracao(hiper: Hiperparametros, terminais: frozenset[Terminal], seeds: int = 2000) -> float:
    return sum(fracao(derivar(hiper, seed), terminais) for seed in range(seeds)) / seeds


def test_mesma_seed_gera_a_mesma_derivacao():
    hiper = Hiperparametros()

    assert derivar(hiper, 7) == derivar(hiper, 7)


def test_seeds_diferentes_geram_musicas_diferentes():
    hiper = Hiperparametros()

    derivacoes = {tuple(derivar(hiper, seed)) for seed in range(20)}

    assert len(derivacoes) > 1


def test_musica_comeca_com_cont_e_termina_com_final():
    hiper = Hiperparametros()

    for seed in SEEDS:
        derivacao = derivar(hiper, seed)
        assert derivacao[0] == Terminal.CONT
        assert derivacao[-1] == Terminal.FINAL
        assert Terminal.CONT not in derivacao[1:-1]
        assert Terminal.FINAL not in derivacao[1:-1]


def test_numero_de_ciclos_e_2_mais_8n_com_n_ate_max_blocos():
    hiper = Hiperparametros(max_blocos=4)

    for seed in SEEDS:
        ciclos = len(derivar(hiper, seed))
        n = (ciclos - 2) // CICLOS_POR_BLOCO
        assert ciclos == 2 + CICLOS_POR_BLOCO * n
        assert 1 <= n <= hiper.max_blocos


def test_p_zero_gera_um_bloco_so():
    hiper = Hiperparametros(p=0.0)

    for seed in SEEDS:
        assert len(derivar(hiper, seed)) == 2 + CICLOS_POR_BLOCO


def test_max_blocos_trunca_a_recursao():
    hiper = Hiperparametros(p=1.0, max_blocos=3)

    for seed in SEEDS:
        assert len(derivar(hiper, seed)) == 2 + CICLOS_POR_BLOCO * 3


def test_virada_e_breque_so_aparecem_no_fim_das_frases():
    hiper = Hiperparametros(epsilon=0.5, va=0.5, b=0.5)

    for seed in SEEDS:
        for bloco in blocos(derivar(hiper, seed)):
            for posicao, terminal in enumerate(bloco):
                if terminal == Terminal.VIRADA:
                    assert posicao in (FIM_DE_FRASE_A, FIM_DE_FRASE_B)
                if terminal == Terminal.BREQUE:
                    assert posicao == FIM_DE_FRASE_B


def test_fim_do_bloco_e_sempre_virada_ou_breque():
    hiper = Hiperparametros()

    for seed in SEEDS:
        for bloco in blocos(derivar(hiper, seed)):
            assert bloco[FIM_DE_FRASE_B] in MARCAS_DE_FORMA


def test_fim_da_frase_a_nunca_tem_breque():
    hiper = Hiperparametros(va=1.0, b=1.0)

    for seed in SEEDS:
        for bloco in blocos(derivar(hiper, seed)):
            assert bloco[FIM_DE_FRASE_A] == Terminal.VIRADA


def test_b_controla_breque_contra_virada_no_fim_do_bloco():
    so_breque = Hiperparametros(b=1.0)
    so_virada = Hiperparametros(b=0.0)

    for seed in SEEDS:
        assert all(bloco[FIM_DE_FRASE_B] == Terminal.BREQUE for bloco in blocos(derivar(so_breque, seed)))
        assert all(bloco[FIM_DE_FRASE_B] == Terminal.VIRADA for bloco in blocos(derivar(so_virada, seed)))


def test_epsilon_e_cuica_zero_so_geram_base_e_marcas_de_forma():
    hiper = Hiperparametros(epsilon=0.0, cuica_presenca=0.0)
    permitidos = {Terminal.BASE, Terminal.VIRADA, Terminal.BREQUE, Terminal.CONT, Terminal.FINAL}

    for seed in SEEDS:
        assert set(derivar(hiper, seed)) <= permitidos


def test_cuica_presenca_zero_nao_gera_cuica():
    hiper = Hiperparametros(epsilon=0.5, cuica_presenca=0.0)

    for seed in SEEDS:
        assert not VARIANTES_DE_CUICA & set(derivar(hiper, seed))


@pytest.mark.parametrize("epsilon", [0.1, 0.3, 0.6])
def test_taxa_de_tamborim_e_pandeiro_segue_a_curva_teorica(epsilon: float):
    hiper = Hiperparametros(epsilon=epsilon, va=0.3, cuica_presenca=0.0)

    assert media_da_fracao(hiper, VARIANTES_TB_PD) == pytest.approx(epsilon * (7 - hiper.va) / CICLOS_POR_BLOCO, abs=0.015)


@pytest.mark.parametrize("presenca", [0.1, 0.25, 0.4])
def test_presenca_da_cuica_segue_a_curva_teorica(presenca: float):
    hiper = Hiperparametros(epsilon=0.2, va=0.3, cuica_presenca=presenca)

    assert media_da_fracao(hiper, VARIANTES_DE_CUICA) == pytest.approx(presenca * (7 - hiper.va) / CICLOS_POR_BLOCO, abs=0.015)


@pytest.mark.parametrize("presenca", [0.0, 0.4])
def test_cuica_nao_muda_a_taxa_de_tamborim_e_pandeiro(presenca: float):
    hiper = Hiperparametros(epsilon=0.3, va=0.3, cuica_presenca=presenca)

    assert media_da_fracao(hiper, VARIANTES_TB_PD) == pytest.approx(0.3 * (7 - hiper.va) / CICLOS_POR_BLOCO, abs=0.015)


def test_variedade_zero_repete_sempre_cu1():
    hiper = Hiperparametros(cuica_presenca=0.5, cuica_variedade=0.0)

    cuicas = {t for seed in SEEDS for t in derivar(hiper, seed) if t in VARIANTES_DE_CUICA}

    assert cuicas == {Terminal.CU1}


@pytest.mark.parametrize("variedade", [0.5, 1.0])
def test_variedade_distribui_as_frases_da_cuica(variedade: float):
    hiper = Hiperparametros(epsilon=0.0, cuica_presenca=0.6, cuica_variedade=variedade)

    contagem = Counter(t for seed in range(2000) for t in derivar(hiper, seed) if t in VARIANTES_DE_CUICA)
    total = sum(contagem.values())

    assert contagem[Terminal.CU1] / total == pytest.approx(1 - 3 * variedade / 4, abs=0.03)
    for terminal in (Terminal.CU2, Terminal.CU3, Terminal.CU4):
        assert contagem[terminal] / total == pytest.approx(variedade / 4, abs=0.03)


def test_proporcoes_dentro_de_var_tb():
    hiper = Hiperparametros(epsilon=1.0, cuica_presenca=0.0)

    contagem = Counter(t for seed in range(2000) for t in derivar(hiper, seed))
    total_tb = contagem[Terminal.TB1] + contagem[Terminal.TB2] + contagem[Terminal.TB3]

    assert contagem[Terminal.TB1] / total_tb == pytest.approx(0.40, abs=0.03)
    assert contagem[Terminal.TB2] / total_tb == pytest.approx(0.35, abs=0.03)
    assert contagem[Terminal.TB3] / total_tb == pytest.approx(0.25, abs=0.03)
