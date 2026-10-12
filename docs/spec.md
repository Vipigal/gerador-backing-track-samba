# SPEC — Gerador de backing track de samba por gramática probabilística

**Disciplina:** DCC831 IA Generativa para Música (UFMG, 2026/2), TP1
**Entrega:** 09/10/2026, 23:59 (Moodle)
**Método:** gramáticas generativas (exclusivamente)
**Status deste documento:** plano de implementação. Os padrões rítmicos marcados como *rascunho* precisam ser validados de ouvido.

---

## 0. Decisões tomadas por padrão (revise antes de começar)

Estas escolhas foram feitas para caber no prazo. Mude-as aqui se discordar, porque o resto do documento depende delas.

| # | Decisão | Alternativa descartada |
|---|---|---|
| D1 | O surdo é **fixo** na música inteira | um surdo sorteado por música: exige "lembrar" a escolha, o que uma gramática livre de contexto não faz bem |
| D2 | No máximo **um instrumento varia por ciclo** | um ε independente por instrumento: às vezes os três variam juntos e a base some |
| D3 | Viradas e breques **só no fim de frase** | virada em qualquer ciclo: desorienta quem improvisa |
| D4 | Viradas e breques **em uníssono** (todos tocam o mesmo ritmo) | uma virada por instrumento: dá 3 a 4 vezes mais vocabulário para escrever |
| D5 | **Todos os instrumentos sempre presentes.** A cuíca não tem base: ela só toca nas suas frases (`cu1..cu4`), e o quanto aparece e varia vem de dois hiperparâmetros próprios (c e v) | cuíca opcional com base repetitiva (descartada de ouvido em 12/10) |
| D6 | Áudio via **sampler próprio com recortes do BRID**, com **fallback FluidSynth GM** | Kontakt (não reprodutível); só GM (timbre fraco) |
| D7 | Terminal = **ciclo de 16 semicolcheias** (2 compassos de 2/4) | terminal de 1 compasso: quebra a clave do tamborim |

---

## 1. Objetivo

Gerar **backing tracks de percussão de samba** em MIDI, renderizadas em áudio, para um cavaquinista praticar improvisação. As músicas devem:

- manter uma levada estável (a "âncora" para quem toca);
- variar de forma contida e musical (variações pontuais de tamborim e pandeiro);
- **sinalizar a forma**, com virada ou breque a cada 16 compassos, para quem improvisa se orientar.

**Restrição estilística (vai no resumo):** samba em 2/4, ciclo rítmico de 2 compassos ancorado no telecoteco do tamborim, frases de 8 compassos agrupadas em blocos de 16 compassos.

**Referência de "feel":** playback de estudo no estilo de "Samba Playback (90 bpm): Surdo + Pandeiro + Tamborim (clave 1)", do canal Guitare Improvisation no YouTube.

---

## 2. Arquitetura

```
 hiperparâmetros + seed
          │
          ▼
 ┌──────────────────┐   sequência de terminais   ┌──────────────────┐
 │ 1. GRAMÁTICA     │ ─────────────────────────▶ │ 2. ARRANJO       │
 │ (gramatica.py)   │  cont base tb2 base virada │ (vocabulario.py) │
 └──────────────────┘          …                 └────────┬─────────┘
                                                          │ grade: pista × passo → {0,1,2}
                                                          ▼
                                                 ┌──────────────────┐
                                                 │ 3. EVENTOS/MIDI  │  .mid + .json (derivação)
                                                 │ (midi_out.py)    │
                                                 └────────┬─────────┘
                                                          ▼
                                   ┌──────────────────────┴───────────────────┐
                                   │ 4a. SAMPLER BRID   │ 4b. FLUIDSYNTH GM   │  .wav / .mp3
                                   │ (sampler.py)       │ (fallback)          │
                                   └────────────────────┴─────────────────────┘

 Offline, uma vez só:  BRID .wav ──▶ tools/slice_brid.py ──▶ samples/<instrumento>/<articulação>/*.wav
```

**Princípio de separação:** a gramática só conhece *nomes de terminais*. Ela não sabe o que é nota, MIDI ou áudio. Essa separação simplifica o código e o resumo, que descreve cada camada separadamente.

---

## 3. Representação simbólica

### 3.1 Grade

- Compasso: **2/4**, ou seja, 2 tempos (semínimas).
- Subdivisão: **semicolcheia**, então 4 passos por tempo e 8 por compasso.
- **Ciclo = 2 compassos = 16 passos.** É a unidade do terminal (D7).
- Contagem dos passos de um compasso: `1 · e · 2 · e ·`. A cabeça do tempo cai nos passos 0 e 4 (e 8 e 12 no segundo compasso).

### 3.2 Durações (Δ = duração da semicolcheia = 60 / (4·BPM))

