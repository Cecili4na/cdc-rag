"""Mede os três métodos de busca contra as perguntas com artigo conhecido.

Métricas:
- acerto@k: em quantas perguntas pelo menos um artigo certo aparece entre os k primeiros.
  É o que importa para o RAG: se o artigo não chega ao modelo, a resposta não tem como citá-lo.
- MRR: média de 1/posição do primeiro artigo certo. Premia acertar logo no topo.
"""

import json
from pathlib import Path

from cdc_rag.busca import MODELOS_EMBEDDING, Buscador

RAIZ = Path(__file__).resolve().parents[2]
PERGUNTAS = RAIZ / "data" / "perguntas.jsonl"
RESULTADOS = RAIZ / "resultados"
KS = (1, 3, 5)


def avaliar(buscador: Buscador, metodo: str, perguntas: list[dict]) -> dict:
    buscar = getattr(buscador, metodo)
    acertos = {k: 0 for k in KS}
    soma_rr = 0.0
    erros = []
    for p in perguntas:
        numeros = [r.numero for r in buscar(p["pergunta"], k=max(KS))]
        posicoes = [i for i, n in enumerate(numeros, start=1) if n in p["artigos"]]
        primeira = posicoes[0] if posicoes else None
        for k in KS:
            acertos[k] += primeira is not None and primeira <= k
        soma_rr += 1 / primeira if primeira else 0.0
        if primeira is None:
            erros.append({"id": p["id"], "pergunta": p["pergunta"], "esperado": p["artigos"], "veio": numeros})
    n = len(perguntas)
    return {
        "metodo": metodo if metodo == "bm25" else f"{metodo} · {buscador.modelo.split('/')[-1]}",
        "granularidade": buscador.granularidade,
        **{f"acerto@{k}": round(acertos[k] / n, 3) for k in KS},
        "mrr": round(soma_rr / n, 3),
        "perguntas": n,
        "erros": erros,
    }


def main() -> None:
    perguntas = [p for p in map(json.loads, PERGUNTAS.open(encoding="utf8")) if not p["fora_do_escopo"]]
    resultados = [avaliar(Buscador(), "bm25", perguntas)]
    for modelo in MODELOS_EMBEDDING:
        buscador = Buscador(modelo=modelo)
        resultados += [avaliar(buscador, m, perguntas) for m in ("denso", "hibrido")]
    # a granularidade por trecho foi testada e perdeu (ver README); fica registrada aqui
    resultados.append(avaliar(Buscador(granularidade="trecho"), "denso", perguntas))

    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "busca.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2))
    print(f"{'método':<40}" + "".join(f"{f'acerto@{k}':>11}" for k in KS) + f"{'MRR':>8}")
    for r in resultados:
        nome = f"{r['metodo']} ({r['granularidade']})"
        print(f"{nome:<40}" + "".join(f"{r[f'acerto@{k}']:>11.3f}" for k in KS) + f"{r['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
