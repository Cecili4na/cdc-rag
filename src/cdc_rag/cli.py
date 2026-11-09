"""Linha de comando.

    cdc perguntar "Comprei online e me arrependi, posso devolver?"
    cdc buscar "meu nome no Serasa"
    cdc avaliar-busca
    cdc avaliar-respostas
"""

import argparse

from cdc_rag import avaliar_busca, avaliar_respostas
from cdc_rag.busca import Buscador


def main() -> None:
    parser = argparse.ArgumentParser(prog="cdc")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("perguntar").add_argument("pergunta")
    sub.add_parser("buscar").add_argument("pergunta")
    sub.add_parser("avaliar-busca")
    sub.add_parser("avaliar-respostas")
    args = parser.parse_args()

    if args.comando == "buscar":
        buscador = Buscador()
        for r in buscador.denso(args.pergunta):
            print(f"art. {r.numero:<6} {r.pontuacao:.3f}  {buscador.artigo(r.id)['texto'][:90]}")
    elif args.comando == "perguntar":
        from cdc_rag.llm import do_ambiente
        from cdc_rag.resposta import responder

        r = responder(args.pergunta, Buscador(), do_ambiente())
        if r.aceita:
            print(r.texto)
        else:
            print("Não consegui uma resposta com citações confiáveis. Artigos mais próximos:")
            print(", ".join(f"art. {n}" for n in r.recuperados))
    elif args.comando == "avaliar-busca":
        avaliar_busca.main()
    else:
        avaliar_respostas.main()


if __name__ == "__main__":
    main()
