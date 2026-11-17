import pytest

from leanline.tools import Engine

DOC_A = """# Billing
## Retry policy
Failed payments are retried three times with exponential backoff.
## Refunds
Refunds are issued to the original payment method within five days.
"""

DOC_B = """# Onboarding
## Accounts
New employees receive an account on their first day.
"""


@pytest.fixture
def engine(tmp_path):
    return Engine(home=tmp_path / "home")


@pytest.fixture
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "billing.md").write_text(DOC_A, encoding="utf-8")
    (d / "onboarding.md").write_text(DOC_B, encoding="utf-8")
    return d
