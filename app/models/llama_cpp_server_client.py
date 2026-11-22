"""Cliente para o servidor llama.cpp (llama-server.exe).

Gerencia o ciclo de vida do processo ``llama-server.exe`` (iniciar/parar) e se
comunica com ele via HTTP usando a API compatível com OpenAI
(``/v1/chat/completions``, ``/v1/models``).

O servidor roda localmente (127.0.0.1) e não faz chamadas externas. O modelo
GGUF ja esta presente em C:\\Users\\Usuário\\llama.cpp\\models\\, entao nao ha
download de modelo.

Quando a biblioteca ``llama-cpp-python`` nao esta instalada (sem wheel para
Python 3.15 neste ambiente), este cliente e a alternativa viavel: usa o
executavel ``llama-server.exe`` ja compilado em C:\\Users\\Usuário\\llama.cpp\\.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import httpx

logger = logging.getLogger("llama_cpp_server")

# Caminho padrão da instalação local do llama.cpp.
DEFAULT_LLAMA_CPP_DIR = Path(
    os.environ.get("LLAMA_CPP_DIR", r"C:\Users\Usuário\llama.cpp")
)
DEFAULT_SERVER_EXE = DEFAULT_LLAMA_CPP_DIR / "llama-server.exe"
DEFAULT_MODEL_PATH = (
    DEFAULT_LLAMA_CPP_DIR / "models" / "Qwen_Qwen3.5-9B-IQ4_XS.gguf"
)
DEFAULT_PORT = int(os.environ.get("LLAMA_CPP_PORT", "8899"))
DEFAULT_HOST = os.environ.get("LLAMA_CPP_HOST", "127.0.0.1")
DEFAULT_N_CTX = int(os.environ.get("LLAMA_CPP_N_CTX", "4096"))
DEFAULT_N_GPU_LAYERS = int(os.environ.get("LLAMA_CPP_N_GPU_LAYERS", "33"))


class LlamaCppServerClient:
    """Wrapper sobre o llama-server.exe gerenciado como subprocesso local.

    O cliente inicia o servidor sob demanda, aguarda ficar saudável e faz
    streaming de respostas via HTTP. Não confia na biblioteca Python
    ``llama-cpp-python`` (que pode não compilar neste ambiente).
    """

    def __init__(
        self,
        server_exe: Optional[str | Path] = None,
        model_path: Optional[str | Path] = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        n_ctx: int = DEFAULT_N_CTX,
        n_gpu_layers: int = DEFAULT_N_GPU_LAYERS,
    ):
        self.server_exe = Path(server_exe or DEFAULT_SERVER_EXE)
        self.model_path = Path(model_path or DEFAULT_MODEL_PATH)
        self.host = host
        self.port = port
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self._proc: Optional[subprocess.Popen] = None
        self._base_url = f"http://{host}:{port}"
        self._available = False
        self._init_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def base_url(self) -> str:
        return self._base_url

    def status(self) -> dict:
        return {
            "available": self.available,
            "engine": "llama.cpp-server",
            "server_exe": str(self.server_exe),
            "server_exe_exists": self.server_exe.is_file(),
            "model_path": str(self.model_path),
            "model_exists": self.model_path.is_file(),
            "host": self.host,
            "port": self.port,
            "n_ctx": self.n_ctx,
            "n_gpu_layers": self.n_gpu_layers,
            "error": self._init_error,
            "base_url": self._base_url,
        }

    # ------------------------------------------------------------------
    # Process lifecycle
    # ------------------------------------------------------------------

    def is_alive(self) -> bool:
        """Verifica se o servidor já está respondendo na porta."""
        try:
            r = httpx.get(f"{self._base_url}/v1/models", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def start(self, wait_seconds: int = 120) -> bool:
        """Inicia o llama-server.exe se ainda não estiver vivo.

        Aguarda até ``wait_seconds`` segundos pelo servidor ficar saudável.
        Retorna True se o servidor estiver disponível ao final.
        """
        if self.is_alive():
            self._available = True
            self._init_error = None
            logger.info("llama-server já está rodando em %s", self._base_url)
            return True

        if not self.server_exe.is_file():
            self._init_error = f"llama-server.exe não encontrado: {self.server_exe}"
            logger.error(self._init_error)
            return False

        if not self.model_path.is_file():
            self._init_error = f"Modelo GGUF não encontrado: {self.model_path}"
            logger.error(self._init_error)
            return False

        args = [
            str(self.server_exe),
            "-m", str(self.model_path),
            "--host", self.host,
            "--port", str(self.port),
            "--ctx-size", str(self.n_ctx),
            "-ngl", str(self.n_gpu_layers),
        ]
        logger.info("Iniciando llama-server: %s", " ".join(args))

        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:
            self._init_error = f"Falha ao iniciar llama-server: {exc}"
            logger.error(self._init_error)
            return False

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self._proc.poll() is not None:
                # Processo encerrou antes de ficar saudável.
                self._init_error = (
                    f"llama-server encerrou inesperadamente (código {self._proc.returncode})"
                )
                logger.error(self._init_error)
                self._proc = None
                return False
            if self.is_alive():
                self._available = True
                self._init_error = None
                logger.info(
                    "llama-server saudável em %s após %.1fs",
                    self._base_url,
                    time.time() - (deadline - wait_seconds),
                )
                return True
            time.sleep(1.0)

        self._init_error = (
            f"llama-server não ficou saudável em {wait_seconds}s em {self._base_url}"
        )
        logger.error(self._init_error)
        self.stop()
        return False

    def stop(self):
        """Para o servidor llama-server se foi iniciado por este cliente."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Erro ao parar llama-server: %s", exc)
            self._proc = None
        self._available = False

    # ------------------------------------------------------------------
    # HTTP API
    # ------------------------------------------------------------------

    async def list_models(self) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{self._base_url}/v1/models")
                if r.status_code == 200:
                    return r.json().get("data", [])
        except Exception as exc:  # pragma: no cover - network
            logger.debug("list_models falhou: %s", exc)
        return []

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        num_ctx: Optional[int] = None,
        max_tokens: int = 1024,
        tools: Optional[List[Dict]] = None,  # ignorado (sem tool calling nativo aqui)
        tool_calls_out: Optional[List[Dict]] = None,  # ignorado
    ) -> AsyncGenerator[str, None]:
        """Streaming de chat via llama-server (API OpenAI-compatível).

        O modelo Qwen3.5-9B usa um modo de "thinking". Para obter a resposta
        final, definimos ``max_tokens`` generosamente e usamos o campo
        ``content`` da mensagem (o reasoning_content pode conter o pensamento
        interno, mas não é exposto ao usuário).
        """
        if not self.available:
            raise RuntimeError(
                "llama.cpp-server não disponível. Inicie com start() primeiro. "
                f"({self._init_error or 'sem servidor'})"
            )

        # Constrói mensagens com system prompt no início.
        formatted: List[Dict[str, str]] = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)

        payload: Dict = {
            "model": model or str(self.model_path),
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if num_ctx:
            payload["num_ctx"] = num_ctx

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(600.0, connect=15.0)
        ) as client:
            async with client.stream(
                "POST", f"{self._base_url}/v1/chat/completions", json=payload
            ) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise RuntimeError(
                        f"llama-server error ({response.status_code}): "
                        f"{err_body.decode('utf-8', errors='ignore')}"
                    )
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            # Suporte a modelos de raciocínio (Qwen 3.5, DeepSeek, etc.):
                            # Quando o modelo está pensando, o texto vem em reasoning_content.
                            # A resposta final vem em content.
                            content = delta.get("content") or ""
                            reasoning = delta.get("reasoning_content") or ""
                            text_token = content or reasoning
                            if text_token:
                                yield text_token
                        except json.JSONDecodeError:
                            continue

    async def generate_embeddings(
        self, text: str, model: Optional[str] = None
    ) -> List[float]:
        """llama-server pode não expor embeddings; retorna lista vazia se não suportar."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{self._base_url}/v1/embeddings",
                    json={"model": model or str(self.model_path), "input": text},
                )
                if r.status_code == 200:
                    data = r.json()
                    embs = data.get("data", [])
                    if embs:
                        return embs[0].get("embedding", [])
        except Exception as exc:  # pragma: no cover - network
            logger.debug("embeddings não suportado pelo llama-server: %s", exc)
        return []


# Instância global (configurada via variáveis de ambiente se presentes).
llama_cpp_server = LlamaCppServerClient(
    server_exe=os.environ.get("LLAMA_CPP_SERVER_EXE"),
    model_path=os.environ.get("LLAMA_CPP_MODEL_PATH"),
    host=os.environ.get("LLAMA_CPP_HOST", DEFAULT_HOST),
    port=int(os.environ.get("LLAMA_CPP_PORT", str(DEFAULT_PORT))),
    n_ctx=int(os.environ.get("LLAMA_CPP_N_CTX", str(DEFAULT_N_CTX))),
    n_gpu_layers=int(os.environ.get("LLAMA_CPP_N_GPU_LAYERS", str(DEFAULT_N_GPU_LAYERS))),
)
