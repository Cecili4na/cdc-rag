"""Gera a resposta a partir dos artigos encontrados e confere as citações antes de devolver.

Regras dadas ao modelo:
1. Responder só com base nos artigos fornecidos.
2. Citar cada afirmação no formato [art. 49].
3. Se os artigos não respondem a pergunta, dizer exatamente FORA_DO_CDC.

Regras conferidas no código (o modelo pode não obedecer, então não se confia nele):
- toda citação tem que ser de um artigo que foi de fato entregue ao modelo;
- uma resposta sem nenhuma citação, que não seja FORA_DO_CDC, é recusada.

Se a resposta falha na conferência, o modelo recebe o motivo e tem uma segunda chance.
Se falhar de novo, o sistema não devolve a resposta: devolve os artigos encontrados.
"""

import re
from dataclasses import dataclass, field

from cdc_rag.busca import Buscador
from cdc_rag.llm import Modelo

FORA = "FORA_DO_CDC"
CITACAO = re.compile(r"\[\s*arts?\.\s*([^\]]+)\]", re.IGNORECASE)
# dentro de um colchete, cada artigo vem separado por vírgula ou "e"; o que não começa com número
# ("§ 1º", "III", "parágrafo único") é parágrafo ou inciso do artigo anterior, não outro artigo
PECAS = re.compile(r",|\be\b")
NUMERO = re.compile(r"(\d+(?:\s*-\s*[A-Z])?)(?:\s*[º°ª])?(?!\d)")  # "art. 6º" é o artigo 6

SISTEMA = f"""Você responde dúvidas de consumidores brasileiros sobre o Código de Defesa do Consumidor.

Regras:
- Use apenas os artigos fornecidos na mensagem. Não use conhecimento de fora deles.
- Cite cada afirmação com o número do artigo entre colchetes, assim: [art. 49] ou [art. 54-A].
- Responda em português simples, em no máximo 5 frases, falando diretamente com a pessoa.
- Se os artigos fornecidos não respondem a pergunta, responda apenas: {FORA}"""


@dataclass
class Resposta:
    texto: str
    citados: list[str]
    recuperados: list[str]
    aceita: bool
    tentativas: int
    problemas: list[str] = field(default_factory=list)

    @property
    def fora_do_escopo(self) -> bool:
        return self.texto.strip() == FORA


def citacoes(texto: str) -> list[str]:
    """'[art. 18]', '[arts. 49 e 54-A]' e '[art. 40, § 1º]' viram ['18', '49', '54-A', '40']."""
    numeros = []
    for grupo in CITACAO.findall(texto):
        for peca in PECAS.split(grupo):
            m = NUMERO.match(peca.strip())
            if m:
                numeros.append(re.sub(r"\s", "", m.group(1)))
    return list(dict.fromkeys(numeros))


def conferir(texto: str, recuperados: list[str]) -> list[str]:
    if texto.strip() == FORA:
        return []
    problemas = []
    citados = citacoes(texto)
    if not citados:
        problemas.append("a resposta não cita nenhum artigo")
    inventados = [n for n in citados if n not in recuperados]
    if inventados:
        problemas.append(f"cita artigos que não foram fornecidos: {', '.join(inventados)}")
    return problemas


def montar_contexto(buscador: Buscador, ids: list[str]) -> str:
    blocos = []
    for id_ in ids:
        a = buscador.artigo(id_)
        blocos.append(f"<artigo numero=\"{a['numero']}\">\n{a['texto']}\n</artigo>")
    return "\n\n".join(blocos)


def responder(pergunta: str, buscador: Buscador, modelo: Modelo, k: int = 5) -> Resposta:
    encontrados = buscador.denso(pergunta, k=k)
    recuperados = [r.numero for r in encontrados]
    mensagem = f"{montar_contexto(buscador, [r.id for r in encontrados])}\n\nPergunta: {pergunta}"

    texto = modelo.completar(SISTEMA, mensagem)
    problemas = conferir(texto, recuperados)
    tentativas = 1
    if problemas:
        tentativas = 2
        correcao = (
            f"{mensagem}\n\nSua resposta anterior foi recusada: {'; '.join(problemas)}. "
            f"Responda de novo seguindo as regras, citando só os artigos fornecidos."
        )
        texto = modelo.completar(SISTEMA, correcao)
        problemas = conferir(texto, recuperados)

    return Resposta(
        texto=texto.strip(),
        citados=citacoes(texto),
        recuperados=recuperados,
        aceita=not problemas,
        tentativas=tentativas,
        problemas=problemas,
    )
