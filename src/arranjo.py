from collections.abc import Sequence
from dataclasses import dataclass

from src.pistas import Pista
from src.terminais import Terminal
from src.vocabulario import PASSOS_POR_CICLO, PASSOS_POR_COMPASSO, Vocabulario

SIMBOLOS = {0: ".", 1: "x", 2: "X"}


@dataclass(frozen=True)
class Grade:
    pistas: dict[Pista, list[int]]

    @property
    def passos(self) -> int:
        return len(self.pistas[Pista.SD1])

    @property
    def ciclos(self) -> int:
        return self.passos // PASSOS_POR_CICLO

    @classmethod
    def de_derivacao(cls, derivacao: Sequence[Terminal], vocabulario: Vocabulario) -> "Grade":
        pistas: dict[Pista, list[int]] = {pista: [] for pista in Pista}
        for terminal in derivacao:
            for pista, padrao in vocabulario.arranjo(terminal).items():
                pistas[pista].extend(padrao)
        return cls(pistas=pistas)

    def como_texto(self, derivacao: Sequence[Terminal]) -> str:
        ativas = [pista for pista in Pista if any(self.pistas[pista])]
        blocos: list[str] = []
        for ciclo, terminal in enumerate(derivacao):
            linhas = [f"ciclo {ciclo}: {terminal.value}"]
            inicio = ciclo * PASSOS_POR_CICLO
            for pista in ativas:
                passos = [SIMBOLOS[v] for v in self.pistas[pista][inicio : inicio + PASSOS_POR_CICLO]]
                compassos = [" ".join(passos[i : i + PASSOS_POR_COMPASSO]) for i in range(0, PASSOS_POR_CICLO, PASSOS_POR_COMPASSO)]
                linhas.append(f"{pista.value:<6}" + " | ".join(compassos))
            blocos.append("\n".join(linhas))
        return "\n\n".join(blocos)
