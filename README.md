# Samba por gramática probabilística

Trabalho Prático 1 de DCC831 IA Generativa para Música (UFMG, 2026/2). O sistema gera **backing tracks de percussão de samba** para quem quer praticar improvisação no cavaquinho. Ele usa exclusivamente **gramáticas generativas probabilísticas**. Cada execução produz um `.mid` reproduzível, um `.json` com a derivação e o áudio renderizado com recortes do dataset BRID.

As músicas precisam:
- manter uma levada estável, a âncora para quem toca;
- variar de forma contida, com comentários pontuais de tamborim, pandeiro e cuíca;
- sinalizar a forma com virada ou breque a cada 16 compassos (e, opcionalmente, a cada 8), para quem improvisa se orientar.

**Restrição estilística:** samba em 2/4, ciclo rítmico de 2 compassos ancorado no telecoteco do tamborim, frases de 8 compassos agrupadas em blocos de 16.

## Instalação

Testado com Python 3.14 no Ubuntu.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo apt install ffmpeg fluidsynth fluid-soundfont-gm
```

O `ffmpeg` gera o mp3, e o `fluidsynth` com um soundfont GM faz o render de reserva. Sem o soundfont do sistema, o render GM usa o que vem com o `pretty_midi`.

## Gerar uma música

```bash
.venv/bin/python gerar.py --seed 3 --epsilon 0.15 --p 0.8
# → output/samba_s3_e0.15.{mid,json,wav,mp3}
```

| Flag | Padrão | O que controla |
|---|---|---|
| `--seed` | 1 | músicas diferentes com a mesma configuração |
| `--bpm` | 90 | andamento (não faz parte do método; use 70–80 para treinar) |
| `--epsilon` | 0.15 | ε: quanto tamborim e pandeiro variam |
| `--p` | 0.8 | continuação: tamanho da música |
| `--va` | 0.3 | v_a: virada também no meio do bloco (a cada 8 compassos) |
| `--b` | 0.3 | breque contra virada no fim do bloco |
| `--max-blocos` | 10 | limite de segurança do tamanho |
| `--cuica-presenca` | 0.25 | c: quanto a cuíca aparece (ε + c ≤ 1) |
| `--cuica-variedade` | 0.5 | v: de 0 (repete sempre `cu1`) a 1 (quatro frases equiprováveis) |
| `--render` | `brid` | `brid` (sampler com recortes do BRID) ou `gm` (FluidSynth) |
| `--out` / `--nome` | `output/` | pasta e nome dos arquivos |
| `--derivacao` | — | sequência fixa de terminais, sem passar pela gramática (ex.: `"cont base cu1 virada final"`) |
| `--mostrar-grade` | — | imprime a grade pista × semicolcheia de cada ciclo |

Se `samples/` não existir, `--render brid` cai no FluidSynth GM, então o repositório é reproduzível mesmo sem os recortes.

## Músicas entregues

As três usam a seed 3 e mudam só os hiperparâmetros. Cada uma tem `.mid`, `.json`, `.wav` e `.mp3` em `output/`, e os comandos abaixo reproduzem os `.mid` byte a byte.

| Música | Comando | O que demonstra |
|---|---|---|
| [`musica_1`](output/musica_1.mp3) | `gerar.py --seed 3 --epsilon 0 --cuica-presenca 0 --nome musica_1` | controle: com ε = c = 0 só sobram `base`, `virada` e `breque`, então a levada vira loop e só a forma varia (breque no fim do 1º bloco, virada no fim do 2º). 18 ciclos, 46 s |
| [`musica_2`](output/musica_2.mp3) | `gerar.py --seed 3 --epsilon 0.7 --cuica-presenca 0.3 --cuica-variedade 0.3 --nome musica_2` | levada muito variada: tamborim e pandeiro variam em 54% dos ciclos, e a cuíca, com pouca variedade, repete só `cu1`. 26 ciclos, 1min07 |
| [`musica_3`](output/musica_3.mp3) | `gerar.py --seed 3 --epsilon 0.1 --cuica-presenca 0.9 --cuica-variedade 0.7 --bpm 100 --nome musica_3` | extremo da cuíca: com ε + c = 1, nenhum ciclo é `base`, e a cuíca ocupa 71% dos ciclos. Mostra também uma música longa: 10 blocos (o máximo), 82 ciclos, 3min15 a 100 BPM |

## Representação

- **Grade:** compasso 2/4, subdivisão em semicolcheias (4 passos por tempo, 8 por compasso). A cabeça do tempo cai nos passos 0, 4, 8 e 12.
- **Ciclo = 2 compassos = 16 passos.** É a unidade de cada terminal da gramática. Um ciclo de um compasso só quebraria a clave do tamborim, que é assimétrica entre os dois compassos.
- **Padrão:** para cada pista e cada ciclo, um array de 16 inteiros: `0` silêncio, `1` batida, `2` batida acentuada.

| Nível | Passos | A 90 BPM | Quem decide |
|---|---|---|---|
| semicolcheia (Δ = 60 / (4·BPM)) | 1 | 167 ms | — |
| ciclo (terminal) | 16 | 2,7 s | vocabulário |
| frase = 4 ciclos = 8 compassos | 64 | 10,7 s | gramática |
| bloco = 2 frases = 16 compassos | 128 | 21,3 s | gramática |
| música = n blocos | — | n × 21,3 s | gramática (p) |

| Pista | Instrumento e articulação | Nota GM | Ganho de mixagem |
|---|---|---|---|
| `sd1` | surdo de primeira, aberto | 41 | 1,0 |
| `sd2` | surdo de segunda, aberto | 43 | 0,8 |
| `pd_g` / `pd_p` / `pd_t` | pandeiro: grave, platinela, tapa | 64 / 54 / 62 | 0,6 |
| `tb` | tamborim | 65 | 0,7 |
| `cu_g` / `cu_a` | cuíca: grave, aguda | 78 / 79 | 0,5 |

## A gramática

**Axioma:** `MÚSICA`.
**Não-terminais:** `MÚSICA, BLOCOS, BLOCO, FRASE_A, FRASE_B, FIM_A, FIM_B, G, VAR_TB, VAR_PD, VAR_CU`.
**Terminais:** `cont, final, base, tb1, tb2, tb3, pd1, pd2, cu1, cu2, cu3, cu4, virada, breque`. Cada terminal é um ciclo de 16 passos com todos os instrumentos.

```
MÚSICA  → cont BLOCOS final                                   [1]
BLOCOS  → BLOCO BLOCOS [p]  |  BLOCO [1 − p]
BLOCO   → FRASE_A FRASE_B                                     [1]
FRASE_A → G G G FIM_A                                         [1]
FRASE_B → G G G FIM_B                                         [1]
FIM_A   → G [1 − v_a]  |  virada [v_a]
FIM_B   → virada [1 − b]  |  breque [b]
G       → base [1 − ε − c]  |  VAR_TB [ε/2]  |  VAR_PD [ε/2]  |  VAR_CU [c]
VAR_TB  → tb1 [0.40]  |  tb2 [0.35]  |  tb3 [0.25]
VAR_PD  → pd1 [0.5]   |  pd2 [0.5]
VAR_CU  → cu1 [1 − 3v/4]  |  cu2 [v/4]  |  cu3 [v/4]  |  cu4 [v/4]
```

Ao atingir `max_blocos`, `BLOCOS` é forçado a `BLOCO`, o que trunca a distribuição do tamanho. A implementação (`src/gramatica.py`) tem um método por não-terminal e usa `random.Random(seed)`.

### Exemplo de expansão

`gerar.py --seed 7`, com todos os parâmetros no padrão (ε = 0,15, c = 0,25, v = 0,5, v_a = 0,3, b = 0,3, p = 0,8), deriva esta árvore:

```
MÚSICA
├── cont
├── BLOCOS                                  BLOCOS → BLOCO BLOCOS  [p]
│   ├── BLOCO
│   │   ├── FRASE_A
│   │   │   ├── G → base
│   │   │   ├── G → VAR_PD → pd1
│   │   │   ├── G → VAR_PD → pd1
│   │   │   └── FIM_A → virada                 virada no meio do bloco  [v_a]
│   │   └── FRASE_B
│   │       ├── G → VAR_TB → tb2
│   │       ├── G → base
│   │       ├── G → VAR_TB → tb2
│   │       └── FIM_B → virada                 fim do bloco  [1 − b]
│   └── BLOCOS                              BLOCOS → BLOCO  [1 − p]
│       └── BLOCO
│           ├── FRASE_A
│           │   ├── G → VAR_PD → pd1
│           │   ├── G → VAR_TB → tb1
│           │   ├── G → base
│           │   └── FIM_A → G → VAR_CU → cu1   sem virada no meio  [1 − v_a]
│           └── FRASE_B
│               ├── G → base
│               ├── G → base
│               ├── G → VAR_CU → cu1
│               └── FIM_B → breque             fim do bloco  [b]
└── final
```

A sequência de terminais tem 18 ciclos, cerca de 45 s a 90 BPM:

```
cont | base pd1 pd1 virada   tb2 base tb2 virada | pd1 tb1 base cu1   base base cu1 breque | final
       └── FRASE_A ───────┘  └── FRASE_B ──────┘   └── FRASE_A ─────┘  └── FRASE_B ───────┘
       └────────────── BLOCO 1 ────────────────┘   └────────────── BLOCO 2 ───────────────┘
