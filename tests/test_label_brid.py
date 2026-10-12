from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from src.pistas import Camada
from tools.label_brid import Articulacao, BibliotecaProvisoria, LinhaRotulavel, Rotulador, histograma_no_compasso
from tools.slice_brid import Instrumento

SR = 44100


def linha(
    k: int,
    *,
    graves: float = 0.5,
    centroide: float = 1000.0,
    decaimento: float = 50.0,
    rms: float = 0.1,
    posicao: int = 0,
    f0: float = float("nan"),
    nivel_final: float = -40.0,
) -> LinhaRotulavel:
    return LinhaRotulavel(
        arquivo=f"x/{k:03d}.wav",
        gid=1,
        beat=k,
        posicao=posicao,
        rms=rms,
        centroide_hz=centroide,
        razao_graves=graves,
        decaimento_ms=decaimento,
        f0_hz=f0,
        nivel_final_db=nivel_final,
    )


def grupo(inicio: int, n: int, **kwargs: float) -> list[LinhaRotulavel]:
    rng = np.random.default_rng(inicio)
    return [
        linha(
            inicio + k,
            graves=float(kwargs["graves"] + rng.normal(0, 0.01)),
            centroide=float(kwargs["centroide"] * (1 + rng.normal(0, 0.01))),
            decaimento=float(kwargs["decaimento"] + rng.normal(0, 1)),
            rms=float(0.05 + 0.01 * k),
        )
        for k in range(n)
    ]


def test_pandeiro_nomeia_grave_platinela_e_tapa_pelas_features():
    graves = grupo(0, 10, graves=0.75, centroide=6000, decaimento=120)
    platinela = grupo(100, 10, graves=0.05, centroide=8000, decaimento=60)
    tapa = grupo(200, 10, graves=0.35, centroide=7500, decaimento=130)

    rotulos = Rotulador().rotular(Instrumento.PANDEIRO, graves + platinela + tapa)

    assert {rotulos[l.arquivo] for l in graves} == {Articulacao.GRAVE}
    assert {rotulos[l.arquivo] for l in platinela} == {Articulacao.PLATINELA}
    assert {rotulos[l.arquivo] for l in tapa} == {Articulacao.TAPA}


def test_surdo_aberto_e_o_de_decaimento_longo():
    linhas = [linha(k, decaimento=float(10 * k)) for k in range(10)]

    rotulos = Rotulador().rotular(Instrumento.SURDO1, linhas)

    assert set(rotulos) == {f"x/{k:03d}.wav" for k in range(6, 10)}
    assert set(rotulos.values()) == {Articulacao.ABERTO}


def test_cuica_separa_grave_e_aguda_pelo_f0_e_ignora_recortes_sem_altura():
    grave = [linha(k, f0=300.0 + k, centroide=1500.0) for k in range(8)]
    aguda = [linha(100 + k, f0=750.0 + k, centroide=1200.0) for k in range(8)]
    sem_altura = [linha(200 + k) for k in range(3)]

    rotulos = Rotulador().rotular(Instrumento.CUICA, grave + aguda + sem_altura)

    assert {rotulos[l.arquivo] for l in grave} == {Articulacao.GRAVE}
    assert {rotulos[l.arquivo] for l in aguda} == {Articulacao.AGUDA}
    assert not {l.arquivo for l in sem_altura} & set(rotulos)


def test_camadas_v2_sao_as_mais_fortes_e_v1_ignora_as_fantasmas():
    linhas = [linha(k, rms=0.01 * (k + 1)) for k in range(100)]

    camadas = BibliotecaProvisoria.separar_camadas(linhas)

    rms_v1 = [l.rms for l in camadas[Camada.V1]]
    rms_v2 = [l.rms for l in camadas[Camada.V2]]
    assert min(rms_v2) > max(rms_v1)
    assert min(rms_v1) >= 0.40
    assert min(rms_v2) >= 0.70


def test_escolha_prefere_os_recortes_tipicos():
    tipicos = [linha(k, graves=0.5, centroide=1000, decaimento=50) for k in range(6)]
    atipicos = [linha(100 + k, graves=0.9, centroide=4000, decaimento=300) for k in range(2)]

    escolhidos = BibliotecaProvisoria.mais_tipicos(tipicos + atipicos, quantidade=6)

    assert {l.arquivo for l in escolhidos} == {l.arquivo for l in tipicos}


def test_biblioteca_copia_para_pasta_da_pista_com_ganho_unico_por_instrumento(tmp_path: Path):
    origem = tmp_path / "raw"
    linhas: list[LinhaRotulavel] = []
    for k in range(40):
        arquivo = f"tamborim/{k:03d}.wav"
        (origem / "tamborim").mkdir(parents=True, exist_ok=True)
        sf.write(origem / arquivo, np.full(100, 0.01 * (k + 1)), SR)
        linhas.append(
            LinhaRotulavel(
                arquivo=arquivo,
                gid=214,
                beat=k,
                posicao=0,
                rms=0.01 * (k + 1),
                centroide_hz=2000,
                razao_graves=0,
                decaimento_ms=20,
                f0_hz=float("nan"),
                nivel_final_db=-40.0,
            )
        )
    destino = tmp_path / "samples"

    curadoria = BibliotecaProvisoria(origem, destino, quantidade=4).montar(
        Instrumento.TAMBORIM, {l.arquivo: Articulacao.BATIDA for l in linhas}, linhas
    )

    v1 = sorted((destino / "tamborim/batida/v1").glob("*.wav"))
    v2 = sorted((destino / "tamborim/batida/v2").glob("*.wav"))
    assert len(v1) == 4
    assert len(v2) == 4
    picos = [float(np.max(np.abs(sf.read(p)[0]))) for p in v1 + v2]
    assert max(picos) == pytest.approx(10 ** (-1 / 20), abs=1e-3)
    assert max(picos[:4]) < min(picos[4:])
    assert len(curadoria) == 8


