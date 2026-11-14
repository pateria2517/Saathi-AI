"""Saathi MCP server (stdio, JSON-RPC 2.0, newline-delimited, MCP protocol 2024-11-05).

Tools:
1. search_policy: Search the reviewed PF/ESIC FAQ knowledge base (710 canonical records, en/hi/kn/ta). [Read-Only]
2. explain_payslip: Generate line-by-line earnings and deductions breakdown with plain-language explanations. [Read-Only]
3. check_payslip_anomalies: Audit payslip against statutory EPFO/ESIC rules and passbook due date. [Read-Only]
4. get_pf_howto: Step-by-step procedures for passbook, UAN, claims, and transfers (honest about no public balance API). [Read-Only]
5. get_worker_payroll_record: Look up MOCK HRMS/payroll record for warehouse workers (Lakshmi). [Read-Only]
6. get_ticket_status: Check status of an existing HR ticket by ID. [Read-Only]
7. create_hr_ticket: Submit an HR follow-up ticket (ONLY with explicit worker consent). [State-Modifying]

Can be run via stdio (`python saathi_mcp.py`) or called directly in-process via `execute_mcp_tool()`.
"""
from __future__ import annotations

import datetime
import io
import json
import math
import os
import re
import sqlite3
import sys
import unicodedata
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
FAQ_JSON = os.path.join(HERE, "Saathi_AI_combined_710_faq_1.json")
DB_PATH = os.path.join(HERE, "saathi_demo.sqlite3")

# Ensure SQLite tickets table exists
with sqlite3.connect(DB_PATH) as _c:
    _c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        title TEXT,
        description TEXT,
        question TEXT,
        category TEXT,
        faq_id TEXT,
        language TEXT,
        status TEXT,
        source TEXT,
        created_at TEXT,
        updated_at TEXT,
        external_id TEXT
    )""")
    _c.commit()


# ==============================================================================
# CANONICAL KNOWLEDGE BASE & RETRIEVAL
# ==============================================================================

def _load_faq() -> List[Dict[str, Any]]:
    if os.path.exists(FAQ_JSON):
        with open(FAQ_JSON, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("records", data) if isinstance(data, dict) else data
    try:
        from config import settings
        with open(settings.knowledge_path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("records", data) if isinstance(data, dict) else data
    except Exception:
        return []

_KB = None

def _get_kb():
    global _KB
    if _KB is None:
        try:
            from main import KB
            _KB = KB
        except Exception:
            from retrieval import KnowledgeBase
            from config import settings
            records = _load_faq()
            _KB = KnowledgeBase(records, settings.database_path)
    return _KB


# ==============================================================================
# TOOL IMPLEMENTATIONS
# ==============================================================================

def tool_search_policy(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search the reviewed PF/ESIC knowledge base (710 canonical FAQs)."""
    query = str(args.get("query", "")).strip()
    language = str(args.get("language", "en")).lower()
    k = int(args.get("k", 3))
    
    if not query:
        return {"matches": [], "understood": False, "query": query}
        
    kb = _get_kb()
    topic = None
    try:
        from main import topic_from
        topic = topic_from(query)
    except Exception:
        pass
    
    res = kb.retrieve(query, topic=topic)
    
    out = []
    if res and res.record:
        seen = set()
        candidate_ids = [res.record.get("id")] + [m.get("id") for m in res.matches if m.get("id") != res.record.get("id")]
        for r_id in candidate_ids:
            if not r_id or r_id in seen:
                continue
            seen.add(r_id)
            rec = next((r for r in kb.records if r.get("id") == r_id), None)
            if not rec:
                continue
            answers = rec.get("answers", {})
            ans = answers.get(language) or answers.get("en", "")
            match_meta = next((m for m in res.matches if m.get("id") == r_id), None)
            score = float(res.score) if r_id == res.record.get("id") else float(match_meta.get("score", 0.5) if match_meta else 0.5)
            out.append({
                "id": rec["id"],
                "score": round(score, 3),
                "category": rec.get("category"),
                "intent": rec.get("intent"),
                "question_en": rec.get("question_en"),
                "answer": ans,
                "answer_en": answers.get("en", ""),
                "source_group": rec.get("source_name", "Statutory EPFO/ESIC Master FAQ"),
                "human_escalation_recommended": rec.get("human_escalation_recommended", False),
                "authenticated_data_required": rec.get("authenticated_data_required", False)
            })
            if len(out) >= k:
                break
                
    understood = bool(out) and (res.score >= 0.35)
    return {"matches": out, "understood": understood, "query": query, "language": language}