```

O vocabulário transforma cada terminal num ciclo de todos os instrumentos. Três deles, vistos com `--mostrar-grade` (`x` batida, `X` acento, `|` separa os compassos):

```
ciclo: base                          ciclo: virada                        ciclo: cu1
sd1   . . . . X . . . | . . . . X . . .   . . . . X . . . | X . . X . . X .   . . . . X . . . | . . . . X . . .
sd2   x . . . . . . . | x . . . . . . .   x . . . . . . . | X . . X . . X .   x . . . . . . . | x . . . . . . .
pd_g  x . . . x . . . | x . . . x . . .   x . . . x . . . | . . . . . . . .   x . . . x . . . | x . . . x . . .
pd_p  x x x X x x x X | x x x X x x x X   x x x X x x x X | . . . . . . . .   x x x X x x x X | x x x X x x x X
pd_t  . . . . . . . x | . . . . . . . x   . . . . . . . x | X . . X . . X .   . . . . . . . x | . . . . . . . x
tb    x . x . x x . x | . x . x x . x .   x . x . x x . x | X . . X . . X .   x . x . x x . x | . x . x x . x .
cu_g  . . . . . . . . | . . . . . . . .   . . . . . . . . | . . . . . . . .   . . . . x x x . | . . . . x . . .
cu_a  . . . . . . . . | . . . . . . . .   . . . . . . . . | X . . X . . X .   . . . x . . . . | . . . X . . x .
```

### Decisões de desenho

1. **Surdo fixo** na música inteira.
2. **Um instrumento varia por ciclo, no máximo.** Cada `G` escolhe uma coisa só; se os três variassem juntos, a base sumiria.
3. **Viradas e breques só no fim de frase,** para não desorientar quem improvisa.
4. **Viradas e breques em uníssono:** todos tocam o mesmo ritmo.
5. **Todos os instrumentos sempre presentes.** A cuíca não tem base: toca só nas suas frases (`cu1..cu4`) e na figura das marcas de forma, com presença e variedade controladas por c e v.
6. **Áudio por sampler próprio** com recortes do BRID, com fallback em FluidSynth GM.
7. **Terminal = ciclo de 16 semicolcheias** (2 compassos), por causa da clave do tamborim.

### Propriedades

- **Tamanho:** o número de blocos segue uma geométrica de média 1/(1 − p), truncada em `max_blocos`. Com p = 0,8 e `max_blocos` = 10, a média é 4,46 blocos (cerca de 1min40 a 90 BPM). Toda música tem 2 + 8n ciclos.
- **Variação esperada:** cada bloco tem 6 `G` fixos mais o `G` de `FIM_A` (com probabilidade 1 − v_a). A fração de ciclos com variação de tamborim ou pandeiro é ε·(7 − v_a)/8, e a de frases de cuíca é c·(7 − v_a)/8. A cuíca não altera a taxa de variação da levada.
- **Variedade da cuíca:** a entropia de `VAR_CU` vai de 0 bit (v = 0) a 2 bits (v = 1).
- **A linguagem gerada é regular.** `BLOCOS` só tem recursão à direita e o resto é finito, então uma cadeia de Markov com estados para a posição na frase geraria as mesmas músicas. A gramática se justifica pela legibilidade e pela hierarquia explícita: `FIM_A` e `FIM_B` são esses estados, só que com nome e significado musical.
- **Falta de memória:** uma gramática livre de contexto não lembra escolhas anteriores. Escolher um surdo por música e mantê-lo exigiria duplicar a gramática ou usar uma gramática de atributos (daí a decisão 1). Pelo mesmo motivo, a gramática não consegue proibir que a mesma frase de cuíca se repita em ciclos seguidos.

## Vocabulário

`src/vocabulario.py` guarda os padrões e a tabela terminal → arranjo. Os padrões base:

```
SD1      . . . . X . . . | . . . . X . . .    surdo de primeira: golpe forte no 2º tempo
SD2      x . . . . . . . | x . . . . . . .    surdo de segunda: responde no 1º tempo
TB_BASE  x . x . x x . x | . x . x x . x .    telecoteco (a clave)
PD_P     x x x X x x x X | x x x X x x x X    platinela contínua, acento na 4ª semicolcheia
PD_G     x . . . x . . . | x . . . x . . .    grave na cabeça do tempo
PD_T     . . . . . . . x | . . . . . . . x    tapa no fim do compasso
```

Variantes da levada. Preservam a identidade da base: o tamborim mantém o 1º compasso (a pergunta), nunca inverte a direção da clave, e cada variante muda 2 a 3 casas.

```
tb1  x . x . x x . x | . x x . x . x x    resposta rearranjada
tb2  x . x . x x . x | . x . x x x x x    semicolcheias no fim "chamam" o próximo ciclo
tb3  x . x x . x . x | . x . x x . x .    antecipação no 1º compasso (a mais rara)
pd1  tapas deslocados:          . . . x . . . . | . . . x . . . x
pd2  grave com antecipação:     x . . x x . . . | x . . x x . . .
```

Frases da cuíca (a = aguda, G = grave), escritas de ouvido a partir de três ideias: antecipação para o golpe do surdo de primeira, pergunta e resposta entre os compassos, e encaixe nos espaços do tamborim.

```
cu1  . . . a G G G . | . . . a G . a .    acento na aguda do passo 11
cu2  . a . G . a . G | . a G G G . . .    acento na grave do passo 10
cu3  a . G . a a . G | . G . . a a a .
cu4  . a G . G . G . | . a G G G G G .
```

| Terminal | Surdos | Pandeiro | Tamborim | Cuíca |
|---|---|---|---|---|
| `cont` | — | — | contagem `x . . . x . . . \| x . . . x . . .` | — |
| `base` | SD1, SD2 | base | TB_BASE | — |
| `tb1..3` | SD1, SD2 | base | variante | — |
| `pd1..2` | SD1, SD2 | variante | TB_BASE | — |
| `cu1..4` | SD1, SD2 | base | TB_BASE | frase |
| `virada` | 1º compasso da base + `UNI` | 1º compasso da base; depois só o tapa em `UNI` | 1º compasso da base + `UNI` | aguda em `UNI` |
| `breque` | 1º compasso da base + `BRQ` | 1º compasso da base; depois só o tapa em `BRQ` | 1º compasso da base + `BRQ` | aguda em `BRQ` |
| `final` | acento único | tapa: acento único | acento único | aguda: acento único |

`UNI` = `X . . X . . X .` (figura 3-3-2 no 2º compasso, todos juntos). `BRQ` = `X . . . . . . .` (um golpe no 1º tempo, depois silêncio). O ciclo seguinte à virada ou ao breque recomeça no passo 0, e é ali que o improvisador reentra.

## Do terminal ao áudio

**MIDI** (`src/midi_out.py`):
- O passo i do ciclo c soa em t = (16·c + i)·Δ + N(0, σ_t), com σ_t = 4 ms de humanização.
- Velocidade: `1` → 78 e `2` → 108, mais ruído N(0, 6), limitada a [1, 127].
- Um `Instrument(is_drum=True)` por grupo (surdo, pandeiro, tamborim, cuíca), com fórmula de compasso 2/4 e o andamento no arquivo. A duração de cada nota é 0,9·Δ.
- Ao lado do `.mid`, um `.json` guarda a seed, os hiperparâmetros, o render e a derivação.

**Seeds independentes:** a gramática usa `Random(seed)`, a humanização `Random(seed + 1)` e o round-robin do sampler `Random(seed + 2)`. Mudar o render não muda a música derivada, e a mesma configuração gera o mesmo `.mid` byte a byte.

**Sampler** (`src/sampler.py`), para cada nota do MIDI:
1. A nota GM indica a pista e a pasta em `samples/`.
2. Velocidade ≥ 95 usa a camada `v2`; abaixo disso, a `v1`.
3. Escolhe a amostra por round-robin aleatório, sem repetir a mesma duas vezes seguidas.
4. Aplica o ganho (vel/127)^1,7 × o ganho de mixagem da pista e soma no buffer.

Ao final, normaliza o pico em −1 dBFS e grava `.wav` e `.mp3`.

## Samples do BRID

Os recortes curados já estão em `samples/`, então gerar músicas não exige o dataset. Eles vêm do **Brazilian Rhythmic Instruments Dataset (BRID)**: 274 faixas solo e 93 mixagens, gravadas em estúdio a 44,1 kHz. Usamos as faixas solo do instrumentista 2 (mesma mão, mesma sala, timbre coerente), de samba a 80 BPM. A exceção é o surdo de segunda, que vem de uma faixa de samba-enredo a 130 BPM, o que não importa para one-shots.

| Pista | Faixa | Reservas recortadas |
|---|---|---|
| surdo de primeira | `[0270] S2-SU2-01-SA` | 0180, 0358 |
| surdo de segunda | `[0279] S2-SU3-06-SE` | 0184, 0365 |
| pandeiro | `[0185] S2-PD2-01-SA` | 0101, 0281 |
| tamborim | `[0214] S2-TB2-01-SA` | 0129, 0302 |
| cuíca | `[0245] S2-CU3-01-SA` | 0162 |

Para refazer a biblioteca:

```bash
# extraia as faixas solo do BRID (Zenodo) em brid/Solo Tracks/
.venv/bin/python -m tools.slice_brid    # → samples_raw/ + manifest.csv
.venv/bin/python -m tools.label_brid    # → samples/ (--instrumentos cuica refaz só a cuíca)
```

**Grade de beats.** As anotações de beat do BRID cobrem só as mixagens. Para as faixas solo, a grade é ajustada aos próprios onsets:
1. O período é buscado em ±4% do BPM nominal do estilo (samba a 80, samba-enredo a 130), pela coerência circular dos onsets na grade de semicolcheias.
2. A fase vem da média circular ponderada pela força dos onsets.
3. Qual semicolcheia é a cabeça do tempo é decidido por voto dos beats do `librosa.beat.beat_track`.

O andamento ajustado fica a ±0,1 BPM do nominal em todas as faixas. O grave do pandeiro cai 100% na cabeça do tempo, o que confirma a fase.

**Recorte** (`tools/slice_brid.py`):
- Recorta do onset k até o k+1, com teto por instrumento: surdo 0,8 s, cuíca 0,4 s, tamborim 0,25 s, pandeiro 0,2 s.
- Remove o silêncio inicial (−30 dB do pico).
- Fade-out linear de 10 ms. Na cuíca, fade-in de 5 ms e fade-out em cosseno de 35 ms.
- Descarta o primeiro e o último onset de cada faixa e os recortes com duração ou RMS fora de [P10, P90].

O manifest guarda as features de cada recorte: RMS, centroide espectral, razão de energia abaixo de 200 Hz, decaimento até −20 dB, posição na grade e, para a cuíca, o f0 (pYIN).

**Rotulagem e curadoria** (`tools/label_brid.py`):
- **Surdo:** "aberto" é o recorte com decaimento ≥ P60.
- **Pandeiro:** k-means com k = 3 (melhor de 10 inicializações) sobre [razão de graves, log do centroide, decaimento]. Os grupos são nomeados pela razão de graves: grave > tapa > platinela.
- **Cuíca:** k-means com k = 2 no log do f0. Os dois picos ficam em cerca de 300 Hz (grave) e 750 Hz (aguda). Só entram recortes que já tinham decaído a −20 dB antes do corte.
- **Camadas:** `v2` = RMS ≥ P70; `v1` = RMS entre P40 e P70, o que deixa de fora as notas fantasma do tamborim.
- **Seleção:** ficam os 6 recortes mais típicos por articulação e camada (os mais próximos da mediana das features), com um ganho único por instrumento.
- A origem de cada arquivo está em `samples/curadoria.csv`.

## Testes

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/pyright
```

