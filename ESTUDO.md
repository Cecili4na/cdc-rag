# Guia de estudo deste projeto

RAG é o assunto mais cobrado em entrevista de engenharia de IA. Para cada parte: o que estudar e
as perguntas que podem cair. Responda em voz alta antes de ler a resposta.

## 1. O que é RAG e por que existe

**Estudar:** o artigo original "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
(Lewis et al., 2020), só a introdução; o capítulo de RAG do curso gratuito de LLM da Hugging Face.

- Por que não perguntar direto ao LLM?
  > Ele pode não saber, saber errado ou desatualizado, e não diz de onde tirou. Com RAG, a resposta
  > vem de documentos que você controla e pode citar.
- Quais as duas metades de um RAG e qual falha mais?
  > Busca e geração. Se a busca não traz o documento certo, nenhum modelo acerta. Por isso a busca
  > foi medida separada aqui, e o resumo das respostas tem a métrica "cita o artigo certo *quando
  > recuperado*", que isola o erro de geração.

## 2. Divisão em pedaços (chunking) — `ingestao.py`

- Por que o pedaço aqui é o artigo?
  > Porque a citação é por artigo. Pedaços de tamanho fixo (500 tokens) cortariam um artigo no meio
  > e misturariam dois.
- Você testou outra divisão?
  > Sim, por parágrafo e inciso, levando o caput junto. Empatou: acerto@5 subiu um ponto, acerto@1
  > caiu cinco. Fiquei com a mais simples.

## 3. BM25 — `busca.py`

**Estudar:** a página da Wikipédia "Okapi BM25" e o vídeo "BM25 explained" (qualquer um curto).

- O que o BM25 mede?
  > Quantas palavras da pergunta aparecem no documento, valorizando palavras raras (IDF) e com
  > retorno decrescente para repetições, normalizado pelo tamanho do documento.
- Por que ele foi mal aqui?
  > A pergunta usa palavras do dia a dia e a lei usa termos técnicos. Ele casa palavras, não
  > significados.
- Que bug os testes pegaram?
  > As palavras vazias com acento ("é", "são") nunca eram removidas, porque a comparação era feita
  > depois de tirar os acentos. E "não" foi mantida de propósito: "não recebi" é outra reclamação.

## 4. Embeddings — `busca.py`

**Estudar:** "What are embeddings" (Vicki Boykis, gratuito); o placar MTEB da Hugging Face.

- O que é um embedding?
  > Um vetor que representa o significado de um texto. Textos parecidos ficam próximos; a
  > proximidade é medida pelo cosseno (aqui, produto interno de vetores normalizados).
- Para que servem os prefixos "query:" e "passage:" do e5?
  > O modelo foi treinado assim, para tratar pergunta e documento de jeitos diferentes. Sem eles,
  > a qualidade cai.
- Como você escolheu o modelo?
  > Medindo três no mesmo conjunto de perguntas. O bge-m3 ganhou com folga, e o e5-base, maior que
  > o small, foi pior. Não se escolhe modelo pelo tamanho nem pela fama.

## 5. Busca híbrida e RRF — `busca.py`

- Como funciona o Reciprocal Rank Fusion?
  > Cada lista dá a cada documento 1/(60 + posição); somam-se as notas. Usa só a posição, então não
  > precisa calibrar a escala do BM25 com a do cosseno.
- Por que o híbrido piorou?
  > Porque uma das listas (BM25) era ruim. A fusão promove o que aparece bem em qualquer lista, e o
  > lixo do BM25 subiu. Híbrido não é melhor por definição.

## 6. Métricas de busca — `avaliar_busca.py`

- Diferença entre acerto@k (recall@k) e MRR?
  > Acerto@5 pergunta "o certo veio entre os 5?". MRR também liga para a posição: acertar em 1º
  > vale 1, em 2º vale 0,5. Para RAG que manda 5 artigos ao modelo, acerto@5 é o que mais importa.
- Por que não ajustou o sistema olhando os erros?
  > Porque os erros são do conjunto de teste. Ajustar olhando para eles infla a métrica e o número
  > deixa de dizer como o sistema vai se sair em perguntas novas.

## 7. Geração com citação e guardrails — `resposta.py`

- Como você garante que o modelo não inventa artigo?
  > Não garanto pedindo: confiro no código. Toda citação tem que estar entre os artigos
  > entregues; sem citação, a resposta é recusada. O modelo tem uma segunda chance com o motivo da
  > recusa; se falhar de novo, o usuário recebe só os artigos.
- A conferência garante que a resposta está certa?
  > Não. Garante que cada afirmação aponta para um artigo que o modelo leu. O modelo ainda pode
  > ler errado. Para isso a avaliação mede se ele cita o artigo do gabarito.
- E perguntas fora do escopo?
  > O modelo é instruído a responder FORA_DO_CDC. A avaliação tem 5 perguntas assim (trabalhista,
  > tributária, aviação) e conta quantas ele recusa.

## 8. Engenharia

- Por que o LLM fica atrás de uma interface (`llm.py`)?
  > Para trocar de provedor (Claude, um modelo aberto num servidor próprio) sem mexer no resto, e
  > para os testes usarem um modelo falso que devolve respostas prontas.
- Como testar um sistema que depende de LLM?
  > Separando o que é determinístico (extração, busca, conferência de citações) e testando com um
  > modelo roteirizado. Os testes rodam sem internet e em menos de um segundo.