def tool_explain_payslip(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate line-by-line earnings and deductions breakdown with plain-language Indic explanations."""
    from payslip_analyzer import PayslipInput, analyze_payslip
    data = PayslipInput(
        worker_name=args.get("worker_name", "Employee"),
        basic_wage=float(args.get("basic_wage", 0.0)),
        dearness_allowance=float(args.get("dearness_allowance", 0.0)),
        retaining_allowance=float(args.get("retaining_allowance", 0.0)),
        other_allowances=float(args.get("other_allowances", 0.0)),
        gross_salary=float(args.get("gross_salary", 0.0)),
        employee_pf_deducted=float(args.get("employee_pf_deducted", 0.0)),
        employer_pf_contribution=float(args.get("employer_pf_contribution")) if args.get("employer_pf_contribution") is not None else None,
        employee_esic_deducted=float(args.get("employee_esic_deducted")) if args.get("employee_esic_deducted") is not None else None,
        employer_esic_contribution=float(args.get("employer_esic_contribution")) if args.get("employer_esic_contribution") is not None else None,
        language=args.get("language", "kn")
    )
    res = analyze_payslip(data)
    return {
        "pf_wage": res.pf_wage,
        "gross_salary": res.gross_salary,
        "net_take_home": res.net_take_home,
        "take_home_pay": res.take_home_pay,
        "total_deductions": res.total_deductions,
        "employer_contributions": res.employer_contributions,
        "breakdown": [b.model_dump() if hasattr(b, "model_dump") else b.dict() for b in res.breakdown],
        "summary": res.summary_message,
        "language": res.language
    }


def tool_check_payslip_anomalies(args: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic statutory rules audit (EPFO & ESIC due dates, wage ceilings, and employer matches)."""
    from payslip_analyzer import PayslipInput, analyze_payslip
    data = PayslipInput(
        worker_name=args.get("worker_name", "Employee"),
        wage_month=args.get("wage_month"),
        as_of_date=args.get("as_of_date"),
        basic_wage=float(args.get("basic_wage", 0.0)),
        dearness_allowance=float(args.get("dearness_allowance", 0.0)),
        retaining_allowance=float(args.get("retaining_allowance", 0.0)),
        other_allowances=float(args.get("other_allowances", 0.0)),
        gross_salary=float(args.get("gross_salary", 0.0)),
        employee_pf_deducted=float(args.get("employee_pf_deducted", 0.0)),
        employer_pf_contribution=float(args.get("employer_pf_contribution")) if args.get("employer_pf_contribution") is not None else None,
        employee_esic_deducted=float(args.get("employee_esic_deducted")) if args.get("employee_esic_deducted") is not None else None,
        employer_esic_contribution=float(args.get("employer_esic_contribution")) if args.get("employer_esic_contribution") is not None else None,
        passbook_deposit_credit=float(args.get("passbook_deposit_credit")) if args.get("passbook_deposit_credit") is not None else None,
        previous_month_pf_deducted=float(args.get("previous_month_pf_deducted")) if args.get("previous_month_pf_deducted") is not None else None,
        was_covered_at_start_of_period=bool(args.get("was_covered_at_start_of_period", False)),
        language=args.get("language", "kn")
    )
    res = analyze_payslip(data)
    return {
        "has_anomalies": res.has_anomalies,
        "anomalies": [a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in res.anomalies],
        "informational_notes": [n.model_dump() if hasattr(n, "model_dump") else n.dict() for n in res.informational_notes],
        "ticket_draft": (res.ticket_draft.model_dump() if hasattr(res.ticket_draft, "model_dump") else res.ticket_draft.dict()) if res.ticket_draft else None,
        "summary": res.summary_message
    }


def tool_get_pf_howto(args: Dict[str, Any]) -> Dict[str, Any]:
    """Official step-by-step guidance for EPFO self-service procedures."""
    topic = str(args.get("topic", "passbook")).lower().strip()
    language = str(args.get("language", "kn")).lower()
    
    # Official disclaimer: EPFO has no public balance API
    official_disclaimer = (
        "IMPORTANT NOTICE: EPFO does not provide any public or external API for checking member balances. "
        "Neither Saathi AI nor any third-party app can directly access your EPF account without your active credentials. "
        "You must access your balance through official channels (EPFO portal, UMANG, SMS, or Missed Call)."
    )
    
    procedures = {
        "passbook": {
            "title": "How to Check EPF Passbook Balance",
            "channels": [
                {
                    "channel": "Missed Call (Free & Instant)",
                    "steps": "Give a missed call to 9966044425 from your UAN-registered mobile. You will receive an SMS with current balance and last contribution."
                },
                {
                    "channel": "SMS Service",
                    "steps": "Send SMS 'EPFOHO UAN' to 7738299899 from your registered mobile number. For Kannada add 'KAN', for Hindi add 'HIN', for Tamil add 'TAM'."
                },
                {
                    "channel": "UMANG Mobile App",
                    "steps": "Open the UMANG App > Select EPFO > Click 'View Passbook' > Enter UAN and submit OTP."
                },
                {
                    "channel": "Official Member Portal",
                    "url": "https://passbook.epfindia.gov.in/MemberPassBook/Login",
                    "steps": "Login with UAN and password. You can view monthly ledger entries of employee and employer shares."
                }
            ]
        },
        "uan_activation": {
            "title": "How to Activate UAN for the First Time",
            "url": "https://unifiedportal-mem.epfindia.gov.in/memberinterface/",
            "steps": [
                "1. Obtain your 12-digit UAN from your warehouse contractor, supervisor, or payslip.",
                "2. Visit the EPFO Member Interface and click 'Activate UAN'.",
                "3. Enter UAN, Member ID, Aadhaar number, Name, Date of Birth, and Mobile Number.",
                "4. Authorize via OTP sent to your Aadhaar-linked mobile.",
                "5. Your password will be sent via SMS. Use it to log in and set a permanent password."
            ]
        },
        "claim_withdrawal": {
            "title": "How to File an Online PF Claim / Advance",
            "url": "https://unifiedportal-mem.epfindia.gov.in/memberinterface/",
            "steps": [
                "1. Log in to Member Portal with UAN and password.",
                "2. Ensure KYC is verified (Aadhaar, PAN, Bank Account linked and verified).",
                "3. Go to 'Online Services' > 'Claim (Form-31, 19, 10C & 10D)'.",
                "4. Verify bank account number by entering the last 4 digits.",
                "5. Select the claim type (Form 31 for illness/housing advance, Form 19 for full settlement after leaving service).",
                "6. Upload scanned copy of cheque/passbook and authenticate via Aadhaar OTP."
            ]
        },
        "transfer": {
            "title": "How to Transfer PF from Previous Job",
            "url": "https://unifiedportal-mem.epfindia.gov.in/memberinterface/",
            "steps": [
                "1. Both old and new Member IDs must be linked to the same active UAN.",
                "2. Go to 'Online Services' > 'One Member - One EPF Account (Transfer Request)'.",
                "3. Verify personal details and current establishment Member ID.",
                "4. Choose previous or present employer for attestation.",
                "5. Authenticate with Aadhaar OTP to submit the transfer claim."
            ]
        }
    }
    
    proc = procedures.get(topic, procedures["passbook"])
    return {
        "topic": topic,
        "title": proc["title"],
        "official_disclaimer": official_disclaimer,
        "procedure_details": proc,
        "language": language
    }


def tool_get_worker_payroll_record(args: Dict[str, Any]) -> Dict[str, Any]:
    """Look up MOCK HRMS/payroll database record for warehouse staff (Demonstration Persona)."""
    worker_id = str(args.get("worker_id", "EMP-LAKSHMI-001")).upper().strip()
    
    # MOCK HRMS Record for Lakshmi
    mock_records = {
        "EMP-LAKSHMI-001": {
            "worker_id": "EMP-LAKSHMI-001",
            "worker_name": "Lakshmi",
            "designation": "Warehouse Packer",
            "establishment": "QuickLogix Warehousing Pvt Ltd (Contract Hub)",
            "uan": "101234567890",
            "esic_ip_number": "5312345678",
            "basic_wage": 11500.0,
            "gross_salary": 14200.0,
            "current_month": "October 2026",
            "payroll_pf_deducted": 1380.0,
            "payroll_esic_deducted": 106.50,
            "epfo_passbook_posted_credit": 0.0,
            "remittance_status": "Deposit Not Received / Under Inquiry",
            "supervisor_name": "Ramesh (Shift Lead)",
            "notes": "MOCK payroll data for TLM university course demonstration only."
        }
    }
    
    # Allow lookup by name 'Lakshmi'
    if "LAKSHMI" in worker_id:
        record = mock_records["EMP-LAKSHMI-001"]
    else:
        record = mock_records.get(worker_id)
        
    if not record:
        return {
            "found": False,
            "message": f"Worker record '{worker_id}' not found in MOCK payroll database.",
            "available_mock_workers": ["EMP-LAKSHMI-001 (Lakshmi - Packer)"]
        }
        
    return {
        "found": True,
        "record": record,
        "privacy_notice": "Demonstration only. No real employee PII is stored."
    }


def tool_get_ticket_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Check status of an existing HR ticket by ID."""
    ticket_id = str(args.get("ticket_id", "")).strip()
    if not ticket_id:
        return {"error": "ticket_id is required"}
        
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute(
            "SELECT id, title, description, category, language, status, created_at, updated_at "
            "FROM tickets WHERE id=?", (ticket_id,)
        ).fetchone()
        
    if not row:
        return {"found": False, "ticket_id": ticket_id, "message": "Ticket ID not found."}
        
    return {
        "found": True,
        "ticket": {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "category": row[3],
            "language": row[4],
            "status": row[5],
            "created_at": row[6],
            "updated_at": row[7]
        }
    }


def tool_create_hr_ticket(args: Dict[str, Any]) -> Dict[str, Any]:
    """Submit an HR ticket. STRICT REQUIREMENT: Requires explicit worker consent."""
    consent_given = bool(args.get("consent_given", False))
    if not consent_given:
        return {
            "error": "CONSENT_REQUIRED",
            "message": "Explicit employee permission is required before filing an HR ticket. Set consent_given=True after obtaining consent.",
            "ticket_created": False
        }
        
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ticket_id = "SAT-" + datetime.datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8].upper()
    title = str(args.get("title", "PF/ESIC Grievance")).strip()
    description = str(args.get("description", "Discrepancy reported by worker")).strip()
    category = str(args.get("category", "PF / EPFO")).strip()
    language = str(args.get("language", "kn")).strip()
    source = str(args.get("source", "mcp_tool")).strip()
    
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT INTO tickets (id, title, description, question, category, faq_id, language, status, source, created_at, updated_at, external_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, title, description, title, category, "", language, "Open", source, now_iso, now_iso, "MCP-LOCAL")
        )
        c.commit()
        
    return {
        "ticket_created": True,
        "ticket": {
            "id": ticket_id,
            "title": title,
            "description": description,
            "category": category,
            "status": "Open",
            "created_at": now_iso,
            "delivery": "local_demo_sqlite"
        },
        "message": "HR ticket successfully created with worker consent."
    }


# ==============================================================================
# TOOL SCHEMAS & REGISTRY
# ==============================================================================

TOOLS = [
    {
        "name": "search_policy",
        "description": "Search the reviewed PF/ESIC statutory knowledge base (710 canonical FAQs in English, Hindi, Kannada, Tamil).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or keyword"},
                "language": {"type": "string", "enum": ["en", "hi", "kn", "ta"], "description": "Response language"},
                "k": {"type": "integer", "description": "Number of top results", "default": 3}
            },
            "required": ["query"]
        }
    },
    {
        "name": "explain_payslip",
        "description": "Generate a line-by-line earnings and deductions breakdown with plain-language Indic explanations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "basic_wage": {"type": "number", "description": "Basic wage in INR"},
                "gross_salary": {"type": "number", "description": "Gross salary in INR"},
                "employee_pf_deducted": {"type": "number", "description": "PF deducted in INR"},
                "employer_pf_contribution": {"type": "number", "description": "Employer PF contribution in INR"},
                "employee_esic_deducted": {"type": "number", "description": "ESIC deducted in INR"},
                "employer_esic_contribution": {"type": "number", "description": "Employer ESIC contribution in INR"},
                "language": {"type": "string", "enum": ["en", "hi", "kn", "ta"], "default": "kn"}
            },
            "required": ["basic_wage", "gross_salary", "employee_pf_deducted"]
        }
    },
    {
        "name": "check_payslip_anomalies",
        "description": "Audit payslip against statutory EPFO/ESIC rules, contribution period continuity, and remittance due dates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "basic_wage": {"type": "number", "description": "Basic wage in INR"},
                "gross_salary": {"type": "number", "description": "Gross salary in INR"},
                "employee_pf_deducted": {"type": "number", "description": "PF deducted in INR"},
                "passbook_deposit_credit": {"type": "number", "description": "Actual EPFO passbook deposit credit in INR"},
                "wage_month": {"type": "string", "description": "Wage month (YYYY-MM)"},
                "as_of_date": {"type": "string", "description": "Evaluation date (YYYY-MM-DD)"},
                "was_covered_at_start_of_period": {"type": "boolean", "description": "Whether worker was covered at start of 6-mo ESIC period"},
                "employer_pf_contribution": {"type": "number", "description": "Employer PF in INR"},
                "employee_esic_deducted": {"type": "number", "description": "ESIC deducted in INR"},
                "employer_esic_contribution": {"type": "number", "description": "Employer ESIC in INR"},
                "previous_month_pf_deducted": {"type": "number", "description": "Previous month PF in INR"},
                "language": {"type": "string", "enum": ["en", "hi", "kn", "ta"], "default": "kn"}
            },
            "required": ["basic_wage", "gross_salary", "employee_pf_deducted"]
        }
    },
    {
        "name": "get_pf_howto",
        "description": "Step-by-step procedures for passbook, UAN activation, claims, and transfers. Honest about no public balance API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "enum": ["passbook", "uan_activation", "claim_withdrawal", "transfer"], "description": "Procedure topic"},
                "language": {"type": "string", "enum": ["en", "hi", "kn", "ta"], "default": "kn"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "get_worker_payroll_record",
        "description": "Look up MOCK HRMS/payroll database record for warehouse workers (Lakshmi's record for course demo).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "worker_id": {"type": "string", "description": "Worker ID or name, e.g. EMP-LAKSHMI-001 or Lakshmi"}
            },
            "required": ["worker_id"]
        }
    },
    {
        "name": "get_ticket_status",
        "description": "Look up current status and details of an existing HR ticket by Ticket ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket ID (e.g. SAT-20261114-XXXXXX)"}
            },
            "required": ["ticket_id"]
        }
    },
    {
        "name": "create_hr_ticket",
        "description": "Create an HR follow-up ticket. Strictly requires explicit worker consent (consent_given=True).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short issue title"},
                "description": {"type": "string", "description": "Detailed explanation of discrepancy"},
                "category": {"type": "string", "description": "PF / EPFO or ESIC"},
                "language": {"type": "string", "enum": ["en", "hi", "kn", "ta"]},
                "consent_given": {"type": "boolean", "description": "Explicit authorization from the employee"}
            },
            "required": ["title", "description", "consent_given"]
        }
    }
]


def execute_mcp_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Direct dispatcher for MCP tools; can be called in-process or via JSON-RPC."""
    if name == "search_policy" or name == "search_faq":
        return tool_search_policy(args)
    elif name == "explain_payslip":
        return tool_explain_payslip(args)
    elif name == "check_payslip_anomalies":
        return tool_check_payslip_anomalies(args)
    elif name == "get_pf_howto":
        return tool_get_pf_howto(args)
    elif name == "get_worker_payroll_record":
        return tool_get_worker_payroll_record(args)
    elif name == "get_ticket_status":
        return tool_get_ticket_status(args)
    elif name == "create_hr_ticket":
        return tool_create_hr_ticket(args)
    elif name == "list_hr_tickets":
        with sqlite3.connect(DB_PATH) as c:
            rows = c.execute("SELECT id, title, category, status, created_at FROM tickets ORDER BY created_at DESC").fetchall()
        return {"tickets": [{"id": r[0], "title": r[1], "category": r[2], "status": r[3], "created_at": r[4]} for r in rows]}
    else:
        raise ValueError(f"Unknown MCP tool '{name}'")


# ==============================================================================
# COMPATIBILITY CONVENIENCE FUNCTIONS
# ==============================================================================

def search_faq(query: str, language: str = "en", k: int = 3) -> Dict[str, Any]:
    """Compatibility wrapper for tool_search_policy."""
    return tool_search_policy({"query": query, "language": language, "k": k})

def create_hr_ticket(title: str, description: str, category: str = "PF / EPFO", language: str = "en", consent_given: bool = False) -> Dict[str, Any]:
    """Compatibility wrapper for tool_create_hr_ticket."""
    return tool_create_hr_ticket({"title": title, "description": description, "category": category, "language": language, "consent_given": consent_given})

def list_hr_tickets(limit: int = 10) -> Dict[str, Any]:
    """Compatibility wrapper for list_hr_tickets."""
    return execute_mcp_tool("list_hr_tickets", {"limit": limit})



# ==============================================================================
# STDIO JSON-RPC 2.0 PROTOCOL LOOP
# ==============================================================================

def reply(i: Any, result: Any = None, error: Any = None) -> None:
    m = {"jsonrpc": "2.0", "id": i}
    m["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        mid = msg.get("id")
        method = msg.get("method")
        if mid is None:
            continue
        try:
            if method == "initialize":
                reply(mid, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "saathi-mcp", "version": "2.0.0"}
                })
            elif method == "tools/list":
                reply(mid, {"tools": TOOLS})
            elif method == "tools/call":
                p = msg.get("params", {})
                res = execute_mcp_tool(p["name"], p.get("arguments") or {})
                reply(mid, {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            elif method == "ping":
                reply(mid, {})
            else:
                reply(mid, error={"code": -32601, "message": f"Method '{method}' not found"})
        except Exception as e:
            reply(mid, error={"code": -32000, "message": str(e)})


if __name__ == "__main__":
    main()
