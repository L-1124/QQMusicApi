---
name: python-standards
description: Apply Python tooling standards including uv package management, pytest testing, ruff/based-pyright code quality, one-line docstrings, and self-documenting code practices. Use this skill when working with Python backend code, managing dependencies, running tests, or ensuring code quality. Apply when installing packages, writing tests, formatting code, type checking, adding docstrings, organizing imports, or deciding whether to create new files vs. extending existing ones. Use for any Python development task requiring adherence to tooling standards and best practices.
---

# Python Standards

**Core Rule:** Use uv for all package operations, pytest for testing, ruff
for formatting/linting. Write self-documenting code with minimal comments.

## When to use this skill

* When installing or managing Python packages and dependencies
* When writing or running unit tests, integration tests, or test suites
* When formatting Python code or fixing linting issues
* When adding type hints or running type checking
* When writing function/method docstrings
* When organizing imports in Python files
* When deciding whether to create a new Python file or extend existing ones
* When setting up code quality checks (linting, formatting, type checking)
* When running coverage reports or analyzing test results
* When ensuring code follows Python best practices and tooling standards

This Skill provides Claude Code with specific guidance on how to adhere to
Python tooling standards and best practices for backend development.

## Package Management - uv Only

**MANDATORY: Use `uv` for all Python package operations. Never use `pip` directly.**

```bash
# Installing packages
uv pip install package-name
uv pip install -r requirements.txt

# Package information
uv pip list
uv pip show package-name

# Running Python scripts/modules
uv run python script.py
uv run pytest
```

**Why uv:** Faster dependency resolution, better lock file management, project
standard for consistency.

**If you catch yourself typing `pip`:** Stop and use `uv pip` instead.

## Testing with pytest

**Run tests using `uv run pytest`:**

```bash
uv run pytest                                      # All tests
uv run pytest -m unit                              # Unit tests only
uv run pytest -m integration                       # Integration tests only
uv run pytest tests/unit/test_module.py            # Specific file
uv run pytest tests/unit/test_module.py::test_name # Specific test
uv run pytest -v                                   # Verbose output
uv run pytest -s                                   # Show print statements
uv run pytest --cov=src --cov-report=term-missing  # Coverage report
uv run pytest --cov-fail-under=80                  # Enforce 80% coverage
```

**Test markers:** Use `@pytest.mark.unit` and `@pytest.mark.integration` to
categorize tests.

## Code Quality Tools

**Ruff (Linting & Formatting):**

```bash
ruff check .           # Check for issues
ruff check . --fix     # Auto-fix issues
ruff format .          # Format all code
```

**Type Checking:**

```bash # Strict type checking with basedpyright
basedpyright src            # Alternative type checker
```

## Code Style

### Docstrings

**Use concise one-line docstrings for most functions:**

```python
def calculate_discount(price: float, rate: float) -> float:
    """Calculate discounted price by applying rate."""
    return price * (1 - rate)
```

**Multi-line docstrings only for complex functions:**

```python
def process_payment(order_id: str, payment_method: str) -> PaymentResult:
    """
    Process payment for order using specified method.

    Validates payment method, charges customer, updates order status,
    and sends confirmation email. Rolls back on any failure.
    """
    # Implementation
```

**Don't document obvious behavior:**

```python
# BAD - docstring adds no value
def get_user_email(user_id: str) -> str:
    """Get the email address for a user by their ID."""

# GOOD - name is self-explanatory
def get_user_email(user_id: str) -> str:
    return db.query(User).filter_by(id=user_id).first().email
```

### Comments

**Write self-documenting code. Minimize inline comments.**

Use clear names instead of comments:

```python
# BAD - comment explains unclear code
# Check if user has permission
if u.r == 'admin' or u.r == 'moderator':

# GOOD - code explains itself
if user.is_admin() or user.is_moderator():
```

**Comment Style Guidelines:**

* Use **Chinese comments** (中文注释) for inline and block comments
* Use **English punctuation** (英文符号) in comments (periods, commas, etc.)
* Follow **Google-style docstring format** for function/class documentation

**Google Style Example:**

```python
def validate_user_credentials(username: str, password: str) -> bool:
    """验证用户凭据的有效性。

    Args:
        username: 用户名。
        password: 用户密码。

    Returns:
        如果凭据有效则返回 True，否则返回 False。

    Raises:
        ValueError: 如果用户名或密码为空。
    """
    # 检查输入参数的合法性。
    if not username or not password:
        raise ValueError("Username and password cannot be empty.")

    # 查询数据库中的用户记录。
    user = db.query(User).filter_by(username=username).first()
    return user and user.verify_password(password)
```

**Use comments only for:**

* Complex algorithms requiring explanation (复杂算法说明)
* Non-obvious business logic or domain rules (业务规则)
* Workarounds for external library bugs (include issue link)
* Performance optimizations that sacrifice clarity

### Import Organization

**Order:** Standard library → Third-party → Local application

```python
# Standard library
import os
from datetime import datetime

# Third-party
import pytest
from sqlalchemy import Column, Integer

# Local application
from app.models import User
from app.services import EmailService
```

**Ruff automatically organizes imports.** Run `ruff check . --fix` to sort.

## Type Hints

**Add type hints to all function signatures:**

```python
# Required
def process_order(order_id: str, user_id: int) -> Order:
    pass

# Not required for simple private methods
def _format_price(amount):
    return f"${amount:.2f}"
```

**Use modern type syntax (Python 3.10+):**

```python
# Good
def get_users(ids: list[int]) -> list[User]:
    pass

# Avoid (old style)
from typing import List
def get_users(ids: List[int]) -> List[User]:
    pass
```

## File Organization

**Prefer editing existing files over creating new ones.**

Before creating a new Python file, ask:

1. Can this fit in an existing module?
2. Is there a related file to extend?
3. Does this truly need to be separate?

**Benefits:** Reduces file sprawl, maintains coherent structure, easier navigation.

**When to create new files:**

* New model/entity with distinct responsibility
* New service layer for separate domain
* Test file for new module
* Clear architectural boundary

## Common Patterns

**Avoid bare `except`:**

```python
# BAD
try:
    process()
except:
    pass

# GOOD
try:
    process()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
```

**Use context managers for resources:**

```python
# GOOD
with open(file_path) as f:
    data = f.read()

# GOOD
with db.session() as session:
    user = session.query(User).first()
```

**Prefer pathlib over os.path:**

```python
# GOOD
from pathlib import Path
config_path = Path(__file__).parent / "config.yaml"

# Avoid
import os
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
```