def test_histograma_conta_articulacao_por_passo_do_compasso():
    linhas = [linha(0, posicao=0), linha(1, posicao=3), linha(3, posicao=0)]
    rotulos = {linhas[0].arquivo: Articulacao.GRAVE, linhas[1].arquivo: Articulacao.TAPA, linhas[2].arquivo: Articulacao.GRAVE}

    contagem = histograma_no_compasso(rotulos, linhas)

    assert contagem[Articulacao.GRAVE] == [1, 0, 0, 0, 1, 0, 0, 0]
    assert contagem[Articulacao.TAPA] == [0, 0, 0, 0, 0, 0, 0, 1]


def test_refazer_um_instrumento_preserva_a_biblioteca_dos_outros(tmp_path: Path):
    from tools import label_brid

    recortes = tmp_path / "raw"
    (recortes / "tamborim").mkdir(parents=True)
    colunas = "arquivo,instrumento,gid,beat,posicao,rms,centroide_hz,razao_graves,decaimento_ms,f0_hz,nivel_final_db"
    linhas_manifesto = [colunas]
    for k in range(20):
        arquivo = f"tamborim/0214_{k:03d}.wav"
        sf.write(recortes / arquivo, np.full(100, 0.01 * (k + 1)), SR)
        linhas_manifesto.append(f"{arquivo},tamborim,214,{k},0,{0.01 * (k + 1)},2000,0,20,nan,-5.0")
    (recortes / "manifest.csv").write_text("\n".join(linhas_manifesto) + "\n")
    samples = tmp_path / "samples"
    (samples / "pandeiro/grave/v1").mkdir(parents=True)
    sf.write(samples / "pandeiro/grave/v1/0185_001.wav", np.zeros(10), SR)
    (samples / "curadoria.csv").write_text(
        "destino,origem,instrumento,articulacao,camada,rms\npandeiro/grave/v1/0185_001.wav,pandeiro/0185_001.wav,pandeiro,grave,v1,0.1\n"
    )

    label_brid.main(["--recortes", str(recortes), "--saida", str(samples), "--instrumentos", "tamborim", "--por-camada", "2"])

    assert (samples / "pandeiro/grave/v1/0185_001.wav").exists()
    assert len(list((samples / "tamborim/batida").rglob("*.wav"))) == 4
    curadoria = (samples / "curadoria.csv").read_text()
    assert "pandeiro/grave/v1/0185_001.wav" in curadoria
    assert curadoria.count("tamborim,batida") == 4


def test_escolha_considera_o_f0_quando_ha_altura():
    afinadas = [linha(k, f0=750.0 + k) for k in range(1, 7)]
    desafinada = [linha(0, f0=530.0)]

    escolhidos = BibliotecaProvisoria.mais_tipicos(afinadas + desafinada, quantidade=6)

    assert {l.arquivo for l in escolhidos} == {l.arquivo for l in afinadas}


def escrever_recortes(origem: Path, linhas: list[LinhaRotulavel]) -> None:
    for l in linhas:
        (origem / l.arquivo).parent.mkdir(parents=True, exist_ok=True)
        sf.write(origem / l.arquivo, np.full(100, l.rms), SR)


def test_cuica_descarta_recortes_cortados_ainda_soando(tmp_path: Path):
    inteiras = [linha(k, rms=0.01 * (k + 1), f0=750.0, nivel_final=-30.0) for k in range(20)]
    cortadas = [linha(100 + k, rms=0.01 * (k + 1), f0=750.0, nivel_final=-10.0) for k in range(20)]
    escrever_recortes(tmp_path / "raw", inteiras + cortadas)
    rotulos = {l.arquivo: Articulacao.AGUDA for l in inteiras + cortadas}

    curadoria = BibliotecaProvisoria(tmp_path / "raw", tmp_path / "samples", quantidade=4).montar(
        Instrumento.CUICA, rotulos, inteiras + cortadas
    )

    origens = {c.origem for c in curadoria}
    assert origens
    assert origens <= {l.arquivo for l in inteiras}


def test_outros_instrumentos_nao_filtram_pelo_nivel_final(tmp_path: Path):
    linhas = [linha(k, rms=0.01 * (k + 1), nivel_final=-5.0) for k in range(20)]
    escrever_recortes(tmp_path / "raw", linhas)

    curadoria = BibliotecaProvisoria(tmp_path / "raw", tmp_path / "samples", quantidade=4).montar(
        Instrumento.TAMBORIM, {l.arquivo: Articulacao.BATIDA for l in linhas}, linhas
    )

    assert len(curadoria) == 8
