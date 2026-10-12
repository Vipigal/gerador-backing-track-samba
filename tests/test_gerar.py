import json
from pathlib import Path

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import gerar
from src.arranjo import Grade
from src.terminais import Terminal
from src.vocabulario import Vocabulario

EXEMPLO_4_2 = "cont base base tb1 base base base base breque base pd2 base virada base base tb2 virada final"
SAMPLES = Path("samples")


def test_grade_em_texto_mostra_cada_pista_por_ciclo():
    grade = Grade.de_derivacao([Terminal.CONT, Terminal.FINAL], Vocabulario())

    texto = grade.como_texto([Terminal.CONT, Terminal.FINAL])

    assert "ciclo 0: cont" in texto
    assert "tb    x . . . x . . . | x . . . x . . ." in texto
    assert "sd1   X . . . . . . . | . . . . . . . ." in texto
    assert "cu_g" not in texto


def test_gerar_com_derivacao_fixa_e_render_gm(tmp_path: Path):
    gerar.main(["--derivacao", EXEMPLO_4_2, "--render", "gm", "--out", str(tmp_path), "--nome", "exemplo"])

    registro = json.loads((tmp_path / "exemplo.json").read_text())
    assert registro["derivacao"] == EXEMPLO_4_2.split()
    assert registro["hiperparametros"] is None
    midi = pretty_midi.PrettyMIDI(str(tmp_path / "exemplo.mid"))
    assert midi.get_end_time() == pytest.approx((17 * 16 + 0.9) * 60 / (4 * 90), abs=0.05)
    assert sf.info(tmp_path / "exemplo.wav").duration > 40
    assert (tmp_path / "exemplo.mp3").exists()


def test_render_brid_sem_samples_cai_no_gm(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    gerar.main(
        ["--derivacao", "cont base final", "--render", "brid", "--samples", str(tmp_path / "vazio"), "--out", str(tmp_path), "--nome", "x"]
    )

    assert "FluidSynth GM" in capsys.readouterr().out
    assert (tmp_path / "x.wav").exists()


@pytest.mark.skipif(not SAMPLES.exists(), reason="biblioteca samples/ ausente")
def test_gerar_com_samples_do_brid(tmp_path: Path):
    gerar.main(["--derivacao", EXEMPLO_4_2, "--render", "brid", "--out", str(tmp_path), "--nome", "exemplo"])

    assert sf.info(tmp_path / "exemplo.wav").duration > 40


def test_derivacao_com_terminal_desconhecido_e_recusada(tmp_path: Path):
    with pytest.raises(SystemExit):
        gerar.main(["--derivacao", "cont samba final", "--out", str(tmp_path)])


def test_cli_le_os_hiperparametros_da_cuica():
    args = gerar.criar_parser().parse_args(["--cuica-presenca", "0.4", "--cuica-variedade", "0.9"])

    assert args.cuica_presenca == 0.4
    assert args.cuica_variedade == 0.9


def test_cli_nao_tem_mais_instrumentos(tmp_path: Path):
    with pytest.raises(SystemExit):
        gerar.main(["--instrumentos", "surdo,pandeiro,tamborim", "--derivacao", "cont final", "--out", str(tmp_path)])


def test_cli_recusa_epsilon_mais_cuica_acima_de_1(tmp_path: Path):
    with pytest.raises(SystemExit):
        gerar.main(["--epsilon", "0.9", "--cuica-presenca", "0.3", "--derivacao", "cont final", "--out", str(tmp_path)])


def test_cuica_toca_sem_flag_de_instrumento(tmp_path: Path):
    gerar.main(["--derivacao", "cont cu3 final", "--render", "gm", "--out", str(tmp_path), "--nome", "c"])

    midi = pretty_midi.PrettyMIDI(str(tmp_path / "c.mid"))
    assert "cuica" in {i.name for i in midi.instruments}


def test_nome_padrao_preserva_o_ponto_do_epsilon(tmp_path: Path):
    for epsilon in ("0.15", "0.45"):
        gerar.main(["--seed", "3", "--epsilon", epsilon, "--p", "0", "--render", "gm", "--out", str(tmp_path)])

    nomes = {p.name for p in tmp_path.iterdir()}
    for epsilon in ("0.15", "0.45"):
        for extensao in ("mid", "json", "wav", "mp3"):
            assert f"samba_s3_e{epsilon}.{extensao}" in nomes


def test_audio_salva_com_ponto_no_nome(tmp_path: Path):
    from src.audio import ArquivoDeAudio

    wav, mp3 = ArquivoDeAudio(44100).salvar(np.zeros(4410), tmp_path / "samba_s1_e0.15")

    assert wav.name == "samba_s1_e0.15.wav"
    assert mp3.name == "samba_s1_e0.15.mp3"


def test_cli_nao_tem_mais_balanco(tmp_path: Path):
    with pytest.raises(SystemExit):
        gerar.main(["--balanco", "0.5", "--derivacao", "cont final", "--out", str(tmp_path)])