| Nível | Contém | a 90 BPM | Quem decide |
|---|---|---|---|
| semicolcheia | 1 passo | 167 ms | — |
| tempo | 4 passos | 0,67 s | vocabulário |
| compasso 2/4 | 8 passos | 1,33 s | vocabulário |
| **ciclo (terminal)** | 16 passos | **2,67 s** | **vocabulário (array)** |
| frase | 4 ciclos = 8 compassos | 10,7 s | gramática |
| bloco | 2 frases = 16 compassos | 21,3 s | gramática |
| música | n blocos | n × 21,3 s | gramática (p) |

### 3.3 Padrões

Cada **pista** (instrumento + articulação) tem, para cada ciclo, um array de 16 inteiros:

- `0` = silêncio
- `1` = batida normal
- `2` = batida acentuada

Exemplo: `TB_BASE = [1,0,1,0,1,1,0,1,  0,1,0,1,1,0,1,0]`. O espaço duplo separa os compassos.

### 3.4 Pistas

| Pista | Instrumento | Articulação |
|---|---|---|
| `sd1` | surdo de primeira | aberto |
| `sd2` | surdo de segunda | aberto |
| `pd_g` | pandeiro | grave (polegar) |
| `pd_p` | pandeiro | platinela (dedos/base) |
| `pd_t` | pandeiro | tapa |
| `tb` | tamborim | batida |
| `cu_g` | cuíca | grave |
| `cu_a` | cuíca | aguda |

---

## 4. A gramática

### 4.1 Definição formal

**Axioma:** `MÚSICA`

**Não-terminais N:** `MÚSICA, BLOCOS, BLOCO, FRASE_A, FRASE_B, FIM_A, FIM_B, G, VAR_TB, VAR_PD, VAR_CU`

**Terminais Σ** (cada um é um **ciclo-arranjo** de 16 passos com todos os instrumentos, definido na seção 5):

`cont, final, base, tb1, tb2, tb3, pd1, pd2, cu1, cu2, cu3, cu4, virada, breque`

**Regras de produção P** (as probabilidades de cada lado esquerdo somam 1):

```
MÚSICA  → cont BLOCOS final                       [1]

BLOCOS  → BLOCO BLOCOS                            [p]
        | BLOCO                                   [1 − p]

BLOCO   → FRASE_A FRASE_B                         [1]

FRASE_A → G G G FIM_A                             [1]
FRASE_B → G G G FIM_B                             [1]

FIM_A   → G                                       [1 − v_a]
        | virada                                  [v_a]

FIM_B   → virada                                  [1 − b]
        | breque                                  [b]

G       → base                                    [1 − ε − c]
        | VAR_TB                                  [ε / 2]
        | VAR_PD                                  [ε / 2]
        | VAR_CU                                  [c]

VAR_TB  → tb1 [0.40] | tb2 [0.35] | tb3 [0.25]
VAR_PD  → pd1 [0.5] | pd2 [0.5]
VAR_CU  → cu1 [1 − 3v/4] | cu2 [v/4] | cu3 [v/4] | cu4 [v/4]
```

ε é a probabilidade de um `G` variar a levada (tamborim ou pandeiro); **c** (presença da cuíca) é a probabilidade de um `G` ser uma frase de cuíca; ε + c ≤ 1. Cada `G` escolhe uma coisa só, o que implementa a decisão D2. **v** (variedade da cuíca) vai de 0 (a cuíca repete sempre `cu1`, como um motivo) a 1 (as quatro frases equiprováveis); a entropia de `VAR_CU` vai de 0 a 2 bits.

**Limite de segurança:** existe um parâmetro `max_blocos`. Ao atingi-lo, `BLOCOS` é forçado a `BLOCO`. Documente que isso **trunca** a distribuição geométrica do tamanho.

### 4.2 Derivação de exemplo (p = 0.5, ε = 0.2, v_a = 0.3, b = 0.3)

```
cont | base base tb1 base  base base base breque | base pd2 base virada  base base tb2 virada | final
       └─ FRASE_A ─────┘   └─ FRASE_B ─────────┘   └─ FRASE_A ─────────┘   └─ FRASE_B ─────────┘
       └──────────────── BLOCO 1 ───────────────┘   └──────────────── BLOCO 2 ───────────────┘
```

Total: 1 + 16 + 1 = 18 ciclos, cerca de 48 s a 90 BPM.

### 4.3 Propriedades (para o resumo)

- **Tamanho:** o número de blocos segue uma distribuição geométrica com média 1/(1 − p), truncada em `max_blocos`. O número de ciclos é `2 + 8·n`.
- **Fração esperada de ciclos variados por bloco:** ε·(7 − v_a)/8 para tamborim e pandeiro e c·(7 − v_a)/8 para a cuíca, porque cada bloco tem 6 `G` fixos mais o `G` de `FIM_A`, que ocorre com probabilidade (1 − v_a). A cuíca não altera a taxa da levada. Use isso para validar o experimento (seção 9).
- **Limitação:** a gramática não lembra a última frase de cuíca, então não consegue proibir a repetição da mesma frase em ciclos seguidos (mesma limitação de D1).
- **A linguagem gerada é regular.** `BLOCOS` é recursiva só à direita e o resto é finito. Uma cadeia de Markov com estados que codificam a *posição na frase* geraria as mesmas músicas. A justificativa para a gramática é **legibilidade e hierarquia explícita**: `FIM_A` e `FIM_B` *são* esses estados, mas com nome e significado musical. Diga isso no resumo, em vez de afirmar que a gramática é "mais poderosa".
- **Limitação do formalismo:** para escolher o surdo uma vez e mantê-lo, seria preciso duplicar a gramática por variante ou usar uma gramática de atributos. Por isso a decisão D1.

