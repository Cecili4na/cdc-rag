"""Roda o RAG completo nas perguntas de avaliação e mede o que dá para medir sem opinião humana.

Por pergunta dentro do escopo:
- aceita: passou na conferência de citações (na primeira ou na segunda tentativa).
- cita_artigo_certo: pelo menos um artigo do gabarito aparece nas citações.
- citacao_valida: todas as citações são de artigos entregues ao modelo (deve ser 100% nas aceitas).

Por pergunta fora do escopo:
- recusou: o modelo respondeu FORA_DO_CDC em vez de inventar.

Também conta quantas respostas precisaram da segunda tentativa: mostra quanto a conferência
está segurando o modelo.
"""

import json
from pathlib import Path

from cdc_rag.busca import Buscador
from cdc_rag.llm import do_ambiente
from cdc_rag.resposta import responder

RAIZ = Path(__file__).resolve().parents[2]
PERGUNTAS = RAIZ / "data" / "perguntas.jsonl"
RESULTADOS = RAIZ / "resultados"


def main() -> None:
    perguntas = list(map(json.loads, PERGUNTAS.open(encoding="utf8")))
    buscador, modelo = Buscador(), do_ambiente()
    linhas = []
    for p in perguntas:
        r = responder(p["pergunta"], buscador, modelo)
        linhas.append({
            **p,
            "resposta": r.texto,
            "citados": r.citados,
            "recuperados": r.recuperados,
            "aceita": r.aceita,
            "tentativas": r.tentativas,
            "fora": r.fora_do_escopo,
            "cita_artigo_certo": bool(set(r.citados) & set(p["artigos"])),
            "artigo_certo_recuperado": bool(set(r.recuperados) & set(p["artigos"])),
        })
        print(f"{p['id']} {'ok ' if r.aceita else 'REC'} {r.citados or r.texto[:30]}", flush=True)

    dentro = [x for x in linhas if not x["fora_do_escopo"]]
    fora = [x for x in linhas if x["fora_do_escopo"]]
    pode_citar = [x for x in dentro if x["artigo_certo_recuperado"]]
    resumo = {
        "modelo": modelo.nome,
        "perguntas_no_escopo": len(dentro),
        "aceitas": round(sum(x["aceita"] and not x["fora"] for x in dentro) / len(dentro), 3),
        "cita_artigo_certo": round(sum(x["cita_artigo_certo"] for x in dentro) / len(dentro), 3),
        # separa erro de busca de erro de geração: quando o artigo certo chegou, o modelo citou?
        "cita_artigo_certo_quando_recuperado": round(
            sum(x["cita_artigo_certo"] for x in pode_citar) / max(len(pode_citar), 1), 3
        ),
        "recusou_no_escopo": sum(x["fora"] for x in dentro),
        "fora_do_escopo_recusadas": f"{sum(x['fora'] for x in fora)}/{len(fora)}",
        "precisou_segunda_tentativa": sum(x["tentativas"] == 2 for x in linhas),
        "recusadas_pela_conferencia": sum(not x["aceita"] for x in linhas),
    }
    RESULTADOS.mkdir(exist_ok=True)
    nome = modelo.nome.replace("/", "_").replace(":", "_")
    (RESULTADOS / f"respostas_{nome}.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in linhas) + "\n"
    )
    (RESULTADOS / f"respostas_{nome}_resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2))
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
