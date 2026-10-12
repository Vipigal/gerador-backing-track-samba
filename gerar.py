import argparse
import json
from pathlib import Path

from src import gramatica
from src.arranjo import Grade
from src.audio import ArquivoDeAudio
from src.hiperparametros import Hiperparametros
from src.midi_out import ArquivoMidi, ParametrosDeRender, RegistroDaMusica, Sequenciador
from src.render_gm import RenderizadorGM
from src.sampler import SR, BibliotecaDeSamples, Sampler
from src.terminais import Terminal
from src.vocabulario import Vocabulario

MICROTIMING = Path("config/microtiming.json")


class Render:
    BRID = "brid"
    GM = "gm"


def ler_derivacao(texto: str) -> list[Terminal]:
    validos = {t.value: t for t in Terminal}
    desconhecidos = [nome for nome in texto.split() if nome not in validos]
    if desconhecidos:
        raise argparse.ArgumentTypeError(f"terminais desconhecidos: {desconhecidos}; válidos: {sorted(validos)}")
    return [validos[nome] for nome in texto.split()]


def ler_microtiming() -> tuple[float, float, float, float]:
    if not MICROTIMING.exists():
        return (0.0, 0.0, 0.0, 0.0)
    mu = json.loads(MICROTIMING.read_text())["mu"]
    return (float(mu[0]), float(mu[1]), float(mu[2]), float(mu[3]))


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera uma backing track de samba por gramática probabilística.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--bpm", type=float, default=90.0)
    parser.add_argument("--epsilon", type=float, default=0.15)
    parser.add_argument("--p", type=float, default=0.8)
    parser.add_argument("--va", type=float, default=0.3)
    parser.add_argument("--b", type=float, default=0.3)
    parser.add_argument("--max-blocos", type=int, default=10)
    parser.add_argument("--cuica-presenca", type=float, default=0.25)
    parser.add_argument("--cuica-variedade", type=float, default=0.5)
    parser.add_argument("--balanco", type=float, default=0.0)
    parser.add_argument("--render", choices=[Render.BRID, Render.GM], default=Render.BRID)
    parser.add_argument("--samples", type=Path, default=Path("samples"))
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--nome")
    parser.add_argument("--derivacao", type=ler_derivacao, help="sequência fixa de terminais; ignora a gramática")
    parser.add_argument("--mostrar-grade", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        hiper = Hiperparametros(
            epsilon=args.epsilon,
            p=args.p,
            va=args.va,
            b=args.b,
            max_blocos=args.max_blocos,
            cuica_presenca=args.cuica_presenca,
            cuica_variedade=args.cuica_variedade,
        )
    except ValueError as erro:
        parser.error(str(erro))
    render = ParametrosDeRender(bpm=args.bpm, balanco=args.balanco, microtiming=ler_microtiming())
    fixa: list[Terminal] | None = args.derivacao
    derivacao = fixa if fixa is not None else gramatica.derivar(hiper, args.seed)
    nome = args.nome or (f"derivacao_s{args.seed}" if fixa is not None else f"samba_s{args.seed}_e{args.epsilon}")
    base = args.out / nome
    caminho_midi = args.out / f"{nome}.mid"
    caminho_json = args.out / f"{nome}.json"

    grade = Grade.de_derivacao(derivacao, Vocabulario())
    if args.mostrar_grade:
        print(grade.como_texto(derivacao), end="\n\n")

    arquivo_midi = ArquivoMidi(render)
    midi = arquivo_midi.montar(Sequenciador(render, args.seed).eventos(grade))
    arquivo_midi.salvar(midi, caminho_midi)
    RegistroDaMusica(
        seed=args.seed, hiperparametros=None if fixa is not None else hiper, render=render, derivacao=derivacao
    ).salvar(caminho_json)

    if args.render == Render.BRID and BibliotecaDeSamples.existe(args.samples):
        audio = Sampler(BibliotecaDeSamples(args.samples), args.seed).renderizar(midi)
        motor = f"sampler BRID ({args.samples})"
    else:
        if args.render == Render.BRID:
            print(f"{args.samples} sem amostras: usando o fallback FluidSynth GM")
        gm = RenderizadorGM()
        audio = gm.renderizar(midi)
        motor = f"FluidSynth GM ({gm.soundfont or 'soundfont do pretty_midi'})"
    wav, mp3 = ArquivoDeAudio(SR).salvar(audio, base)

    print(f"{len(derivacao)} ciclos, {midi.get_end_time():.1f} s a {args.bpm:g} BPM, render: {motor}")
    print(" ".join(t.value for t in derivacao))
    for caminho in (caminho_midi, caminho_json, wav, mp3):
        print(f"  {caminho}")


if __name__ == "__main__":
    main()
