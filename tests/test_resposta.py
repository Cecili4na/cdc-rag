from cdc_rag.busca import Resultado
from cdc_rag.resposta import FORA, citacoes, conferir, responder


class ModeloRoteirizado:
    """Devolve respostas prontas, na ordem, e guarda as mensagens que recebeu."""

    nome = "roteiro"

    def __init__(self, *respostas: str):
        self.respostas = list(respostas)
        self.mensagens: list[str] = []

    def completar(self, sistema: str, mensagem: str) -> str:
        self.mensagens.append(mensagem)
        return self.respostas.pop(0)


class BuscadorFixo:
    def __init__(self, numeros: list[str]):
        self.numeros = numeros

    def denso(self, pergunta, k=5):
        return [Resultado(f"art{n}", n, 1.0) for n in self.numeros[:k]]

    def artigo(self, id_):
        return {"numero": id_.removeprefix("art"), "texto": f"Texto do {id_}"}


def test_extrai_citacoes_simples_e_compostas():
    assert citacoes("Pode devolver [art. 49]. Veja também [arts. 18 e 54-A].") == ["49", "18", "54-A"]


def test_citacao_repetida_conta_uma_vez():
    assert citacoes("[art. 49] ... [art. 49]") == ["49"]


def test_recusa_resposta_sem_citacao():
    assert conferir("Pode devolver em 7 dias.", ["49"]) == ["a resposta não cita nenhum artigo"]


def test_recusa_citacao_de_artigo_nao_fornecido():
    assert conferir("Pode devolver [art. 51].", ["49", "18"]) == ["cita artigos que não foram fornecidos: 51"]


def test_fora_do_escopo_dispensa_citacao():
    assert conferir(FORA, ["49"]) == []


def test_segunda_tentativa_corrige_citacao_inventada():
    modelo = ModeloRoteirizado("Pode devolver [art. 99].", "Pode devolver em 7 dias [art. 49].")
    r = responder("Posso devolver?", BuscadorFixo(["49", "18"]), modelo)
    assert r.aceita and r.tentativas == 2 and r.citados == ["49"]
    assert "cita artigos que não foram fornecidos: 99" in modelo.mensagens[1]


def test_resposta_recusada_duas_vezes_nao_e_aceita():
    modelo = ModeloRoteirizado("Sem citação.", "Ainda sem citação.")
    r = responder("Posso devolver?", BuscadorFixo(["49"]), modelo)
    assert not r.aceita and r.problemas == ["a resposta não cita nenhum artigo"]