### 4.4 Restrição de autoria (regra do TP)

O PDF proíbe que IA gere **na íntegra** a implementação do método. Portanto, apenas **as regras e o expansor (`gramatica.py`) devem ser escritos por você.** O expansor é pequeno:

- um dicionário que mapeia cada não-terminal para uma lista de pares (expansão, probabilidade);
- uma função recursiva que expande a partir de `MÚSICA` usando `random.Random(seed)`;
- o retorno é a lista de terminais.

Código auxiliar (sampler, recorte do BRID, render, experimentos) e tudo mais gerado, pode ter apoio de IA, desde que declarado no README.

---

## 5. Vocabulário (terminal → arranjo)

Todos os arrays abaixo são **rascunho**: vieram de memória e precisam ser validados de ouvido. A página interativa "O ciclo do samba", na sua galeria de artifacts, permite editar as casas clicando e copia o array no formato abaixo.

### 5.1 Padrões base

```python
# Surdo (fixo, D1)
SD1      = [0,0,0,0,2,0,0,0,  0,0,0,0,2,0,0,0]   # primeira: forte no tempo 2
SD2      = [1,0,0,0,0,0,0,0,  1,0,0,0,0,0,0,0]   # segunda: responde no tempo 1

# Tamborim: telecoteco (a "clave")
TB_BASE  = [1,0,1,0,1,1,0,1,  0,1,0,1,1,0,1,0]

# Pandeiro: RASCUNHO. Substituir pelo padrão transcrito do BRID (seção 7.4)
PD_P     = [1,1,1,2,1,1,1,2,  1,1,1,2,1,1,1,2]   # platinela contínua, acento na 4ª semicolcheia
PD_G     = [1,0,0,0,1,0,0,0,  1,0,0,0,1,0,0,0]   # grave na cabeça do tempo
PD_T     = [0,0,0,0,0,0,0,1,  0,0,0,0,0,0,0,1]   # tapa no fim do compasso

# Cuíca: sem base. Silêncio fora das frases cu1..cu4 (D5)
```

### 5.2 Variantes

**Princípio:** a variante preserva a identidade da base. No tamborim, mantenha o **1º compasso** (a "pergunta") e mexa no 2º, e **nunca inverta a direção da clave**. Em toda variante, mude no máximo 2 a 3 casas.

```python
TB_V1 = [1,0,1,0,1,1,0,1,  0,1,1,0,1,0,1,1]   # resposta rearranjada
TB_V2 = [1,0,1,0,1,1,0,1,  0,1,0,1,1,1,1,1]   # semicolcheias no fim: "chama" o próximo ciclo
TB_V3 = [1,0,1,1,0,1,0,1,  0,1,0,1,1,0,1,0]   # antecipação no 1º compasso (a mais rara)

PD_V1: PD_T movido para [0,0,0,1,0,0,0,0,  0,0,0,1,0,0,0,1]   # tapas deslocados
PD_V2: PD_G com antecipação  [1,0,0,1,1,0,0,0,  1,0,0,1,1,0,0,0]

Frases da cuíca (a = aguda, G = grave). Não seguem o princípio de preservar uma base, porque a cuíca não tem base:
CU_V1: ". . . a G G G . | . . . a G . a ."   antecipação da aguda puxando o surdo de primeira; acento na aguda do passo 11
CU_V2: ". a . G . a . G | . a G G G . . ."   nos espaços do tamborim; acento na grave do passo 10
CU_V3: "a . G . a a . G | . G . . a a a ."
CU_V4: ". a G . G . G . | . a G G G G G ."
Versão final escrita pelo autor, de ouvido, a partir das ideias de antecipação, pergunta e resposta e encaixe nos espaços do tamborim.
```

### 5.3 Tabela terminal → arranjo

`¹` = só o 1º compasso (passos 0–7) da base; `UNI` = figura em uníssono no 2º compasso.

| Terminal | sd1 | sd2 | pd_g / pd_p / pd_t | tb | cu |
|---|---|---|---|---|---|
| `cont` | — | — | — | contagem `[1,0,0,0,1,0,0,0, 1,0,0,0,1,0,0,0]` | — |
| `base` | SD1 | SD2 | PD base | TB_BASE | — |
| `tb1..3` | SD1 | SD2 | PD base | **TB_Vk** | — |
| `pd1..2` | SD1 | SD2 | **PD_Vk** | TB_BASE | — |
| `cu1..4` | SD1 | SD2 | PD base | TB_BASE | **CU_Vk** |
| `virada` | base¹ + UNI | base¹ + UNI | base¹, depois só pd_t em UNI | base¹ + UNI | aguda em UNI no 2º compasso |
| `breque` | base¹ + BRQ | base¹ + BRQ | base¹, depois só pd_t em BRQ | base¹ + BRQ | aguda em BRQ no 2º compasso |
| `final` | `[2,0,…,0]` | `[2,0,…,0]` | pd_t `[2,0,…,0]` | `[2,0,…,0]` | aguda `[2,0,…,0]` |

