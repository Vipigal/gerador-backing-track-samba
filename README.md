# Samba por gramática probabilística

Trabalho Prático 1 de DCC831 IA Generativa para Música (UFMG, 2026/2). O sistema gera **backing tracks de percussão de samba** para quem quer praticar improvisação no cavaquinho. Ele usa exclusivamente **gramáticas generativas probabilísticas**. Cada execução produz um `.mid` reproduzível, o `.json` com a derivação e o áudio renderizado com recortes do dataset BRID.

**Restrição estilística:** samba em 2/4, ciclo rítmico de 2 compassos ancorado no telecoteco do tamborim, frases de 8 compassos agrupadas em blocos de 16 compassos. Cada bloco termina em virada ou breque, para quem improvisa se orientar na forma.

**Instrumentos:** surdo de primeira e de segunda, pandeiro (grave, platinela e tapa), tamborim e cuíca (aguda e grave).

O desenho completo, com a gramática formal, o vocabulário e o registro de decisões, está em [`docs/spec.md`](docs/spec.md).

## Instalação

Testado com Python 3.14 no Ubuntu.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Pacotes de sistema: `ffmpeg` gera o mp3, e `fluidsynth` com um soundfont GM faz o render de reserva.

```bash
sudo apt install ffmpeg fluidsynth fluid-soundfont-gm
```

Sem o soundfont do sistema, o render GM usa o soundfont que vem com o `pretty_midi`.

## Gerar uma música

```bash
.venv/bin/python gerar.py --seed 3 --epsilon 0.15 --p 0.8
# → output/samba_s3_e0.15.{mid,json,wav,mp3}
```

| Flag | Padrão | O que controla |
|---|---|---|
| `--seed` | 1 | músicas diferentes com a mesma configuração |
| `--bpm` | 90 | andamento (não faz parte do método) |
| `--epsilon` | 0.15 | ε: quanto tamborim e pandeiro variam |
| `--p` | 0.8 | continuação: tamanho médio da música (geométrica truncada) |
| `--va` | 0.3 | virada no meio do bloco |
| `--b` | 0.3 | breque contra virada no fim do bloco |
| `--max-blocos` | 10 | limite de segurança do tamanho |
| `--cuica-presenca` | 0.25 | c: quanto a cuíca aparece (ε + c ≤ 1) |
| `--cuica-variedade` | 0.5 | v: de 0 (repete sempre `cu1`) a 1 (quatro frases equiprováveis) |
| `--render` | `brid` | `brid` (sampler com recortes do BRID) ou `gm` (FluidSynth) |
| `--out` / `--nome` | `output/` | pasta e nome dos arquivos |
| `--derivacao` | — | sequência fixa de terminais, sem passar pela gramática (ex.: `"cont base cu1 virada final"`) |
| `--mostrar-grade` | — | imprime a grade pista × semicolcheia de cada ciclo |

A mesma seed com os mesmos parâmetros gera um `.mid` idêntico byte a byte. A gramática, a humanização e o round-robin do sampler usam seeds independentes (`seed`, `seed + 1`, `seed + 2`), então mudar o render não muda a música derivada.

## A gramática

```
MÚSICA  → cont BLOCOS final
BLOCOS  → BLOCO BLOCOS [p]  |  BLOCO [1 − p]
BLOCO   → FRASE_A FRASE_B
FRASE_A → G G G FIM_A          FIM_A → G [1 − v_a]  |  virada [v_a]
FRASE_B → G G G FIM_B          FIM_B → virada [1 − b]  |  breque [b]
G       → base [1 − ε − c]  |  VAR_TB [ε/2]  |  VAR_PD [ε/2]  |  VAR_CU [c]
VAR_TB  → tb1 [0.40] | tb2 [0.35] | tb3 [0.25]
VAR_PD  → pd1 [0.5]  | pd2 [0.5]
VAR_CU  → cu1 [1 − 3v/4] | cu2 [v/4] | cu3 [v/4] | cu4 [v/4]
```

Cada terminal é um ciclo de 16 semicolcheias com todos os instrumentos (`src/vocabulario.py`). A cuíca não tem base: ela só toca nas suas frases e na figura das viradas, dos breques e do final.

## Músicas entregues

<!-- TODO: preencher com os arquivos finais de output/ e o comando de cada um -->

| Arquivo | Comando | O que demonstra |
|---|---|---|
| `output/…` | `gerar.py --seed … …` | … |

## Samples do BRID

Os recortes curados já estão em `samples/`, então gerar músicas não exige o dataset. Para refazê-los:

1. Baixe o BRID do [Zenodo](https://doi.org/10.5281/zenodo.14051323) e extraia as faixas solo em `brid/Solo Tracks/`.
2. Recorte os onsets e escreva o manifest: `.venv/bin/python -m tools.slice_brid` (gera `samples_raw/`).
3. Rotule as articulações e monte a biblioteca: `.venv/bin/python -m tools.label_brid` (gera `samples/`). Com `--instrumentos cuica`, refaz só os instrumentos indicados.

O recorte ajusta uma grade de semicolcheias aos onsets de cada faixa, porque as faixas solo do BRID não têm anotação de beat. A rotulagem usa k-means sobre features espectrais para o pandeiro e o f0 (pYIN) para a cuíca. A origem de cada arquivo está em `samples/curadoria.csv`.

## Testes

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/pyright
```

Os testes de aceite da gramática (`tests/test_gramatica.py`) verificam:
- determinismo por seed;
- número de ciclos igual a 2 + 8n, com n ≤ `max_blocos`;
- virada e breque só nos fins de frase;
- as taxas de variação teóricas ε·(7 − v_a)/8 e c·(7 − v_a)/8;
- as proporções de `VAR_TB` e `VAR_CU`.

## Créditos

Os samples são recortes do **Brazilian Rhythmic Instruments Dataset (BRID)**, sob licença CC BY 4.0 (detalhes em `samples/LICENSE-BRID.txt`):

> L. S. Maia, P. D. Tomaz Jr., M. Fuentes, M. Rocamora, L. W. P. Biscainho, M. V. M. Costa e S. Cohen, "A Novel Dataset of Brazilian Rhythmic Instruments and Some Experiments in Computational Rhythm Analysis", *2018 AES Latin American Congress of Audio Engineering*, pp. 53–60. DOI: 10.5281/zenodo.14051323.

## Uso de IA

**Ferramenta:** Claude (Anthropic), via Claude Code.

**Usado para:**
- discussão da ideia e do escopo, escolha entre gramática e cadeia de Markov, pesquisa do dataset BRID;
- o documento de especificação (`docs/spec.md`), incluindo os padrões rítmicos iniciais de surdo, tamborim e pandeiro, que o autor validou e ajustou de ouvido;
- código auxiliar: estrutura do projeto, vocabulário e tabela terminal → arranjo, arranjo, geração de MIDI, sampler, render GM, CLI, ferramentas de recorte e rotulagem do BRID (`tools/`) e os testes, incluindo os testes de aceite da gramática;
- explicações de teoria musical e exemplos de frases que serviram de ponto de partida para as frases de cuíca, reescritas pelo autor;
- rascunho deste README.

**Não usado para:** a gramática e o expansor (`src/gramatica.py`), escritos pelo autor, nem para escrever o resumo na íntegra.

**Links das conversas:**
<!-- TODO: colar os links das conversas (ideação/spec e sessões de implementação) -->
- …
