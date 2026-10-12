import hashlib
import json
from pathlib import Path

import pretty_midi
import pytest

from src.arranjo import Grade
from src.hiperparametros import Hiperparametros
from src.midi_out import ArquivoMidi, Evento, ParametrosDeRender, RegistroDaMusica, Sequenciador
from src.pistas import Grupo, Pista
from src.terminais import Terminal
from src.vocabulario import Vocabulario

DERIVACAO = [Terminal.CONT, Terminal.BASE, Terminal.TB1, Terminal.VIRADA, Terminal.FINAL]
QUANTIZADO = ParametrosDeRender(bpm=90, sigma_tempo_s=0.0, sigma_velocidade=0.0)


def grade() -> Grade:
    return Grade.de_derivacao(DERIVACAO, Vocabulario())


def test_eventos_quantizados_caem_na_grade_de_semicolcheias():
    delta = 60 / (4 * 90)

    eventos = Sequenciador(QUANTIZADO, seed=1).eventos(grade())

    for evento in eventos:
        passo = evento.tempo_s / delta
        assert passo == pytest.approx(round(passo), abs=1e-9)


def test_eventos_reproduzem_cada_casa_ativa_da_grade():
    g = grade()

    eventos = Sequenciador(QUANTIZADO, seed=1).eventos(g)

    ativas = sum(1 for padrao in g.pistas.values() for valor in padrao if valor)
    assert len(eventos) == ativas


def test_velocidade_vem_do_valor_da_casa():
    eventos = Sequenciador(QUANTIZADO, seed=1).eventos(grade())

    assert {e.velocidade for e in eventos} == {78, 108}


def test_balanco_desloca_pela_posicao_no_tempo():
    delta = 60 / (4 * 90)
    parametros = ParametrosDeRender(
        bpm=90, balanco=0.5, microtiming=(0.0, 0.0, 0.0, -0.2), sigma_tempo_s=0.0, sigma_velocidade=0.0
    )

    eventos = Sequenciador(parametros, seed=1).eventos(grade())

    deslocamentos = {round(e.tempo_s / delta) % 4: e.tempo_s / delta - round(e.tempo_s / delta) for e in eventos}
    assert deslocamentos[0] == pytest.approx(0.0)
    assert deslocamentos[3] == pytest.approx(-0.1)


def test_humanizacao_e_deterministica_pela_seed():
    parametros = ParametrosDeRender(bpm=90)

    assert Sequenciador(parametros, seed=4).eventos(grade()) == Sequenciador(parametros, seed=4).eventos(grade())
    assert Sequenciador(parametros, seed=4).eventos(grade()) != Sequenciador(parametros, seed=5).eventos(grade())


def test_velocidade_humanizada_fica_entre_1_e_127_e_tempo_nao_e_negativo():
    parametros = ParametrosDeRender(bpm=90, sigma_tempo_s=1.0, sigma_velocidade=500.0)

    eventos = Sequenciador(parametros, seed=1).eventos(grade())

    assert all(1 <= e.velocidade <= 127 for e in eventos)
    assert all(e.tempo_s >= 0 for e in eventos)


def test_midi_tem_um_instrumento_de_percussao_por_grupo_com_notas_gm():
    eventos = [
        Evento(tempo_s=0.0, pista=Pista.SD1, velocidade=100),
        Evento(tempo_s=0.1, pista=Pista.SD2, velocidade=80),
        Evento(tempo_s=0.2, pista=Pista.PD_T, velocidade=90),
        Evento(tempo_s=0.3, pista=Pista.TB, velocidade=70),
    ]

    midi = ArquivoMidi(QUANTIZADO).montar(eventos)

    nomes = {i.name: i for i in midi.instruments}
    assert set(nomes) == {Grupo.SURDO.value, Grupo.PANDEIRO.value, Grupo.TAMBORIM.value}
    assert all(i.is_drum for i in midi.instruments)
    assert [n.pitch for n in nomes[Grupo.SURDO.value].notes] == [41, 43]
    assert nomes[Grupo.PANDEIRO.value].notes[0].pitch == 62
    nota = nomes[Grupo.TAMBORIM.value].notes[0]
    assert nota.end - nota.start == pytest.approx(0.9 * 60 / (4 * 90))
    assert nota.velocity == 70


def test_midi_salvo_tem_andamento_e_compasso_2_por_4(tmp_path: Path):
    arquivo = ArquivoMidi(QUANTIZADO)
    destino = tmp_path / "x.mid"

    arquivo.salvar(arquivo.montar(Sequenciador(QUANTIZADO, seed=1).eventos(grade())), destino)

    lido = pretty_midi.PrettyMIDI(str(destino))
    _, andamentos = lido.get_tempo_changes()
    assert andamentos[0] == pytest.approx(90, abs=0.01)
    assert (lido.time_signature_changes[0].numerator, lido.time_signature_changes[0].denominator) == (2, 4)


def test_mesma_seed_gera_midi_identico_byte_a_byte(tmp_path: Path):
    parametros = ParametrosDeRender(bpm=90)
    hashes = []
    for nome in ("a.mid", "b.mid"):
        arquivo = ArquivoMidi(parametros)
        destino = tmp_path / nome
        arquivo.salvar(arquivo.montar(Sequenciador(parametros, seed=3).eventos(grade())), destino)
        hashes.append(hashlib.sha256(destino.read_bytes()).hexdigest())

    assert hashes[0] == hashes[1]


def test_registro_guarda_seed_parametros_e_derivacao(tmp_path: Path):
    destino = tmp_path / "x.json"

    RegistroDaMusica(seed=3, hiperparametros=Hiperparametros(), render=QUANTIZADO, derivacao=DERIVACAO).salvar(destino)

    registro = json.loads(destino.read_text())
    assert registro["seed"] == 3
    assert registro["hiperparametros"]["epsilon"] == 0.15
    assert registro["render"]["bpm"] == 90
    assert registro["derivacao"] == ["cont", "base", "tb1", "virada", "final"]
    assert registro["ciclos"] == 5