```python
UNI = [2,0,0,2,0,0,2,0]   # 2º compasso da virada: figura 3-3-2, todos juntos (RASCUNHO)
BRQ = [2,0,0,0,0,0,0,0]   # 2º compasso do breque: uma batida no tempo 1, depois silêncio
```

O ciclo seguinte à virada ou ao breque recomeça normalmente no passo 0, e é ali que o improvisador "reentra".

---

## 6. Eventos e MIDI (`midi_out.py`)

### 6.1 Tempo de cada nota

```
t(c, i) = (16·c + i)·Δ  +  balanco · μ[i mod 4]·Δ  +  N(0, σ_t)
```

- `c` = índice do ciclo na derivação; `i` = passo de 0 a 15.
- `μ` = deslocamento médio por posição no tempo (microtiming), em frações de Δ. O padrão é `[0,0,0,0]`. Se a seção 7.6 for feita, use os valores medidos no BRID.
- `σ_t` ≈ 4 ms de humanização.

### 6.2 Velocidade

`1 → 78`, `2 → 108`, mais ruído N(0, 6), limitado a [1, 127].

### 6.3 Arquivo MIDI

- Use `pretty_midi`, com **um `Instrument(is_drum=True)` por instrumento** (surdo, pandeiro, tamborim, cuíca). Isso facilita os stems e a análise.
- Nota MIDI por pista, mapeada para o fallback General MIDI:

| Pista | Nota GM | Nome GM |
|---|---|---|
| sd1 | 41 | Low Floor Tom |
| sd2 | 43 | High Floor Tom |
| pd_g | 64 | Low Conga |
| pd_p | 54 | Tambourine |
| pd_t | 62 | Mute Hi Conga |
| tb | 65 | High Timbale |
| cu_g | 78 | Mute Cuica |
| cu_a | 79 | Open Cuica |

- A duração da nota é Δ·0,9. Ela é irrelevante para os one-shots, mas o MIDI precisa de uma.
- Ao lado de cada `.mid`, salve um **`.json`** com: hiperparâmetros, seed, a derivação (lista de terminais) e a árvore. Isso serve à reprodutibilidade e é material para a figura do resumo.

### 6.4 Seeds independentes

Use `random.Random(seed)` só para a gramática, `Random(seed + 1)` para a humanização e `Random(seed + 2)` para o round-robin do sampler. Assim, mudar o render não muda a música derivada.

---

## 7. Sampler a partir do BRID

### 7.1 Dataset

- **Brazilian Rhythmic Instruments Dataset (BRID):** <https://zenodo.org/records/14051323>. São 367 faixas (274 solo e 93 mix), 44,1 kHz, estéreo, gravadas em estúdio em Manaus, com anotações de beat.
- **Citação:** L. S. Maia, P. D. Tomaz Jr., M. Fuentes, M. Rocamora, L. W. P. Biscainho, M. V. M. Costa e S. Cohen, "A Novel Dataset of Brazilian Rhythmic Instruments and Some Experiments in Computational Rhythm Analysis", *2018 AES Latin American Congress of Audio Engineering*, pp. 53–60. DOI do dataset: 10.5281/zenodo.14051323. (Não é ISMIR 2018.)
- **Licença: CC BY 4.0** (confirmada no Zenodo em 12/10/2026). Os recortes curados podem ir no repositório, com atribuição em `samples/LICENSE-BRID.txt`.
  - Em qualquer caso, **nunca** suba o dataset inteiro, só os recortes curados (algumas dezenas de arquivos com menos de 1 s cada).

**Formato dos arquivos solo:** `[GID#] SW-XXX-YY-ZZ.wav`. Por exemplo, `[0185] S2-PD2-01-SA.wav` = instrumentista 2, Pandeiro 2, faixa 01, Samba.

### 7.2 Faixas selecionadas

Use **o instrumentista 2** sempre que possível, porque a mesma mão e a mesma sala dão um timbre coerente. Prefira **Samba (SA) a 80 BPM**: com as batidas mais espaçadas, os recortes saem mais limpos.

