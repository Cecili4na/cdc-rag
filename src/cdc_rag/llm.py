"""Acesso ao modelo de linguagem, com o provedor escolhido por variável de ambiente.

- ANTHROPIC_API_KEY definida: usa a API da Anthropic (Claude).
- LLM_BASE_URL definida: usa qualquer servidor compatível com a API da OpenAI
  (Ollama, vLLM, LM Studio), com o modelo em LLM_MODELO.

O resto do código só conhece a função `completar(sistema, mensagem) -> str`, então trocar de
provedor não muda nada fora daqui. Os testes usam um modelo falso com a mesma assinatura.
"""

import os
from typing import Protocol

import httpx


class Modelo(Protocol):
    nome: str

    def completar(self, sistema: str, mensagem: str) -> str: ...


class Anthropic:
    def __init__(self, modelo: str | None = None):
        import anthropic

        self.nome = modelo or os.environ.get("LLM_MODELO", "claude-haiku-5-5")
        self._cliente = anthropic.Anthropic()

    def completar(self, sistema: str, mensagem: str) -> str:
        r = self._cliente.messages.create(
            model=self.nome,
            max_tokens=800,
            temperature=0,
            system=sistema,
            messages=[{"role": "user", "content": mensagem}],
        )
        return "".join(b.text for b in r.content if b.type == "text")


class CompativelOpenAI:
    def __init__(self, base_url: str, modelo: str):
        self.nome = modelo
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._cabecalhos = {"Authorization": f"Bearer {os.environ.get('LLM_API_KEY', 'local')}"}

    def completar(self, sistema: str, mensagem: str) -> str:
        r = httpx.post(
            self._url,
            headers=self._cabecalhos,
            timeout=120,
            json={
                "model": self.nome,
                "temperature": 0,
                "max_tokens": 800,
                "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": mensagem}],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def do_ambiente() -> Modelo:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return Anthropic()
    if os.environ.get("LLM_BASE_URL"):
        return CompativelOpenAI(os.environ["LLM_BASE_URL"], os.environ.get("LLM_MODELO", "qwen2.5:7b-instruct"))
    raise RuntimeError(
        "Nenhum modelo configurado. Defina ANTHROPIC_API_KEY, ou LLM_BASE_URL e LLM_MODELO "
        "para um servidor compatível com a API da OpenAI."
    )
