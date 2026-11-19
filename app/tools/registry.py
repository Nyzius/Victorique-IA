import inspect
from typing import Dict, Any, Callable
from app.security.permissions import ActionCategory, security_manager
from app.tools.file_tools import (
    list_directory, read_file, search_files, write_file, create_directory, delete_file
)
from app.tools.system_tools import calculate, get_system_info
from app.tools.web_search import search_web


class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        category: ActionCategory,
        func: Callable,
        risk_description: str = ""
    ):
        self.name = name
        self.description = description
        self.category = category
        self.func = func
        self.risk_description = risk_description


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, tool: ToolDefinition):
        self.tools[tool.name] = tool

    def _register_default_tools(self):
        # Category 1: Free (still limited to the authorized directories)
        self.register(ToolDefinition(
            name="list_directory",
            description="Lista arquivos e pastas em um diretório autorizado.",
            category=ActionCategory.FREE,
            func=list_directory
        ))
        self.register(ToolDefinition(
            name="read_file",
            description="Lê o conteúdo em texto de um arquivo autorizado.",
            category=ActionCategory.FREE,
            func=read_file
        ))
        self.register(ToolDefinition(
            name="search_files",
            description="Busca arquivos por nome ou padrão nos diretórios autorizados.",
            category=ActionCategory.FREE,
            func=search_files
        ))
        self.register(ToolDefinition(
            name="calculate",
            description="Executa cálculos matemáticos seguros.",
            category=ActionCategory.FREE,
            func=calculate
        ))
        self.register(ToolDefinition(
            name="get_system_info",
            description="Obtém informações do sistema operacional e armazenamento.",
            category=ActionCategory.FREE,
            func=get_system_info
        ))

        # Category 2: Requires explicit user authorization
        self.register(ToolDefinition(
            name="write_file",
            description="Cria ou sobrescreve um arquivo em diretório autorizado.",
            category=ActionCategory.REQUIRES_AUTH,
            func=write_file,
            risk_description="Esta ação irá criar ou modificar um arquivo no seu computador."
        ))
        self.register(ToolDefinition(
            name="create_directory",
            description="Cria uma nova pasta em diretório autorizado.",
            category=ActionCategory.REQUIRES_AUTH,
            func=create_directory,
            risk_description="Esta ação criará um novo diretório no sistema."
        ))
        self.register(ToolDefinition(
            name="delete_file",
            description="Remove um arquivo (ou pasta vazia) em diretório autorizado.",
            category=ActionCategory.REQUIRES_AUTH,
            func=delete_file,
            risk_description="ATENÇÃO: Esta ação excluirá permanentemente o arquivo ou pasta especificado."
        ))

        # Category 3: External (Internet)
        self.register(ToolDefinition(
            name="search_web",
            description="Realiza pesquisa de informações na internet.",
            category=ActionCategory.EXTERNAL,
            func=search_web,
            risk_description="Esta ação conectará à internet para buscar informações externas."
        ))

    @staticmethod
    def _resource_target(params: Dict[str, Any]) -> str:
        for key in ("path", "query", "expression"):
            if params.get(key) is not None:
                return str(params.get(key))
        return "local"

    async def _run_tool(self, tool: ToolDefinition, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes an already-authorized/free tool. Internal use only."""
        resource_target = self._resource_target(params)
        try:
            if inspect.iscoroutinefunction(tool.func):
                result = await tool.func(**params)
            else:
                result = tool.func(**params)

            security_manager.log_action(
                action_type=tool.name,
                category=tool.category,
                resource=resource_target,
                authorized=True,
                details="Executed successfully"
            )
            return {"status": "success", "result": result}
        except Exception as e:
            security_manager.log_action(
                action_type=tool.name,
                category=tool.category,
                resource=resource_target,
                authorized=True,
                details=f"Execution error: {str(e)}"
            )
            return {"status": "error", "error": str(e)}

    async def execute_tool(
        self,
        name: str,
        params: Dict[str, Any],
        authorized: bool = False
    ) -> Dict[str, Any]:
        """
        Public entry point used by the HTTP API.

        `authorized` is accepted only for backward compatibility and is NEVER
        trusted: protected and external tools always create a pending
        authorization request, resolved server-side by the user.
        """
        tool = self.tools.get(name)
        if not tool:
            return {"error": f"Ferramenta desconhecida: '{name}'", "status": "error"}
        if not isinstance(params, dict):
            return {"error": "Parâmetros inválidos: esperado um objeto JSON.", "status": "error"}

        resource_target = self._resource_target(params)

        if tool.category in (ActionCategory.REQUIRES_AUTH, ActionCategory.EXTERNAL):
            action_id = security_manager.create_authorization_request(
                action_type=tool.name,
                category=tool.category,
                resource=resource_target,
                description=tool.risk_description,
                payload=params
            )
            return {
                "status": "requires_authorization",
                "action_id": action_id,
                "tool_name": tool.name,
                "category": tool.category.value,
                "resource": resource_target,
                "description": tool.risk_description,
                "parameters": params
            }

        return await self._run_tool(tool, params)

    async def execute_approved_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a pending action previously approved by the user.
        Only called by the authorization endpoint with the server-stored payload.
        """
        tool = self.tools.get(action.get("action_type"))
        if not tool:
            return {"status": "error", "error": "Ferramenta da autorização não existe mais."}
        if tool.category == ActionCategory.FREE:
            return {"status": "error", "error": "Ação livre não deveria exigir autorização."}

        # Re-validate the target immediately before executing.
        params = action.get("payload", {})
        return await self._run_tool(tool, params)

    def get_tool_schemas_for_prompt(self) -> str:
        """Formats tools description for model instruction."""
        lines = [
            "FERRAMENTAS DISPONÍVEIS (o modelo NÃO executa ferramentas sozinho; "
            "o usuário precisa aprovar ações protegidas):"
        ]
        for t in self.tools.values():
            req = "(Requer autorização explícita do usuário)" if t.category != ActionCategory.FREE else "(Acesso livre, limitado aos diretórios autorizados)"
            lines.append(f"- `{t.name}`: {t.description} {req}")
        return "\n".join(lines)


tool_registry = ToolRegistry()
