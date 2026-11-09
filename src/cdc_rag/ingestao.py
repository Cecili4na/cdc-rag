"""Transforma o HTML do Planalto em uma lista de artigos.

Cada artigo vira um documento com o texto completo (caput, parágrafos e incisos) e o caminho
na estrutura da lei (título, capítulo, seção). O artigo é a unidade de busca porque é a unidade
de citação: uma resposta jurídica precisa dizer "art. 49", não "trecho 312".

As anotações de alteração ("Incluído pela Lei nº ...", "Redação dada pela ...") saem do texto
de busca, que fica mais limpo, mas são guardadas no campo `alteracoes`.
"""

import html
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
HTML = RAIZ / "data" / "raw" / "cdc.html"
SAIDA = RAIZ / "data" / "processed" / "artigos.jsonl"

INICIO_ARTIGO = re.compile(r"^Art\.\s*(\d+)\s*(?:º|°|o)?\s*(?:-\s*([A-Z]))?\s*\.?\s+", re.MULTILINE)
ANOTACAO = re.compile(r"\((?:Incluíd[oa]|Redação dada|Vide|Revogad[oa]|Vigência|Renumerad[oa])[^)]*\)", re.IGNORECASE)
CABECALHO = re.compile(r"^(TÍTULO|CAPÍTULO|SEÇÃO|Seção)\s+([IVXL]+(?:-[A-Z])?)\s*$")


@dataclass
class Artigo:
    numero: str  # "49", "54-A"
    texto: str
    vetado: bool = False
    estrutura: list[str] = field(default_factory=list)
    alteracoes: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"art{self.numero}"


def limpar_html(bruto: str) -> str:
    texto = re.sub(r"(?is)<(script|style).*?</\1>", "", bruto)
    texto = texto.replace("\r\n", " ").replace("\n", " ")  # quebras dentro do parágrafo são só do HTML
    texto = re.sub(r"(?i)</p>|<br\s*/?>|</h\d>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = html.unescape(texto).replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    return "\n".join(linha.strip() for linha in texto.splitlines() if linha.strip())


def juntar_cabecalhos(linhas: list[str]) -> list[str]:
    """No HTML, 'CAPÍTULO' e 'VI-A' às vezes caem em linhas separadas."""
    saida: list[str] = []
    for linha in linhas:
        if saida and saida[-1] in {"TÍTULO", "CAPÍTULO", "SEÇÃO", "Seção"}:
            saida[-1] = f"{saida[-1]} {linha}"
        else:
            saida.append(linha)
    return saida


def extrair_artigos(texto: str) -> list[Artigo]:
    corpo = texto[texto.index("TÍTULO I"):texto.rindex("Brasília,")]
    linhas = juntar_cabecalhos(corpo.splitlines())

    artigos: list[Artigo] = []
    estrutura: dict[str, str] = {}
    esperando_nome: str | None = None

    for linha in linhas:
        cab = CABECALHO.match(linha)
        if cab:
            nivel = "TÍTULO" if cab.group(1) == "TÍTULO" else "CAPÍTULO" if cab.group(1) == "CAPÍTULO" else "SEÇÃO"
            estrutura[nivel] = linha
            # um título novo zera capítulo e seção; um capítulo novo zera a seção
            for abaixo in {"TÍTULO": ["CAPÍTULO", "SEÇÃO"], "CAPÍTULO": ["SEÇÃO"], "SEÇÃO": []}[nivel]:
                estrutura.pop(abaixo, None)
            esperando_nome = nivel
            continue
        if esperando_nome and not INICIO_ARTIGO.match(linha) and not ANOTACAO.fullmatch(linha):
            estrutura[esperando_nome] += f" · {linha}"
            esperando_nome = None
            continue
        esperando_nome = None

        inicio = INICIO_ARTIGO.match(linha)
        if inicio:
            numero = inicio.group(1) + (f"-{inicio.group(2)}" if inicio.group(2) else "")
            artigos.append(Artigo(numero=numero, texto="", estrutura=[
                estrutura[n] for n in ("TÍTULO", "CAPÍTULO", "SEÇÃO") if n in estrutura
            ]))
        if artigos:
            artigos[-1].texto += ("\n" if artigos[-1].texto else "") + linha

    # o mesmo número pode aparecer duas vezes quando o Planalto mantém a redação antiga
    unicos: dict[str, Artigo] = {}
    for art in artigos:
        unicos[art.numero] = art
    for art in unicos.values():
        # anotações podem atravessar linhas, então saem só com o artigo inteiro montado
        art.alteracoes = [" ".join(a.split()) for a in ANOTACAO.findall(art.texto)]
        linhas = (linha.strip() for linha in ANOTACAO.sub("", art.texto).splitlines())
        art.texto = "\n".join(linha for linha in linhas if linha)
        # artigo vetado inteiro fica só com "Art. 9° (Vetado)": não tem o que buscar nele
        art.vetado = bool(re.fullmatch(r"Art\.[^.]*?\.?\s*\(Vetado\)\.?", art.texto.strip(), re.IGNORECASE))
    return list(unicos.values())


def main() -> None:
    texto = limpar_html(HTML.read_bytes().decode("cp1252"))
    artigos = extrair_artigos(texto)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", encoding="utf8") as f:
        for art in artigos:
            f.write(json.dumps({"id": art.id, **asdict(art)}, ensure_ascii=False) + "\n")
    print(f"{len(artigos)} artigos · {sum(a.vetado for a in artigos)} vetados por inteiro")


if __name__ == "__main__":
    main()
