"""Parse arithmetic with explicit rules; never execute input as Python code."""

import re
from dataclasses import dataclass
from decimal import Decimal, DecimalException, ROUND_HALF_EVEN, localcontext

MAX_EXPRESSION_LENGTH = 500
MAX_PARENTHESIS_DEPTH = 50
PRECISION = 28
NUMBER_PATTERN = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
SYMBOLS = str.maketrans({"×": "*", "÷": "/", "−": "-"})


class CalculationError(ValueError):
    """An input error that can safely be explained to a calculator user."""

    def __init__(self, message, code="INVALID_EXPRESSION", position=None):
        super().__init__(message)
        self.code = code
        self.position = position


@dataclass(frozen=True)
class Token:
    """A number, an operator, a parenthesis, or the end of the expression."""

    kind: str
    text: str
    position: int


def tokenize(expression):
    """Recognize only decimal numbers, arithmetic operators and parentheses."""
    if not isinstance(expression, str):
        raise CalculationError("expression 必须是字符串。", "INVALID_INPUT")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculationError(
            "表达式不能超过 500 个字符。", "EXPRESSION_TOO_LONG"
        )
    if not expression.strip():
        raise CalculationError("请输入表达式。", "EMPTY_EXPRESSION")

    expression = expression.translate(SYMBOLS)
    tokens = []
    position = 0
    while position < len(expression):
        character = expression[position]
        if character.isspace():
            position += 1
            continue
        number = NUMBER_PATTERN.match(expression, position)
        if number:
            tokens.append(Token("NUMBER", number.group(), position))
            position = number.end()
        elif character in "+-*/()":
            tokens.append(Token(character, character, position))
            position += 1
        else:
            raise CalculationError(
                f"第 {position + 1} 个字符不受支持：{character}。",
                position=position + 1,
            )

    tokens.append(Token("END", "", len(expression)))
    return tokens


class ExpressionParser:
    """Parse expression -> term -> unary -> primary in priority order."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.depth = 0

    @property
    def current(self):
        """Return the next token that has not yet been consumed."""
        return self.tokens[self.index]

    def parse(self):
        """Consume the complete expression, rejecting any trailing tokens."""
        result = self.expression()
        if self.current.kind != "END":
            raise CalculationError(
                "表达式中缺少运算符，或存在多余的右括号。",
                position=self.current.position + 1,
            )
        return result

    def expression(self):
        """Handle addition and subtraction after their terms are evaluated."""
        result = self.term()
        while self.current.kind in ("+", "-"):
            operator = self.current.kind
            self.index += 1
            right = self.term()
            result = result + right if operator == "+" else result - right
        return result

    def term(self):
        """Handle multiplication and division from left to right."""
        result = self.unary()
        while self.current.kind in ("*", "/"):
            operator = self.current
            self.index += 1
            right = self.unary()
            if operator.kind == "/" and right == 0:
                raise CalculationError(
                    "除数不能为 0。", "DIVISION_BY_ZERO",
                    position=operator.position + 1,
                )
            result = result * right if operator.kind == "*" else result / right
        return result

    def unary(self):
        """Handle signs such as -5, +2, 3*-2 and -(1+2)."""
        negative = False
        while self.current.kind in ("+", "-"):
            if self.current.kind == "-":
                negative = not negative
            self.index += 1
        result = self.primary()
        # copy_negate changes only the sign, without prematurely rounding.
        return result.copy_negate() if negative else result

    def primary(self):
        """Read a number or recursively evaluate a parenthesized expression."""
        token = self.current
        if token.kind == "NUMBER":
            self.index += 1
            return Decimal(token.text)
        if token.kind == "(":
            if self.depth >= MAX_PARENTHESIS_DEPTH:
                raise CalculationError(
                    "括号嵌套不能超过 50 层。", "EXPRESSION_TOO_DEEP",
                    position=token.position + 1,
                )
            self.depth += 1
            self.index += 1
            result = self.expression()
            if self.current.kind != ")":
                raise CalculationError(
                    "缺少与左括号匹配的右括号。",
                    position=token.position + 1,
                )
            self.index += 1
            self.depth -= 1
            return result
        raise CalculationError(
            "此处需要数字或左括号，请检查是否缺少操作数。",
            position=token.position + 1,
        )


def calculate_expression(expression):
    """Return a decimal string using 28 significant digits of precision."""
    tokens = tokenize(expression)
    try:
        with localcontext() as context:
            context.prec = PRECISION
            context.rounding = ROUND_HALF_EVEN
            result = +ExpressionParser(tokens).parse()
    except DecimalException as error:
        raise CalculationError(
            "数值超出可计算范围。", "NUMERIC_ERROR"
        ) from error

    if not result.is_finite():
        raise CalculationError("结果必须是有限数值。", "NUMERIC_ERROR")
    if result == 0:
        return "0"
    # Send a string so JSON/JavaScript do not convert it to a binary float.
    text = format(result, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