Os testes de aceite da gramática (`tests/test_gramatica.py`) verificam:
- determinismo por seed, e seeds diferentes gerando músicas diferentes;
- 2 + 8n ciclos, com 1 ≤ n ≤ `max_blocos`;
- virada só nas posições 3 e 7 de cada bloco, e breque só na 7;
- ε = 0 com c = 0 gerando só `base`, `virada`, `breque`, `cont` e `final`;
- as taxas teóricas ε·(7 − v_a)/8 e c·(7 − v_a)/8, com a cuíca sem alterar a da levada;
- as proporções de `VAR_TB` e `VAR_CU`.

Os demais testes cobrem o vocabulário, o MIDI (incluindo o `.mid` idêntico byte a byte), o sampler, o render GM, a CLI e as ferramentas do BRID.

## Limitações e trabalhos futuros

- A variação é combinatória (escolha entre padrões escritos à mão), não improvisação.
- Pela falta de memória da gramática livre de contexto, o surdo é fixo e a cuíca pode repetir a mesma frase em ciclos seguidos.
- As amostras da cuíca têm altura fixa, então falta o deslizar contínuo entre aguda e grave do instrumento real. Um caminho é recortar pares aguda→grave inteiros da gravação e usá-los como amostras de transição.
- As notas caem na grade, com só ruído de humanização. O microtiming característico do samba poderia ser medido nos onsets do BRID e aplicado por posição no tempo.
- Outros trabalhos futuros: gramática de atributos (surdo por música), variação condicionada à harmonia do cavaquinho, mais instrumentos (caixa, repique).

