from pathlib import Path

import numpy as np
import pytest

from tools.slice_brid import (
    SELECAO_BRID,
    CatalogoBrid,
    Curva,
    Descritores,
    Envelope,
    Estilo,
    FaixaBrid,
    Fatiador,
    FiltroPercentil,
    GradeDeBeats,
    Instrumento,
    Recorte,
)

SR = 44100
RAIZ_BRID = Path("brid")


def burst(duracao_s: float, decaimento_s: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(int(duracao_s * SR)) / SR
    return rng.standard_normal(t.size) * np.exp(-t / decaimento_s)


def trilha_de_cliques(bpm: float, fase_s: float, duracao_s: float) -> np.ndarray:
    rng = np.random.default_rng(0)
    y = np.zeros(int(duracao_s * SR))
    delta = 60 / bpm / 4
    passo = 0
    while fase_s + passo * delta < duracao_s - 0.1:
        inicio = int((fase_s + passo * delta) * SR)
        amplitude = 1.0 if passo % 4 == 0 else 0.25
        clique = amplitude * burst(0.03, 0.005, rng)
        y[inicio : inicio + clique.size] += clique
        passo += 1
    return y


def test_faixa_brid_le_o_nome_do_arquivo():
    faixa = FaixaBrid.de_caminho(Path("x/[0185] S2-PD2-01-SA.wav"))

    assert faixa.gid == 185
    assert faixa.instrumentista == 2
    assert faixa.codigo_instrumento == "PD2"
    assert faixa.numero == 1
    assert faixa.estilo == Estilo.SAMBA
    assert faixa.bpm == 80


def test_faixa_brid_le_samba_enredo_a_130():
    faixa = FaixaBrid.de_caminho(Path("[0279] S2-SU3-06-SE.wav"))

    assert faixa.estilo == Estilo.SAMBA_ENREDO
    assert faixa.bpm == 130


def test_faixa_brid_recusa_virada():
    with pytest.raises(ValueError):
        FaixaBrid.de_caminho(Path("[0114] S1-PD3-07-VSA.wav"))


@pytest.mark.skipif(not RAIZ_BRID.exists(), reason="pasta brid/ ausente")
def test_catalogo_encontra_todas_as_faixas_selecionadas():
    catalogo = CatalogoBrid(RAIZ_BRID)

    for gids in SELECAO_BRID.values():
        for gid in gids:
            assert catalogo.faixa(gid).caminho.exists()


def test_grade_localiza_passo_beat_e_desvio():
    grade = GradeDeBeats(t0=0.1, periodo=0.75)
    delta = 0.75 / 4

    posicao = grade.localizar(0.1 + 0.75 * 2 + 3 * delta + 0.1 * delta)

    assert posicao.beat == 2
    assert posicao.posicao == 3
    assert posicao.desvio == pytest.approx(0.1)


def test_grade_arredonda_para_o_passo_seguinte_quando_adiantado():
    grade = GradeDeBeats(t0=0.0, periodo=0.75)
    delta = 0.75 / 4

    posicao = grade.localizar(4 * delta - 0.2 * delta)

    assert posicao.beat == 1
    assert posicao.posicao == 0
    assert posicao.desvio == pytest.approx(-0.2)


def test_grade_ajusta_a_fase_com_bpm_fixo():
    bpm, fase = 80.0, 0.31
    y = trilha_de_cliques(bpm, fase, 20.0)

    grade = GradeDeBeats.ajustar(y, SR, bpm)

    assert grade.periodo == pytest.approx(0.75, abs=0.002)
    erro = (grade.t0 - fase + grade.periodo / 2) % grade.periodo - grade.periodo / 2
    assert abs(erro) < 0.02


def test_grade_acha_o_andamento_real_perto_do_nominal():
    bpm_real, fase = 81.2, 0.12
    y = trilha_de_cliques(bpm_real, fase, 20.0)

    grade = GradeDeBeats.ajustar(y, SR, 80.0)

    assert 60 / grade.periodo == pytest.approx(bpm_real, abs=0.1)
    ultimo_beat = fase + 24 * 60 / bpm_real
    posicao = grade.localizar(ultimo_beat)
    assert posicao.posicao == 0
    assert abs(posicao.desvio) < 0.1


def test_fatiador_recorta_entre_onsets_limitando_a_duracao():
    rng = np.random.default_rng(1)
    y = np.zeros(SR * 2)
    onsets = [int(0.1 * SR), int(0.6 * SR), int(1.1 * SR)]
    for inicio in onsets:
        som = burst(0.4, 0.05, rng)
        y[inicio : inicio + som.size] += som

    recortes = Fatiador(SR).recortar_em(y, np.array(onsets), duracao_max_s=0.2)

    assert len(recortes) == 3
    for recorte, inicio in zip(recortes, onsets):
        assert recorte.audio.size <= int(0.2 * SR)
        assert inicio <= recorte.inicio < inicio + int(0.005 * SR)


def test_fatiador_remove_silencio_inicial_e_aplica_fade_out():
    rng = np.random.default_rng(2)
    y = np.zeros(SR)
    som = burst(0.5, 0.2, rng)
    y[1000 : 1000 + som.size] = som

    recorte = Fatiador(SR).recortar_em(y, np.array([0]), duracao_max_s=0.3)[0]

    assert recorte.inicio >= 1000
    assert abs(recorte.audio[0]) >= 0.03 * np.max(np.abs(recorte.audio))
    assert recorte.audio[-1] == pytest.approx(0.0, abs=1e-9)
    assert np.max(np.abs(recorte.audio[-10:])) < np.max(np.abs(recorte.audio)) * 0.01


def test_fatiador_detecta_onsets_de_bursts():
    rng = np.random.default_rng(3)
    y = np.zeros(SR * 3)
    esperados = [0.3, 0.9, 1.5, 2.1, 2.6]
    for t in esperados:
        som = burst(0.2, 0.03, rng)
        y[int(t * SR) : int(t * SR) + som.size] += som

    recortes = Fatiador(SR).recortar(y, duracao_max_s=0.25)

    inicios = sorted(r.inicio / SR for r in recortes)
    assert inicios == pytest.approx(esperados[1:-1], abs=0.02)


def test_descritores_separam_grave_de_agudo():
    t = np.arange(int(0.2 * SR)) / SR
    grave = np.sin(2 * np.pi * 80 * t)
    agudo = np.sin(2 * np.pi * 4000 * t)

    d_grave = Descritores.extrair(grave, SR)
    d_agudo = Descritores.extrair(agudo, SR)

    assert d_grave.razao_graves > 0.9
    assert d_agudo.razao_graves < 0.05
    assert d_grave.centroide_hz == pytest.approx(80, rel=0.2)
    assert d_agudo.centroide_hz == pytest.approx(4000, rel=0.05)
    assert d_grave.duracao_ms == pytest.approx(200)
    assert d_grave.rms == pytest.approx(1 / np.sqrt(2), rel=0.01)


def test_descritores_medem_decaimento_ate_menos_20_db():
    t = np.arange(int(0.8 * SR)) / SR
    tau = 0.05
    som = np.sin(2 * np.pi * 200 * t) * np.exp(-t / tau)
    esperado_ms = tau * np.log(10) * 1000

    d = Descritores.extrair(som, SR)

    assert d.decaimento_ms == pytest.approx(esperado_ms, rel=0.15)


def test_filtro_percentil_descarta_extremos_de_duracao_e_rms():
    recortes = [Recorte(indice=k, inicio=k, audio=np.zeros(1), nivel_final_db=-40.0) for k in range(20)]
    descritores = [
        Descritores(duracao_ms=100.0 + k, rms=0.5, centroide_hz=0.0, razao_graves=0.0, decaimento_ms=0.0)
        for k in range(20)
    ]
    descritores[5] = Descritores(duracao_ms=110.0, rms=5.0, centroide_hz=0.0, razao_graves=0.0, decaimento_ms=0.0)

    mantidos = FiltroPercentil(10, 90).manter(list(zip(recortes, descritores)))

    indices = [r.indice for r, _ in mantidos]
    assert 0 not in indices
    assert 19 not in indices
    assert 5 not in indices
    assert 10 in indices


def test_descritores_medem_f0_so_quando_pedido():
    t = np.arange(int(0.2 * SR)) / SR
    som = np.sin(2 * np.pi * 300 * t)

    com_f0 = Descritores.extrair(som, SR, com_f0=True)
    sem_f0 = Descritores.extrair(som, SR)

    assert com_f0.f0_hz == pytest.approx(300, rel=0.03)
    assert np.isnan(sem_f0.f0_hz)


def test_descritores_sem_altura_definida_tem_f0_nan():
    ruido = np.random.default_rng(0).standard_normal(int(0.2 * SR))

    assert np.isnan(Descritores.extrair(ruido, SR, com_f0=True).f0_hz)


def test_cuica_tem_fades_suaves_e_os_outros_mantem_o_fade_curto():
    assert Instrumento.CUICA.envelope == Envelope(fade_in_s=0.005, fade_out_s=0.035, curva=Curva.COSSENO)
    for instrumento in (Instrumento.SURDO1, Instrumento.SURDO2, Instrumento.PANDEIRO, Instrumento.TAMBORIM):
        assert instrumento.envelope == Envelope(fade_in_s=0.0, fade_out_s=0.010, curva=Curva.LINEAR)


def test_fade_out_em_cosseno_cai_devagar_no_comeco():
    y = np.ones(SR)
    envelope = Envelope(fade_in_s=0.0, fade_out_s=0.040, curva=Curva.COSSENO)

    audio = Fatiador(SR, envelope).recortar_em(y, np.array([0]), duracao_max_s=0.2)[0].audio

    n = int(0.040 * SR)
    fade = audio[audio.size - n :]
    assert fade[n // 4] == pytest.approx(0.854, abs=0.01)
    assert fade[n // 2] == pytest.approx(0.5, abs=0.01)
    assert audio[-1] == pytest.approx(0.0, abs=1e-9)


def test_fade_in_sobe_de_zero_ate_o_sinal():
    y = np.ones(SR)
    envelope = Envelope(fade_in_s=0.005, fade_out_s=0.010, curva=Curva.COSSENO)

    audio = Fatiador(SR, envelope).recortar_em(y, np.array([0]), duracao_max_s=0.2)[0].audio

    n = int(0.005 * SR)
    assert audio[0] == pytest.approx(0.0, abs=1e-9)
    assert audio[n // 2] == pytest.approx(0.5, abs=0.02)
    assert audio[n] == pytest.approx(1.0)


def test_recorte_mede_o_nivel_do_fim_antes_do_fade():
    t = np.arange(SR) / SR
    sustentado = np.sin(2 * np.pi * 300 * t)
    decaido = sustentado * np.exp(-t / 0.02)
    fatiador = Fatiador(SR, Instrumento.CUICA.envelope)

    alto = fatiador.recortar_em(sustentado, np.array([0]), duracao_max_s=0.2)[0]
    baixo = fatiador.recortar_em(decaido, np.array([0]), duracao_max_s=0.2)[0]

    assert alto.nivel_final_db == pytest.approx(-3.0, abs=0.5)
    assert baixo.nivel_final_db < -30
