import random

from src.hiperparametros import Hiperparametros
from src.terminais import Terminal

CICLOS_POR_FRASE = 4

PESOS_TB: dict[Terminal, float] = {Terminal.TB1: 0.40, Terminal.TB2: 0.35, Terminal.TB3: 0.25}
PESOS_PD: dict[Terminal, float] = {Terminal.PD1: 0.5, Terminal.PD2: 0.5}
PESO_DO_TAMBORIM = 0.5
CUICA_REPETIDA = Terminal.CU1
FRASES_DA_CUICA = (Terminal.CU1, Terminal.CU2, Terminal.CU3, Terminal.CU4)


class Gramatica:
    def __init__(self, hiper: Hiperparametros, seed: int):
        self.hiper = hiper
        self.rng = random.Random(seed)

    def musica(self) -> list[Terminal]:
        return [Terminal.CONT, *self.blocos(1), Terminal.FINAL]

    def blocos(self, n: int) -> list[Terminal]:
        if n < self.hiper.max_blocos and self.sorteia(self.hiper.p):
            return self.bloco() + self.blocos(n + 1)
        return self.bloco()

    def bloco(self) -> list[Terminal]:
        return self.frase_a() + self.frase_b()

    def frase_a(self) -> list[Terminal]:
        fim = Terminal.VIRADA if self.sorteia(self.hiper.va) else self.ciclo()
        return self.miolo() + [fim]

    def frase_b(self) -> list[Terminal]:
        fim = Terminal.BREQUE if self.sorteia(self.hiper.b) else Terminal.VIRADA
        return self.miolo() + [fim]

    def miolo(self) -> list[Terminal]:
        return [self.ciclo() for _ in range(CICLOS_POR_FRASE - 1)]

    def ciclo(self) -> Terminal:
        sorteio = self.rng.random()
        if sorteio < self.hiper.epsilon:
            return self.variante()
        if sorteio < self.hiper.epsilon + self.hiper.cuica_presenca:
            return self.cuica()
        return Terminal.BASE

    def variante(self) -> Terminal:
        pesos = PESOS_TB if self.sorteia(PESO_DO_TAMBORIM) else PESOS_PD
        return self.escolhe(pesos)

    def cuica(self) -> Terminal:
        if self.sorteia(self.hiper.cuica_variedade):
            return self.rng.choice(FRASES_DA_CUICA)
        return CUICA_REPETIDA

    def escolhe(self, pesos: dict[Terminal, float]) -> Terminal:
        return self.rng.choices(list(pesos), weights=list(pesos.values()))[0]

    def sorteia(self, probabilidade: float) -> bool:
        return self.rng.random() < probabilidade


def derivar(hiper: Hiperparametros, seed: int) -> list[Terminal]:
    return Gramatica(hiper, seed).musica()
