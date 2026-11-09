from cdc_rag.busca import Resultado, fundir, normalizar
from cdc_rag.ingestao import extrair_artigos


def test_normalizar_tira_acento_e_palavras_vazias_mas_mantem_negacao():
    assert normalizar("Não recebi o cartão de crédito, já é tarde") == ["nao", "recebi", "cartao", "credito", "tarde"]


def test_rrf_premia_quem_aparece_bem_nas_duas_listas():
    bm25 = [Resultado("a", "1", 9), Resultado("b", "2", 8), Resultado("c", "3", 7)]
    denso = [Resultado("c", "3", 0.9), Resultado("b", "2", 0.8), Resultado("d", "4", 0.7)]
    # "b" é 2º nas duas; "a" e "c" são 1º numa e 3º ou ausente na outra
    assert [r.id for r in fundir([bm25, denso], k=2)] == ["c", "b"]


def test_extrai_artigo_com_letra_e_marca_vetado():
    texto = "\n".join([
        "TÍTULO I", "Dos Direitos", "CAPÍTULO I", "Disposições Gerais",
        "Art. 11. (Vetado).",
        "Art. 54-A. Este Capítulo dispõe sobre o superendividamento. (Incluído pela Lei nº 14.181, de 2021)",
        "§ 1º Entende-se por superendividamento a impossibilidade manifesta.",
        "Brasília, 11 de setembro de 1990",
    ])
    artigos = {a.numero: a for a in extrair_artigos(texto)}
    assert artigos["11"].vetado
    assert not artigos["54-A"].vetado
    assert "Incluído" not in artigos["54-A"].texto
    assert artigos["54-A"].alteracoes == ["(Incluído pela Lei nº 14.181, de 2021)"]
    assert artigos["54-A"].estrutura == ["TÍTULO I · Dos Direitos", "CAPÍTULO I · Disposições Gerais"]
