import shutil
from pathlib import Path

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

from src.audio import ArquivoDeAudio
from src.pistas import Camada, Pista
from src.render_gm import RenderizadorGM
from src.sampler import BibliotecaDeSamples, Sampler

SR = 44100


def escrever_amostra(raiz: Path, pista: Pista, camada: Camada, nome: str, valor: float) -> None:
    pasta = raiz / pista.especificacao.pasta / camada.value
    pasta.mkdir(parents=True, exist_ok=True)
    audio = np.zeros(10)
    audio[0] = valor
    sf.write(pasta / nome, audio, SR, subtype="FLOAT")


def midi_com(notas: list[tuple[float, int, int]]) -> pretty_midi.PrettyMIDI:
    midi = pretty_midi.PrettyMIDI(initial_tempo=90)
    instrumento = pretty_midi.Instrument(program=0, is_drum=True)
    for inicio, nota, velocidade in notas:
        instrumento.notes.append(pretty_midi.Note(velocity=velocidade, pitch=nota, start=inicio, end=inicio + 0.1))
    midi.instruments.append(instrumento)
    return midi


def test_sampler_soma_a_amostra_no_instante_com_ganho_da_velocidade(tmp_path: Path):
    escrever_amostra(tmp_path, Pista.SD1, Camada.V1, "a.wav", 0.5)
    sampler = Sampler(BibliotecaDeSamples(tmp_path), seed=1)

    audio = sampler.renderizar(midi_com([(0.5, 41, 80)]))

    esperado = 0.5 * (80 / 127) ** 1.7 * Pista.SD1.especificacao.ganho
    assert audio[int(0.5 * SR)] == pytest.approx(esperado, rel=1e-4)
    assert np.count_nonzero(audio) == 1


def test_sampler_usa_a_camada_v2_a_partir_de_velocidade_95(tmp_path: Path):
    escrever_amostra(tmp_path, Pista.TB, Camada.V1, "a.wav", 0.1)
    escrever_amostra(tmp_path, Pista.TB, Camada.V2, "b.wav", 0.9)
    sampler = Sampler(BibliotecaDeSamples(tmp_path), seed=1)

    audio = sampler.renderizar(midi_com([(0.0, 65, 94), (1.0, 65, 95)]))

    ganho = Pista.TB.especificacao.ganho
    assert audio[0] == pytest.approx(0.1 * (94 / 127) ** 1.7 * ganho, rel=1e-4)
    assert audio[SR] == pytest.approx(0.9 * (95 / 127) ** 1.7 * ganho, rel=1e-4)


def test_sampler_cai_na_outra_camada_quando_uma_falta(tmp_path: Path):
    escrever_amostra(tmp_path, Pista.TB, Camada.V1, "a.wav", 0.4)
    sampler = Sampler(BibliotecaDeSamples(tmp_path), seed=1)

    audio = sampler.renderizar(midi_com([(0.0, 65, 120)]))

    assert audio[0] > 0


def test_round_robin_nao_repete_a_mesma_amostra_seguida_e_usa_todas(tmp_path: Path):
    valores = [0.2, 0.4, 0.6]
    for k, valor in enumerate(valores):
        escrever_amostra(tmp_path, Pista.PD_P, Camada.V1, f"{k}.wav", valor)
    sampler = Sampler(BibliotecaDeSamples(tmp_path), seed=1)
    ganho = (80 / 127) ** 1.7 * Pista.PD_P.especificacao.ganho

    audio = sampler.renderizar(midi_com([(0.1 * k, 54, 80) for k in range(60)]))

    escolhidos = [round(audio[int(round(0.1 * k * SR))] / ganho, 3) for k in range(60)]
    assert set(escolhidos) == set(valores)
    assert all(a != b for a, b in zip(escolhidos, escolhidos[1:]))


def test_round_robin_e_deterministico_pela_seed(tmp_path: Path):
    for k in range(4):
        escrever_amostra(tmp_path, Pista.PD_P, Camada.V1, f"{k}.wav", 0.1 * (k + 1))
    biblioteca = BibliotecaDeSamples(tmp_path)
    midi = midi_com([(0.1 * k, 54, 80) for k in range(30)])

    a = Sampler(biblioteca, seed=7).renderizar(midi)
    b = Sampler(biblioteca, seed=7).renderizar(midi)
    c = Sampler(biblioteca, seed=8).renderizar(midi)

    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_sampler_recusa_pista_sem_amostras(tmp_path: Path):
    escrever_amostra(tmp_path, Pista.SD1, Camada.V1, "a.wav", 0.5)
    sampler = Sampler(BibliotecaDeSamples(tmp_path), seed=1)

    with pytest.raises(ValueError, match="cuica/grave"):
        sampler.renderizar(midi_com([(0.0, 78, 80)]))


def test_biblioteca_existe_so_com_wavs(tmp_path: Path):
    assert not BibliotecaDeSamples.existe(tmp_path / "nada")
    assert not BibliotecaDeSamples.existe(tmp_path)
    escrever_amostra(tmp_path, Pista.SD1, Camada.V1, "a.wav", 0.5)
    assert BibliotecaDeSamples.existe(tmp_path)


def test_audio_normaliza_o_pico_para_menos_1_dbfs():
    audio = np.array([0.0, 0.3, -2.0, 1.0])

    normalizado = ArquivoDeAudio.normalizar(audio)

    assert np.max(np.abs(normalizado)) == pytest.approx(10 ** (-1 / 20))
    assert normalizado[2] < 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")
def test_audio_salva_wav_e_mp3(tmp_path: Path):
    audio = np.sin(2 * np.pi * 440 * np.arange(SR) / SR)

    wav, mp3 = ArquivoDeAudio(SR).salvar(audio, tmp_path / "x")

    assert sf.info(wav).samplerate == SR
    assert mp3.stat().st_size > 1000


@pytest.mark.parametrize("soundfont", [RenderizadorGM.soundfont_do_sistema(), None])
def test_render_gm_produz_audio_audivel(soundfont: Path | None):
    audio = RenderizadorGM(soundfont).renderizar(midi_com([(0.0, 41, 100), (0.3, 65, 100)]))

    assert audio.size > SR * 0.3
    assert np.max(np.abs(audio)) > 0.01
