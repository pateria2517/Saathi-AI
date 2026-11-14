"""Saathi AI — Model Context Protocol (MCP) Verification Suite (Step 4).

Verifies:
1. Tool Discovery: All 7 MCP tools registered with valid JSON Schemas.
2. Tool Execution (search_policy, explain_payslip, check_payslip_anomalies, get_pf_howto, get_worker_payroll_record, get_ticket_status).
3. State-Modifying Consent Gate: create_hr_ticket strictly enforces consent_given=True.
4. EPFO API Transparency: get_pf_howto honestly states EPFO has no public balance API.
5. End-to-End API Integration: /api/ask calls tools through MCP by default and logs tool calls.
6. Telephony Integration: Spoken turns route through MCP tools.
"""
from __future__ import annotations

import asyncio
import io
import json
import pytest
from fastapi.testclient import TestClient

from main import app
import saathi_mcp
from mcp_client import mcp_client

client = TestClient(app)


def test_mcp_tools_registry_and_schemas():
    """Verify all 7 tools are exposed with valid input schemas."""
    expected_tools = {
        "search_policy",
        "explain_payslip",
        "check_payslip_anomalies",
        "get_pf_howto",
        "get_worker_payroll_record",
        "get_ticket_status",
        "create_hr_ticket"
    }
    tool_names = {t["name"] for t in saathi_mcp.TOOLS}
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"
    
    # Check that create_hr_ticket requires consent_given
    create_tool = next(t for t in saathi_mcp.TOOLS if t["name"] == "create_hr_ticket")
    assert "consent_given" in create_tool["inputSchema"]["required"]


def test_mcp_search_policy():
    """Verify search_policy tool retrieves canonical FAQs."""
    res = asyncio.run(mcp_client.call_tool("search_policy", {"query": "what is PF?", "language": "en"}))
    assert not res.get("isError")
    sc = res.get("structuredContent") or {}
    assert sc.get("understood") is True
    matches = sc.get("matches", [])
    assert len(matches) > 0
    assert matches[0]["id"] == "SAH-001"
    assert ("PF" in matches[0]["answer"] or "EPF" in matches[0]["answer"])


def test_mcp_explain_payslip():
    """Verify explain_payslip tool provides line breakdown."""
    args = {
        "basic_wage": 11500.0,
        "gross_salary": 14200.0,
        "employee_pf_deducted": 1380.0,
        "employee_esic_deducted": 106.50,
        "language": "kn"
    }
    res = asyncio.run(mcp_client.call_tool("explain_payslip", args))
    assert not res.get("isError")
    sc = res.get("structuredContent") or {}
    assert sc.get("pf_wage") == 11500.0
    assert sc.get("net_take_home") == 12713.50
    assert len(sc.get("breakdown", [])) >= 3


def test_mcp_check_payslip_anomalies_lakshmi_scenario():
    """Verify check_payslip_anomalies audits Lakshmi's missing passbook deposit."""
    args = {
        "basic_wage": 11500.0,
        "gross_salary": 14200.0,
        "employee_pf_deducted": 1380.0,
        "passbook_deposit_credit": 0.0,
        "wage_month": "2026-08",
        "as_of_date": "2026-10-01",  # Due date has passed
        "language": "kn"
    }
    res = asyncio.run(mcp_client.call_tool("check_payslip_anomalies", args))
    assert not res.get("isError")
    sc = res.get("structuredContent") or {}
    assert sc.get("has_anomalies") is True
    anomalies = sc.get("anomalies", [])
    assert any(a["code"] == "ANOMALY_PASSBOOK_MISSING_CREDIT" for a in anomalies)
    assert sc.get("ticket_draft") is not None


def test_mcp_get_pf_howto_honesty():
    """Verify get_pf_howto honestly notes that EPFO has no public balance API."""
    res = asyncio.run(mcp_client.call_tool("get_pf_howto", {"topic": "passbook", "language": "kn"}))
    assert not res.get("isError")
    sc = res.get("structuredContent") or {}
    disclaimer = sc.get("official_disclaimer", "")
    assert "public or external API" in disclaimer
    assert "9966044425" in str(sc.get("procedure_details", ""))
    assert "UMANG" in str(sc.get("procedure_details", ""))