## Créditos

Samples recortados do BRID, sob licença CC BY 4.0 (detalhes em `samples/LICENSE-BRID.txt`):

> L. S. Maia, P. D. Tomaz Jr., M. Fuentes, M. Rocamora, L. W. P. Biscainho, M. V. M. Costa e S. Cohen, "A Novel Dataset of Brazilian Rhythmic Instruments and Some Experiments in Computational Rhythm Analysis", *2018 AES Latin American Congress of Audio Engineering*, pp. 53–60. DOI: [10.5281/zenodo.14051323](https://doi.org/10.5281/zenodo.14051323).

## Uso de IA

**Ferramenta:** Claude (Anthropic), via Claude Code.

**Usado para:**
- discussão da ideia e do escopo, escolha entre gramática e cadeia de Markov, pesquisa do dataset BRID;
- um documento de planejamento inicial, incluindo os padrões rítmicos iniciais de surdo, tamborim e pandeiro, que o autor validou e ajustou de ouvido;
- código auxiliar: estrutura do projeto, vocabulário e tabela terminal → arranjo, arranjo, geração de MIDI, sampler, render GM, CLI, ferramentas de recorte e rotulagem do BRID (`tools/`) e os testes, incluindo os testes de aceite da gramática;
- explicações de teoria musical e exemplos de frases que serviram de ponto de partida para as frases de cuíca, reescritas pelo autor;
- rascunho deste README.

**Não usado para:** a gramática e o expansor (`src/gramatica.py`), escritos pelo autor, nem para escrever o resumo na íntegra.

**Links das conversas:**
- Ideação e escopo: <https://claude.ai/share/ee6b247f-e646-4227-b1e3-20792f9c0ef4>
- Implementação (Claude Code): [`docs/conversa-implementacao.jsonl`](docs/conversa-implementacao.jsonl). É o transcript desta sessão, exportado do Claude Code. Foram removidos só dados pessoais e de trabalho do autor (e-mail, a listagem de uma pasta pessoal e o contexto de ambiente que o Claude Code injeta); mensagens, chamadas de ferramenta e resultados estão intactos.
