"""Três formas de achar os artigos certos para uma pergunta, e a combinação delas.

- BM25: casa palavras. Bom quando a pergunta usa os termos da lei ("orçamento", "cadastro").
- Denso: compara significados com embeddings. Bom quando a pergunta usa palavras do dia a dia
  ("meu nome no Serasa") que a lei diz de outro jeito ("cadastros de consumidores").
- Híbrido: junta as duas listas com Reciprocal Rank Fusion (RRF), que só olha a posição de cada
  artigo em cada lista. Assim não é preciso calibrar escalas de pontuação diferentes.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

RAIZ = Path(__file__).resolve().parents[2]
ARTIGOS = RAIZ / "data" / "processed" / "artigos.jsonl"
CACHE = RAIZ / "data" / "cache"
# prefixos que cada modelo espera na consulta e no documento
MODELOS_EMBEDDING = {
    "intfloat/multilingual-e5-small": ("query: ", "passage: "),
    "intfloat/multilingual-e5-base": ("query: ", "passage: "),
    "BAAI/bge-m3": ("", ""),
}
MODELO_EMBEDDING = "BAAI/bge-m3"

def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


# "não" fica de fora de propósito: "não recebi" e "recebi" são reclamações diferentes
STOPWORDS = {
    _sem_acento(p)
    for p in ["a", "o", "e", "é", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "com", "sem", "que", "se", "ao", "aos", "à", "às", "ou", "como", "mais", "mas", "foi", "ser", "são", "tem", "ter", "eu", "meu", "minha", "me", "isso", "essa", "esse", "este", "esta", "ele", "ela", "eles", "elas", "pode", "posso", "qual", "quais", "quando", "onde", "quem", "já", "sim", "seu", "sua", "seus", "suas", "lhe"]
}


@dataclass
class Resultado:
    id: str
    numero: str
    pontuacao: float


def normalizar(texto: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", _sem_acento(texto)) if t not in STOPWORDS and len(t) > 1]


def carregar_artigos() -> list[dict]:
    with ARTIGOS.open(encoding="utf8") as f:
        return [a for a in map(json.loads, f) if not a["vetado"]]


def texto_indexado(artigo: dict) -> str:
    # o nome do capítulo e da seção ajudam: "Da Cobrança de Dívidas" diz muito sobre o art. 42
    return " · ".join(artigo["estrutura"] + [artigo["texto"]])


def trechos(artigo: dict) -> list[str]:
    """Quebra o artigo em caput, parágrafos e incisos, cada um com o caput e a seção de contexto.

    Um inciso solto ("III - enviar ao consumidor, sem solicitação prévia...") não diz que se trata
    de prática abusiva; isso está no caput. Por isso todo trecho carrega o caput junto.
    """
    linhas = artigo["texto"].splitlines()
    contexto = " · ".join(artigo["estrutura"][-1:] + [linhas[0]])
    return [contexto] + [f"{contexto} {linha}" for linha in linhas[1:]]


class Buscador:
    """Busca artigos. Com granularidade="trecho", indexa cada parágrafo e inciso separadamente e
    a nota do artigo é a do seu melhor trecho."""

    def __init__(
        self, artigos: list[dict] | None = None, granularidade: str = "artigo", modelo: str = MODELO_EMBEDDING
    ):
        self.artigos = artigos or carregar_artigos()
        self.granularidade = granularidade
        self.modelo = modelo
        self._prefixo_consulta, self._prefixo_documento = MODELOS_EMBEDDING[modelo]
        self._unidades: list[tuple[int, str]] = []  # (índice do artigo, texto indexado)
        for i, a in enumerate(self.artigos):
            textos = trechos(a) if granularidade == "trecho" else [texto_indexado(a)]
            self._unidades += [(i, t) for t in textos]
        self._dono = np.array([i for i, _ in self._unidades])
        self._bm25 = BM25Okapi([normalizar(t) for _, t in self._unidades])

    @cached_property
    def _modelo(self):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.modelo, device="cpu")

    @cached_property
    def _vetores(self) -> np.ndarray:
        CACHE.mkdir(parents=True, exist_ok=True)
        nome = self.modelo.split("/")[-1]
        caminho = CACHE / f"vetores_{nome}_{self.granularidade}_{len(self._unidades)}.npy"
        if caminho.exists():
            return np.load(caminho)
        # o e5 foi treinado com os prefixos "passage:" e "query:"; sem eles a qualidade cai
        vetores = self._modelo.encode(
            [self._prefixo_documento + t for _, t in self._unidades], normalize_embeddings=True, batch_size=8
        )
        np.save(caminho, vetores)
        return vetores

    def _ordenar(self, pontuacoes: np.ndarray, k: int) -> list[Resultado]:
        # nota do artigo = nota do seu melhor trecho
        por_artigo = np.full(len(self.artigos), -np.inf)
        np.maximum.at(por_artigo, self._dono, pontuacoes)
        ordem = np.argsort(-por_artigo)[:k]
        pontuacoes = por_artigo
        return [Resultado(self.artigos[i]["id"], self.artigos[i]["numero"], float(pontuacoes[i])) for i in ordem]

    def bm25(self, pergunta: str, k: int = 5) -> list[Resultado]:
        return self._ordenar(np.asarray(self._bm25.get_scores(normalizar(pergunta))), k)

    def denso(self, pergunta: str, k: int = 5) -> list[Resultado]:
        consulta = self._modelo.encode([self._prefixo_consulta + pergunta], normalize_embeddings=True)[0]
        return self._ordenar(self._vetores @ consulta, k)

    def hibrido(self, pergunta: str, k: int = 5, profundidade: int = 30, c: int = 60) -> list[Resultado]:
        listas = [self.bm25(pergunta, profundidade), self.denso(pergunta, profundidade)]
        return fundir(listas, k, c)

    def artigo(self, id_: str) -> dict:
        return next(a for a in self.artigos if a["id"] == id_)


def fundir(listas: list[list[Resultado]], k: int, c: int = 60) -> list[Resultado]:
    """Reciprocal Rank Fusion: cada lista dá 1/(c + posição) a cada artigo; somam-se as notas."""
    notas: dict[str, float] = {}
    numeros: dict[str, str] = {}
    for lista in listas:
        for posicao, r in enumerate(lista, start=1):
            notas[r.id] = notas.get(r.id, 0.0) + 1.0 / (c + posicao)
            numeros[r.id] = r.numero
    melhores = sorted(notas, key=notas.get, reverse=True)[:k]
    return [Resultado(i, numeros[i], notas[i]) for i in melhores]