def test_mcp_get_worker_payroll_record():
    """Verify get_worker_payroll_record retrieves MOCK HRMS data for Lakshmi."""
    res = asyncio.run(mcp_client.call_tool("get_worker_payroll_record", {"worker_id": "EMP-LAKSHMI-001"}))
    assert not res.get("isError")
    sc = res.get("structuredContent") or {}
    assert sc.get("found") is True
    record = sc.get("record", {})
    assert record.get("worker_name") == "Lakshmi"
    assert record.get("basic_wage") == 11500.0
    assert record.get("payroll_pf_deducted") == 1380.0
    assert record.get("epfo_passbook_posted_credit") == 0.0


def test_mcp_create_ticket_consent_enforcement():
    """Verify create_hr_ticket rejects when consent is not given, succeeds when given."""
    # 1. Without consent -> Must fail!
    args_no_consent = {
        "title": "Discrepancy test",
        "description": "Attempting ticket creation without consent",
        "consent_given": False
    }
    res_no = asyncio.run(mcp_client.call_tool("create_hr_ticket", args_no_consent))
    sc_no = res_no.get("structuredContent") or {}
    assert sc_no.get("ticket_created") is False
    assert sc_no.get("error") == "CONSENT_REQUIRED"

    # 2. With consent -> Must succeed!
    args_with_consent = {
        "title": "Lakshmi Passbook Missing Deposit",
        "description": "PF deducted on payslip but Rs 0 in passbook",
        "category": "PF / EPFO",
        "language": "kn",
        "consent_given": True
    }
    res_yes = asyncio.run(mcp_client.call_tool("create_hr_ticket", args_with_consent))
    sc_yes = res_yes.get("structuredContent") or {}
    assert sc_yes.get("ticket_created") is True
    ticket = sc_yes.get("ticket", {})
    assert ticket.get("id", "").startswith("SAT-")
    
    # 3. Look up status via get_ticket_status tool
    ticket_id = ticket["id"]
    status_res = asyncio.run(mcp_client.call_tool("get_ticket_status", {"ticket_id": ticket_id}))
    sc_stat = status_res.get("structuredContent") or {}
    assert sc_stat.get("found") is True
    assert sc_stat["ticket"]["id"] == ticket_id
    assert sc_stat["ticket"]["status"] == "Open"


def test_api_ask_calls_mcp_and_logs_tool_calls():
    """End-to-End Test: /api/ask executes tools via MCP by default and logs tool calls."""
    res = client.post("/api/ask", json={
        "question": "ನನ್ನ ಪಿಎಫ್ ಬ್ಯಾಲೆನ್ಸ್ ಹೇಗೆ ನೋಡುವುದು? ಲಕ್ಷ್ಮಿ ರೆಕಾರ್ಡ್ ಏನು?",
        "language": "kn"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["understood"] is True
    assert data.get("mcp_used") is True
    tool_calls = data.get("mcp_tool_calls", [])
    assert len(tool_calls) >= 1
    
    tools_called = [tc["tool"] for tc in tool_calls]
    assert "search_policy" in tools_called
    assert any(tc["status"] == "success" for tc in tool_calls)


def test_telephony_speech_turn_executes_mcp():
    """Verify telephony speech turn executes MCP tools."""
    res = client.post("/api/telephony/simulate", json={
        "action": "speech",
        "call_id": "CALL-MCP-TEST-001",
        "input": "ನನ್ನ ಪಿಎಫ್ ಬ್ಯಾಲೆನ್ಸ್ ಹೇಗೆ ನೋಡುವುದು?",
        "language": "kn"
    })
    assert res.status_code == 200
    data = res.json()
    resp_data = data.get("response", {})
    assert "ಬ್ಯಾಲೆನ್ಸ್" in resp_data.get("message", "") or "PF" in resp_data.get("message", "")
    assert len(resp_data.get("mcp_tool_calls", [])) >= 1
