# cdc-rag

Responde dúvidas de consumidores sobre o **Código de Defesa do Consumidor** citando o artigo da
lei, e recusa a resposta quando não consegue citar direito.

```
$ cdc perguntar "Comprei um celular pela internet e me arrependi. Posso devolver?"
```

O foco do projeto não é a resposta em si, é **medir** cada parte: se a busca acha o artigo certo,
se o modelo cita o que recebeu, e se ele sabe dizer "isso não está no CDC".

## Como funciona

```
pergunta ──► busca (bge-m3) ──► 5 artigos ──► LLM ──► conferência de citações ──► resposta
                                                         │
                                       citação inventada ou ausente: o modelo recebe o
                                       motivo e tenta de novo; se falhar outra vez, o
                                       sistema devolve só os artigos encontrados
```

1. **Ingestão** (`ingestao.py`): o HTML oficial do Planalto vira 130 artigos, cada um com caput,
   parágrafos, incisos e o caminho na lei (título, capítulo, seção). As anotações de alteração
   ("Incluído pela Lei nº 14.181") são separadas do texto. Os 12 artigos vetados por inteiro saem
   da busca.
2. **Busca** (`busca.py`): BM25, embeddings densos e a fusão das duas (RRF). A unidade é o artigo,
   porque é a unidade de citação.
3. **Resposta** (`resposta.py`): o modelo recebe os artigos e só pode usá-los. A conferência é
   feita no código, não confiando no modelo: toda citação tem que ser de um artigo entregue a ele, e
   uma resposta sem citação é recusada.

## Avaliação da busca

61 perguntas escritas como um consumidor escreveria ("meu nome pode ficar no Serasa por quanto
tempo?"), cada uma com o artigo correto conferido no texto da lei, mais 5 perguntas fora do
escopo do CDC. Arquivo: `data/perguntas.jsonl`.

| Método | Acerto@1 | Acerto@3 | Acerto@5 | MRR |
|---|---|---|---|---|
| BM25 | 0,328 | 0,508 | 0,541 | 0,421 |
| Denso, multilingual-e5-small | 0,525 | 0,705 | 0,738 | 0,608 |
| Denso, multilingual-e5-base | 0,475 | 0,639 | 0,721 | 0,566 |
| **Denso, bge-m3** | **0,672** | **0,836** | **0,869** | **0,753** |
| Híbrido (BM25 + bge-m3, RRF) | 0,475 | 0,574 | 0,623 | 0,519 |
| Denso, bge-m3, indexando por trecho | 0,623 | 0,869 | 0,885 | 0,747 |

*Acerto@k: em quantas perguntas um artigo certo aparece entre os k primeiros. MRR: média de
1/posição do primeiro artigo certo.*

**O que os números mostram**

- **O problema é de vocabulário.** O consumidor diz "Serasa", "cartão que eu não pedi", "o
  vendedor me deu um recibo"; a lei diz "cadastros de consumidores", "sem solicitação prévia",
  "escritos particulares". BM25, que casa palavras, acerta só metade.
- **O modelo de embedding importa mais que qualquer outro ajuste.** Trocar o e5-small pelo bge-m3
  subiu o acerto@5 de 74% para 87%. O e5-base, maior que o small, foi *pior*: tamanho não garante
  nada, só medindo.
- **Híbrido piorou.** É o resultado contrário ao senso comum. Com perguntas coloquiais, a lista do
  BM25 traz artigos irrelevantes no topo e a fusão os promove. Busca híbrida ajuda quando as duas
  listas são razoáveis; aqui uma delas não é.
- **Indexar por trecho (parágrafo ou inciso) não compensou.** A hipótese era que artigos longos,
  como o art. 39 com 14 incisos, diluíam o significado. O acerto@5 subiu um ponto, mas o acerto@1
  caiu cinco. A versão por artigo ficou como padrão.

Os 8 erros que sobram com o bge-m3 estão em `resultados/busca.json` e têm dois padrões:

- **Artigo-lista.** O art. 39 enumera 14 práticas abusivas num artigo só. Quem pergunta sobre
  "venda casada" ou "cartão que eu não pedi" descreve um inciso, e o vetor do artigo inteiro fica
  longe. O art. 6º (direitos básicos) tem o mesmo problema.
- **Artigos penais competindo.** Para "meu nome no Serasa", a busca traz os arts. 72 e 73, que
  definem os *crimes* ligados a cadastros, em vez do art. 43, que define os *direitos*. Os textos
  são parecidos; o que muda é a seção da lei.

Próximos testes, nesta ordem: um reranker (cross-encoder) sobre os 20 primeiros e reescrita da
pergunta pelo LLM para a linguagem da lei. Ajustar pesos olhando estes mesmos erros seria
otimizar para o teste, por isso fica de fora.

## Avaliação das respostas

`cdc avaliar-respostas` roda o sistema completo nas 66 perguntas e mede, sem depender de opinião:

- **aceitas**: passaram na conferência de citações;
- **cita o artigo certo**: geral e só nos casos em que a busca entregou o artigo certo (separa
  erro de busca de erro de geração);
- **fora do escopo recusadas**: o modelo respondeu `FORA_DO_CDC` em vez de inventar;
- **precisou de segunda tentativa**: quanto a conferência está segurando o modelo.

> Resultados por modelo: em andamento.

## Rodando

```bash
uv sync
uv run python -m cdc_rag.ingestao          # gera data/processed/artigos.jsonl
uv run cdc buscar "meu nome no Serasa"      # só a busca, sem LLM
uv run cdc avaliar-busca

# com um modelo (um dos dois):
export ANTHROPIC_API_KEY=...                                   # Claude
export LLM_BASE_URL=http://localhost:11434/v1 LLM_MODELO=qwen2.5:7b-instruct   # Ollama, vLLM
uv run cdc perguntar "Recebi um cartão de crédito que eu não pedi. Pode isso?"
uv run cdc avaliar-respostas
```

Testes (não precisam de modelo nem de internet): `uv run pytest`.

## Limites

- Não é aconselhamento jurídico. Só o texto do CDC entra; jurisprudência, súmulas e leis
  relacionadas (como as normas da ANAC ou do Banco Central) ficam de fora.
- O gabarito foi escrito por uma pessoa só. Perguntas com mais de um artigo defensável aceitam
  qualquer um da lista, mas ainda há julgamento envolvido.

## Fonte

Lei nº 8.078/1990, texto compilado do [Planalto](https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm).
Textos de lei não são protegidos por direito autoral (Lei nº 9.610/1998, art. 8º, IV).
