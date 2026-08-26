# Aster & Row Support Agent - Unit Tests

import pytest
from app.agent import extract_cited_documents, should_escalate_to_human
from app.orders import get_order, normalize_order_id

def test_citation_extraction():
    """Verify that document citations with parenthesized headings are correctly extracted."""
    response = (
        "You have 30 calendar days to return standard items. "
        "Source: 01-returns-policy-current.md (Standard return window)"
    )
    citations = extract_cited_documents(response)
    assert citations == ["01-returns-policy-current.md (Standard return window)"]

def test_order_masking_cancelled():
    """Verify that cancelled orders mask estimated delivery and tracking fields."""
    order = get_order("ORD-1004")
    assert order["status"].lower() == "cancelled"
    assert order["estimated_delivery"] is None
    assert order["carrier"] is None
    assert order["tracking_number"] is None

def test_should_escalate_handoff():
    """Verify that critical safety queries or explicit handoff tags trigger human escalation."""
    # Test keyword trigger
    assert should_escalate_to_human("No info", None, current_user_query="My account was hacked and fraud occurred.") is True
    
    # Test tag trigger
    assert should_escalate_to_human("Connecting you now... [HANDOFF: TRUE]", None) is True
    
    # Test safe queries do not trigger handoff
    assert should_escalate_to_human("Here is the policy. [HANDOFF: FALSE]", None, current_user_query="What is the return policy?") is False