| Pista | Faixa principal | Reservas | Observação |
|---|---|---|---|
| sd1 | `0270 S2-SU2-01-SA` | `0180`, `0358` | surdo de primeira (Dó#) |
| sd2 | `0279 S2-SU3-06-SE` | `0184`, `0365` | **surdo de segunda real** (Mi). É samba-enredo a 130 BPM, mas isso não importa para one-shots |
| pd_* | `0185 S2-PD2-01-SA` | `0101`, `0281` | Pandeiro 2: 10", couro |
| tb | `0214 S2-TB2-01-SA` | `0129`, `0302` | Tamborim 2: baqueta de madeira, nylon |
| cu_* | `0245 S2-CU3-01-SA` | `0162` | grave e aguda rotuladas por f0 |
| referência | faixas `V*` (viradas) | — | **só para ouvir e transcrever** UNI e as variantes. Não use como samples |

### 7.3 Recorte (`tools/slice_brid.py`)

1. Carregue em mono a 44,1 kHz (`librosa.load(..., sr=44100, mono=True)`).
2. Detecte os onsets com `librosa.onset.onset_detect(..., backtrack=True, units="samples")`.
3. Recorte do onset k até o k+1, limitando ao comprimento máximo do instrumento: surdo 0,8 s, tamborim 0,25 s, pandeiro 0,2 s, cuíca 0,4 s.
4. Remova o silêncio inicial (threshold) e aplique um **fade-out de 10 ms**.
5. Descarte o primeiro e o último onset da faixa, e também recortes com duração ou RMS fora do intervalo [P10, P90].
6. Salve em `samples_raw/<instrumento>/<gid>_<k>.wav` e escreva um **manifest CSV** com: arquivo de origem, instante do onset, RMS, centroide espectral, razão de energia abaixo de 200 Hz, tempo de decaimento (ms até −20 dB) e **posição no tempo**, de 0 a 3 (seção 7.4).

### 7.4 Rotulagem das articulações

- **Posição no tempo:** as anotações de beat do BRID (`Annotations/beats/*.beats`, linhas `tempo_s  batida_no_compasso`) existem **só para as 93 mixagens**, nunca para as faixas solo. A grade de cada faixa solo é **ajustada aos onsets** (`GradeDeBeats` em `tools/slice_brid.py`):
  1. período livre em ±4% do BPM do PDF (o andamento é fixo por estilo: SA 80, PA 100, SE 130, MA 120, CA 65), escolhido pela coerência circular dos onsets na grade de semicolcheias;
  2. fase da semicolcheia pela média circular ponderada pela força do onset;
  3. qual das 4 semicolcheias é a cabeça do tempo: voto dos beats do `librosa.beat.beat_track`.
  - `pos = round((t_onset − t0) / Δ) mod 4`; o manifest guarda também o `beat` e o `desvio` em frações de Δ.
  - O passo 3 é a parte frágil: no pandeiro e no tamborim, que tocam as 4 semicolcheias, ele precisa ser confirmado de ouvido ou pelo cluster do grave do pandeiro.
- **Surdo:** um recorte aberto tem decaimento longo, e um abafado, decaimento curto. Use só os abertos para sd1 e sd2.
- **Pandeiro:** combine features e posição.
  1. Rode k-means com k = 3 sobre [razão de graves, centroide, decaimento].
  2. Ouça uns poucos recortes de cada cluster e nomeie-os: grave, platinela ou tapa.
  3. **Transcreva o padrão base do pandeiro a partir dos dados:** monte um histograma *articulação × posição no ciclo* sobre a faixa SA. Ele substitui os rascunhos `PD_G`, `PD_P` e `PD_T` da seção 5. Isso rende um bom parágrafo no resumo, porque o vocabulário passa a ser derivado de uma gravação real.
- **Tamborim:** tem uma articulação só. As camadas de velocidade vêm dos quantis de RMS.
- **Cuíca:** dois clusters por pitch (centroide ou f0): grave e aguda.

**A curadoria manual é permitida e honesta.** Ouça e mantenha os **4 a 8 melhores recortes por articulação e camada**, e documente isso no README.

### 7.5 Estrutura final e o sampler (`sampler.py`)

```
samples/
  surdo1/aberto/{v1,v2}/*.wav
  surdo2/aberto/{v1,v2}/*.wav
  pandeiro/{grave,platinela,tapa}/{v1,v2}/*.wav
  tamborim/batida/{v1,v2}/*.wav
  cuica/{grave,aguda}/{v1,v2}/*.wav
  LICENSE-BRID.txt
```

`v1` corresponde ao valor 1 do array, e `v2` ao valor 2, ou seja, às camadas de velocidade separadas por RMS.

O algoritmo do sampler, para cada nota do MIDI:

1. Mapeie pista → pasta.
2. Escolha a camada de velocidade (`vel ≥ 95 → v2`).
3. Escolha um arquivo por **round-robin aleatório** com `Random(seed + 2)`, sem repetir o mesmo arquivo duas vezes seguidas.
4. Aplique o ganho `(vel / 127) ** 1.7` multiplicado pelo ganho de mixagem do instrumento.
5. Some ao buffer na posição `int(t · 44100)`.

Ao final:

- normalize o pico para −1 dBFS;
- escreva o `.wav`;
- converta para `.mp3` com o ffmpeg;
- (opcional) exporte um stem por instrumento.

**Mixagem inicial** (ajuste de ouvido): surdo1 1,0 · surdo2 0,8 · pandeiro 0,6 · tamborim 0,7 · cuíca 0,5.

**Fallback:** se `samples/` não existir, renderize com `pretty_midi.fluidsynth()` e um soundfont GM livre. Assim o repositório é reproduzível mesmo sem o BRID.

### 7.6 Microtiming (opcional, se sobrar tempo)

Com o mesmo manifest:

1. Para os onsets de pandeiro e tamborim nas faixas SA, calcule o desvio entre o instante real e a grade ideal, em frações de Δ.
2. Agrupe os desvios por posição no tempo (0 a 3).
3. A **média** de cada grupo dá o vetor μ da seção 6.1.

Salve μ em `config/microtiming.json`. **Limitação a citar:** μ é medido a 80 BPM e aplicado a 90 BPM.

Referência: Naveda, Gouyon, Guedes & Leman, "Microtiming patterns and interactions with musical properties in samba music", *Journal of New Music Research*, 2011. *Confirme os dados da referência.*

---

## 8. Hiperparâmetros e CLI

| Parâmetro | Flag | Padrão | Efeito |
|---|---|---|---|
| seed | `--seed` | 1 | músicas diferentes com a mesma configuração |
| andamento | `--bpm` | 90 | não é do método. Use 70–80 para treinar |
| **variação** | `--epsilon` | 0.15 | **principal:** de playback monótono a percussão "conversando" |
| continuação | `--p` | 0.8 | tamanho: média de 5 blocos, cerca de 1min50 a 90 BPM |
| virada no meio do bloco | `--va` | 0.3 | marca a cada 8 compassos, além dos 16 |
| breque | `--b` | 0.3 | breque vs. virada no fim do bloco |
| limite de blocos | `--max-blocos` | 10 | segurança |
| presença da cuíca | `--cuica-presenca` | 0.25 | c: quanto a cuíca aparece (≈ 1,7 frases por bloco); ε + c ≤ 1 |
| variedade da cuíca | `--cuica-variedade` | 0.5 | v: de 0 (sempre `cu1`) a 1 (quatro frases equiprováveis) |
| balanço | `--balanco` | 0.0 | escala o microtiming μ (0 = quantizado) |
| render | `--render` | `brid` | `brid` ou `gm` |
| saída | `--out` | `output/` | |

```bash
python gerar.py --seed 3 --bpm 90 --epsilon 0.15 --p 0.8 --render brid
# → output/samba_s3_e0.15.{mid,json,wav,mp3}
```

---

## 9. Experimentos e músicas entregues

### 9.1 As três (ou mais) músicas

| Arquivo | Configuração | O que demonstra |
|---|---|---|
| `musica_1` | seed 1, ε = 0.15 (padrão) | resultado típico |
| `musica_2` | seed 2, ε = 0.15 | **mesma configuração, música diferente** (requisito) |
| `musica_3` | seed 1, ε = 0.45, b = 0.6 | **efeito do hiperparâmetro** (requisito) |
| (bônus) `musica_4` | seed 1, ε = 0 | controle: levada pura, só a forma varia |

### 9.2 Experimento quantitativo (não implementado; ver seção 15)

Para ε ∈ {0, 0.1, 0.2, 0.3, 0.45, 0.6}, gere 30 seeds e meça:

- **taxa de variação:** número de ciclos variantes de tamborim e pandeiro (`tb*`, `pd*`) dividido pelo número de ciclos dos blocos (sem contar `cont` e `final`). Virada e breque não contam como variação. A presença da cuíca (`cu*`) é medida à parte, com a curva c·(7 − v_a)/8;
- **entropia de Shannon (bits)** da distribuição de terminais em cada música;
- (opcional) a duração média em função de p, para comparar com 1/(1 − p).

O resultado vira **uma figura** com média ± desvio por ε, mais a **curva teórica ε·(7 − v_a)/8** sobreposta. A curva teórica mostra que o sistema faz o que a gramática diz. Ouvir os ε extremos dá a discussão qualitativa.

### 9.3 Critérios de aceitação

- [ ] A mesma seed e os mesmos parâmetros geram um `.mid` byte a byte idêntico (verifique por hash).
- [ ] O número de ciclos é sempre 2 + 8·n, com n ≤ `max_blocos`.
- [ ] `virada` e `breque` só aparecem nas posições 3 e 7 de cada bloco, contando a partir de 0.
- [ ] Com ε = 0 e c = 0, só aparecem `base`, `virada`, `breque`, `cont` e `final`.
- [ ] A cuíca não muda a taxa de variação de tamborim e pandeiro.
- [ ] O `.mid` abre e toca no MuseScore ou numa DAW.
- [ ] O render funciona com `--render gm` sem a pasta `samples/`.

---

## 10. Estrutura do repositório

```
samba-gramatica/
├── README.md              instalação, reprodução, uso de IA (com links), créditos do BRID
├── requirements.txt       pretty_midi, numpy, scipy, soundfile, librosa, scikit-learn, matplotlib, pyfluidsynth
├── gerar.py               CLI
├── src/
│   ├── gramatica.py       regras + expansor          ← ESCRITO POR VOCÊ
│   ├── vocabulario.py     arrays e tabela terminal → arranjo
│   ├── arranjo.py         derivação → grade (pista × passo)
│   ├── midi_out.py        grade → eventos → .mid/.json
│   ├── sampler.py         .mid → .wav (BRID)
│   └── render_gm.py       fallback FluidSynth
├── tools/
│   ├── slice_brid.py      recorte + manifest
│   └── label_brid.py      clusters + posição no tempo + histograma + biblioteca provisória
├── tests/                 pytest: aceite da gramática, vocabulário, MIDI, sampler, BRID
├── docs/                  spec.md + diretrizes.pdf
├── samples/               recortes curados + LICENSE-BRID.txt + curadoria.csv
├── output/                músicas entregues (.mid, .json, .wav, .mp3)
└── resumo/                LaTeX no template ISMIR + PDF
```

---

## 11. Plano de execução até 09/10, 23:59

| Fase | Entregável | Tempo |
|---|---|---|
| **1. Núcleo** | vocabulário (rascunho) + gramática + MIDI + render GM → as 3 músicas já existem | ~4 h |
| **2a. BRID** | recorte, rotulagem e curadoria (surdo, tamborim, pandeiro) + sampler → re-render | ~3–4 h |
| 2b. Cuíca | recorte, frases e hiperparâmetros c e v | ~1 h |
| **3. Experimento** | script, figura e 4ª música | ~1 h |
| **4. Resumo ISMIR** | 2 páginas, seção 12 | ~4–5 h |
| **5. README** | instruções e declaração de IA | ~30 min |

**Regra de ouro:** ao fim da fase 1 você já tem um TP entregável. Tudo depois disso é melhoria.

**Ordem de corte**, do primeiro ao último a cair: microtiming → cuíca → pandeiro do BRID (fica no GM) → BRID inteiro (render GM). **A gramática, o MIDI, as 3 músicas, o resumo e o README não são cortáveis.**

---

## 12. Roteiro do resumo ISMIR (2 páginas)

1. **Introdução:** backing track de samba para praticar improvisação no cavaquinho; a gramática probabilística como método; a restrição estilística.
2. **Trabalhos relacionados** (pelo menos 1, mas cite 3 ou 4):
   - Steedman (1984), gramática generativa para progressões de jazz;
   - Lerdahl & Jackendoff (1983), GTTM, sobre hierarquia em música;
   - Sandroni (2001), *Feitiço Decente*, sobre o paradigma rítmico do samba e o telecoteco;
   - Maia et al. (2018), o BRID;
   - Naveda et al. (2011), microtiming no samba.

   *Verifique todas as referências antes de citar.*
3. **Método:**
   - representação: grade de 16 semicolcheias, terminal = ciclo (justifique pela clave);
   - a gramática formal: a seção 4.1, compacta;
   - o vocabulário, com 1 figura da grade;
   - os hiperparâmetros;
   - o render com os recortes do BRID.
4. **Resultados:** as 3 músicas e o que varia entre elas; a figura de taxa de variação × ε com a curva teórica; uma discussão qualitativa do que se ouve nos extremos de ε.
5. **Discussão e limitações:**
   - linguagem regular (equivalência com Markov) e o argumento de legibilidade;
   - surdo fixo pela limitação da gramática livre de contexto;
   - variação combinatória, não improvisação;
   - padrões transcritos à mão;
   - timbres de instrumentistas e salas diferentes;
   - microtiming medido a 80 BPM.

   **Trabalhos futuros:** gramática de atributos (surdo por música), variação condicionada à harmonia do cavaquinho, mais instrumentos (caixa, repique).

---

## 13. Declaração de uso de IA (README)

Inclua no README:

- **Ferramenta:** Claude.
- **Usado para:** discussão da ideia e do escopo; escolha entre gramática e Markov; pesquisa do dataset BRID; POC de timbres GM; este documento de especificação; [o que mais for usado na implementação, como sampler ou recorte].
- **Não usado para:** gerar a gramática e o expansor (escritos pelo autor), nem para escrever o resumo na íntegra.
- **Links das conversas:** [cole o link desta conversa e das sessões de implementação].

---

## 14. Pendências a resolver durante a implementação

1. ~~**Licença do BRID**~~: resolvida, CC BY 4.0 (seção 7.1).
2. ~~**Formato das anotações de beat do BRID**~~: resolvida, só há anotação para mixagens; a grade dos solos é ajustada aos onsets (seção 7.4).
3. **Validar de ouvido** o telecoteco, as variantes do tamborim, `UNI` e o padrão do pandeiro (que deve vir do histograma).
4. **Template ISMIR:** baixe-o em ismir.net logo no início, porque o LaTeX sempre consome tempo.

---

## 15. Registro de mudanças no spec

- **12/10/2026 — 7.1:** licença confirmada como CC BY 4.0; citação corrigida (AES Latin American Congress 2018, não ISMIR).
- **12/10/2026 — 7.4:** solos do BRID não têm anotação de beat. Decisão: grade ajustada aos onsets com BPM do PDF como referência, em vez das anotações.
- **12/10/2026 — 4.4 / 9.3:** `src/gramatica.py` nasce como stub (`derivar(hiper, seed) -> list[Terminal]`, lança `NotImplementedError`) com os testes de aceite em `tests/test_gramatica.py`, que ficam em *skip* até a implementação. O teste de posições segue a gramática: virada nas posições 3 e 7, breque só na 7.
- **12/10/2026 — 7.4 / 7.5:** `tools/label_brid.py` monta uma biblioteca **provisória** em `samples/`, só da faixa principal de cada pista (instrumentista 2). Surdo aberto = decaimento ≥ P60. Pandeiro = k-means k = 3 (melhor de 10 inicializações) sobre [razão de graves, log do centroide, decaimento], com nomes dados pela razão de graves: grave > tapa > platinela. Cuíca = k-means k = 2 pelo centroide. Camadas: v2 = RMS ≥ P70; v1 = RMS entre P40 e P70, o que deixa de fora as notas fantasma do tamborim. Por camada ficam os 6 recortes mais típicos (mais próximos da mediana das features) e um ganho único por instrumento (pico −1 dBFS). A escolha final continua sendo de ouvido.
- **12/10/2026 — 7.5:** a cuíca também usa `v1/` e `v2/`, como as outras pistas. O sampler cai na outra camada quando uma está vazia.
- **12/10/2026 — 5.2:** `cu1` e `cu2` são recusados pelo vocabulário até `CU_V1` e `CU_V2` serem definidos.
- **12/10/2026 — 7.5:** o fallback GM usa o FluidR3 do sistema e, se ele faltar, o soundfont embutido no `pretty_midi`.
- **12/10/2026 — 8:** `gerar.py` ganhou `--derivacao "<terminais>"` (renderiza uma sequência fixa sem a gramática), `--nome`, `--samples` e `--mostrar-grade` (imprime a grade pista × semicolcheia por ciclo).
- **12/10/2026 — 5.1 / 5.2:** cuíca transcrita da faixa 0245. Grave e aguda foram rotuladas pelo f0 (dois picos: ~300 Hz e ~750 Hz), e o padrão foi lido na grade, compasso a compasso. A base são pares aguda-aguda-grave-grave em semicolcheias contínuas; `cu1` = "a a a a G G G G" e `cu2` = respiro "a . a . a a a a" no 2º compasso. `cu1`/`cu2` com a cuíca desativada são recusados.
- **12/10/2026 — 7.3 / 7.4:** o manifest ganhou `f0_hz` (pYIN, 150–2000 Hz, só para a cuíca). A cuíca é agrupada por k-means k = 2 no log do f0, e recortes sem altura detectável ficam fora. Na escolha dos mais típicos, o f0 entra junto com as outras features quando existe.
- **12/10/2026 — 7.5:** `label_brid.py --instrumentos <lista>` refaz só os instrumentos pedidos e preserva os arquivos e as linhas de `curadoria.csv` dos demais.
- **12/10/2026 — 5.1 / 5.2 (revisão de ouvido):** a base transcrita em pares contínuos soou mecânica. Voltou o rascunho esparso do spec (`. . G . a . G .` por compasso). As variantes passaram a ser repetições com respiros: `cu1` = `a . a . a a a a` no 2º compasso; `cu2` = `a a G G | G a . a G . G G`, começando no 2º tempo do 1º compasso. As duas mantêm o 1º tempo da base. A rotulagem por f0 continua valendo para as amostras.
- **12/10/2026 — D5, 3.4, 4.1, 4.3, 5, 8, 9 (cuíca com probabilidade própria):** a cuíca deixou de ter base e de ser opcional. Ela toca só nas frases `cu1..cu4` (Σ ganhou `cu3` e `cu4`), e sai de cena na base, nas viradas e nos breques. Dois hiperparâmetros novos: **c** (`cuica_presenca`, `G → VAR_CU [c]`) e **v** (`cuica_variedade`, `VAR_CU → cu1 [1 − 3v/4] | cu2..cu4 [v/4]`). O K saiu; ε divide-se em ε/2 para tamborim e pandeiro, com ε + c ≤ 1 validado em `Hiperparametros`. A CLI perdeu `--instrumentos` e ganhou `--cuica-presenca` e `--cuica-variedade`. A taxa de variação do experimento conta só tamborim e pandeiro; a cuíca tem curva própria.
- **12/10/2026 — 5.2 / 5.3 (vocabulário final):** as quatro frases da cuíca foram reescritas pelo autor, e `cu1`/`cu2` têm um acento cada. A aguda da cuíca toca a figura das marcas de forma: `UNI` na virada, `BRQ` no breque e o acento do `final`. A grave fica fora delas.
- **12/10/2026 — 7.6 / 9.2 / 10 (escopo final):** o microtiming (7.6) e o experimento quantitativo (9.2) não foram implementados; `experimentos/` e `config/` saíram do repositório. O resumo usa a discussão qualitativa das músicas. Sem `config/microtiming.json`, μ = 0, e `--balanco` não tem efeito.
- **12/10/2026 — 4.1:** `VAR_PD` ficou com pesos 0,5/0,5, como na `gramatica.py` do autor (antes: 0,60/0,40).
