from dataclasses import dataclass

PROBABILIDADES = ("epsilon", "p", "va", "b", "cuica_presenca", "cuica_variedade")


@dataclass(frozen=True)
class Hiperparametros:
    epsilon: float = 0.15
    p: float = 0.8
    va: float = 0.3
    b: float = 0.3
    max_blocos: int = 10
    cuica_presenca: float = 0.25
    cuica_variedade: float = 0.5

    def __post_init__(self) -> None:
        for campo in PROBABILIDADES:
            valor = getattr(self, campo)
            if not 0.0 <= valor <= 1.0:
                raise ValueError(f"{campo} precisa estar em [0, 1], recebeu {valor}")
        if self.epsilon + self.cuica_presenca > 1.0:
            raise ValueError(
                f"epsilon + cuica_presenca precisa ser ≤ 1, recebeu {self.epsilon} + {self.cuica_presenca}"
            )
        if self.max_blocos < 1:
            raise ValueError(f"max_blocos precisa ser ≥ 1, recebeu {self.max_blocos}")
