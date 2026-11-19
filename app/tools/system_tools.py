import ast
import operator
import platform
import shutil
from typing import Dict, Any

# Safe math operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

MAX_ABS_VALUE = 10 ** 12
MAX_EXPONENT = 1000


def _check_number(value):
    if isinstance(value, bool):
        raise TypeError("Booleanos não são permitidos em cálculos.")
    if isinstance(value, complex):
        raise TypeError("Números complexos não são suportados.")
    if abs(value) > MAX_ABS_VALUE:
        raise ValueError(f"Valor acima do limite permitido ({MAX_ABS_VALUE}).")
    return value


def _eval_expr(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return _check_number(node.value)
        raise TypeError(f"Tipo não suportado: {type(node.value)}")
    elif isinstance(node, ast.BinOp):
        left = _eval_expr(node.left)
        right = _eval_expr(node.right)
        op_type = type(node.op)
        if op_type not in OPERATORS:
            raise TypeError(f"Operador não suportado: {op_type}")
        if op_type is ast.Pow:
            if not isinstance(right, (int, float)) or abs(right) > MAX_EXPONENT:
                raise ValueError(f"Expoente limitado a {MAX_EXPONENT}.")
        result = OPERATORS[op_type](left, right)
        return _check_number(result)
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_expr(node.operand)
        op_type = type(node.op)
        if op_type in OPERATORS:
            return _check_number(OPERATORS[op_type](operand))
        raise TypeError(f"Operador unário não suportado: {op_type}")
    else:
        raise TypeError(f"Expressão inválida: {type(node)}")


def calculate(expression: str) -> Dict[str, Any]:
    """Safely evaluates mathematical expressions without eval()."""
    if not isinstance(expression, str) or len(expression) > 500:
        return {"expression": expression, "error": "Expressão inválida ou longa demais.", "status": "error"}
    try:
        parsed = ast.parse(expression.strip(), mode="eval")
        result = _eval_expr(parsed.body)
        return {"expression": expression, "result": result, "status": "success"}
    except Exception as e:
        return {"expression": expression, "error": str(e), "status": "error"}


def get_system_info() -> Dict[str, Any]:
    """Retrieves basic system state."""
    total, used, free = shutil.disk_usage("C:\\")
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "disk_c": {
            "total_gb": round(total / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2)
        }
    }
