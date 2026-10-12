from collections.abc import Callable

import pytest

from src.hiperparametros import Hiperparametros


def test_padroes_da_cuica():
    hiper = Hiperparametros()

    assert hiper.cuica_presenca == 0.25
    assert hiper.cuica_variedade == 0.5


def test_epsilon_mais_presenca_da_cuica_nao_passa_de_1():
    with pytest.raises(ValueError, match="epsilon"):
        Hiperparametros(epsilon=0.8, cuica_presenca=0.3)

    assert Hiperparametros(epsilon=0.75, cuica_presenca=0.25).epsilon == 0.75


CONSTRUTORES: dict[str, Callable[[float], Hiperparametros]] = {
    "epsilon": lambda v: Hiperparametros(epsilon=v, cuica_presenca=0.0),
    "p": lambda v: Hiperparametros(p=v),
    "va": lambda v: Hiperparametros(va=v),
    "b": lambda v: Hiperparametros(b=v),
    "cuica_presenca": lambda v: Hiperparametros(epsilon=0.0, cuica_presenca=v),
    "cuica_variedade": lambda v: Hiperparametros(cuica_variedade=v),
}


@pytest.mark.parametrize("campo", list(CONSTRUTORES))
def test_probabilidades_ficam_entre_0_e_1(campo: str):
    with pytest.raises(ValueError, match=campo):
        CONSTRUTORES[campo](1.5)
    with pytest.raises(ValueError, match=campo):
        CONSTRUTORES[campo](-0.1)


def test_max_blocos_e_pelo_menos_1():
    with pytest.raises(ValueError, match="max_blocos"):
        Hiperparametros(max_blocos=0)
