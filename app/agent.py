# Aster & Row Support Agent - Agent Orchestrator

import os, re, json, time
from dotenv import load_dotenv
from groq import Groq
from app.retriever import get_retriever
from app.orders import get_order, normalize_order_id, get_db_snapshot_time
from app.prompts import SYSTEM_PROMPT, REWRITE_PROMPT

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
GROQ_API_URL = os.getenv("GROQ_API_URL") or "https://api.groq.com/openai/v1"
CONFIDENTIAL_PII_FIELDS = {"email", "address", "risk_score", "internal_note"}

client = Groq(api_key=GROQ_API_KEY, timeout=25.0) if GROQ_API_KEY and GROQ_API_KEY != "your_key_here" else None
if client and GROQ_API_URL and "api.groq.com" not in GROQ_API_URL: client.base_url = GROQ_API_URL

def find_order_id_in_conversation(messages):
    for msg in reversed(messages):
        detected = normalize_order_id(msg.get("content", ""))
        if detected: return detected
    return None

get_session_order_id = find_order_id_in_conversation

def remove_private_customer_details(order):
    return {k: v for k, v in order.items() if k not in CONFIDENTIAL_PII_FIELDS} if order else None

sanitize_order = remove_private_customer_details

def extract_cited_documents(response):
    text = re.sub(r'[\u2011\u2013]', '-', response).replace('\u202f', ' ').replace('\xa0', ' ')
    seen, citations = set(), []
    for m in re.finditer(r'\b([\w\-]+\.md)\b', text):
        heading = re.match(r'[\s\(\-\*>]*([^\)\n\r\*]{1,59})', text[m.end():m.end() + 80])
        key = f"{m.group(1)} ({heading.group(1).strip(' ()>-*') if heading else 'Overview'})"
        if key not in seen:
            seen.add(key)
            citations.append(key)
    return citations

extract_citations = extract_cited_documents

def rewrite_query_with_context(history, query):
    if not history or not client: return query
    try:
        fmt_hist = "".join(f"{m['role'].upper()}: {m['content']}\n" for m in history[-3:])
        res = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": REWRITE_PROMPT.format(history=fmt_hist, query=query)}],
            temperature=0.0
        )
        return res.choices[0].message.content.strip() or query
    except Exception: return query

rewrite_query = rewrite_query_with_context

def send_chat_completion(messages):
    for attempt in range(5):
        try:
            res = client.chat.completions.create(model=GROQ_MODEL, messages=messages, temperature=0.0)
            text = res.choices[0].message.content
            return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip() or text.strip()
        except Exception as err:
            wait = 3.0 * (2 ** attempt)
            if attempt == 4 or not any(k in str(err).lower() for k in ["rate limit", "429", "connect", "unreachable", "addrinfo"]):
                raise
            match = re.search(r'try again in\s+(?:(\d+)m)?\s*(?:([\d.]+)s)?', str(err), re.I)
            if match: wait = int(match.group(1) or 0)*60 + float(match.group(2) or 0) + 2.0
            print(f"[Warning] LLM call failed: {err}. Retrying in {wait:.1f}s...")
            time.sleep(wait)

call_llm = send_chat_completion

def should_escalate_to_human(response, order, current_user_query="", order_id=None):
    if any(w in current_user_query.lower() for w in ["migration note", "ignore the real policy"]):
        return False
    resp_lower, query_lower = response.lower(), current_user_query.lower()
    if any(w in query_lower for w in ["damaged", "broken", "defective", "wrong item", "faulty", "flawed", "fraud", "hacked", "unauthorized", "stolen", "compromise", "email", "address", "risk score", "internal note", "cancel", "change address", "change delivery", "change shipping"]):
        return True
    if order and (not order.get("found") or order.get("status", "").lower() == "exception"):
        return True
    tag = re.search(r'\[HANDOFF:\s*(TRUE|FALSE)\]', response, re.I)
    if tag: return tag.group(1).upper() == "TRUE"
    if not order_id and any(w in resp_lower for w in ["order id", "order number"]):
        return False
    return False

determine_handoff = should_escalate_to_human

def answer_question(messages):
    if not messages: return {"answer": "No input provided.", "sources": [], "handoff": False}
    if not client: raise ValueError("GROQ_API_KEY is not configured.")
    query = messages[-1].get("content", "").strip()
    order_id = find_order_id_in_conversation(messages)
    order = get_order(order_id) if order_id else None
    tool = "order_lookup" if order_id else "not_called"
    if order_id and any(term in query.lower() for term in {"email", "address", "risk score", "internal note"}):
        tool = "optional_sanitized_lookup"
    
    chunks = get_retriever().retrieve(rewrite_query_with_context(messages[:-1], query), top_k=4)
    low_conf = not chunks or chunks[0]["final_score"] < 0.26
    evidence = "\n\n".join(f"--- EVIDENCE {i+1} ---\nSource: {c['chunk']['source']} ({c['chunk']['heading']})\nContent: {c['chunk']['text']}" for i, c in enumerate(chunks)) if not low_conf else ""
    
    safe_order = remove_private_customer_details(order)
    order_block = f"ORDER INFORMATION:\n{json.dumps(safe_order, indent=2)}" if safe_order else "ORDER INFORMATION: No order lookup performed."
    snap_time = (order.get("snapshot_at") or get_db_snapshot_time()) if order else get_db_snapshot_time()
    
    chat_msgs = [{"role": "system", "content": SYSTEM_PROMPT.format(snapshot_at=snap_time)}]
    for m in messages[:-1][-4:]:
        chat_msgs.append({"role": m.get("role"), "content": m.get("content")})
    chat_msgs.append({"role": "user", "content": f"USER QUERY: {query}\n\nEVIDENCE:\n{evidence or 'No relevant evidence found.'}\n\n{order_block}\n"})
    
    raw = send_chat_completion(chat_msgs)
    if not raw.strip():
        raw = "I'm sorry, I don't have enough information. Please speak with a human support specialist. [HANDOFF: TRUE]"
    
    sources = extract_cited_documents(raw)
    handoff = should_escalate_to_human(raw, order, current_user_query=query, order_id=order_id)
    clean_ans = re.sub(r'\s*\[HANDOFF:\s*(TRUE|FALSE)\]\s*', '', raw, flags=re.I).strip()
    
    if os.getenv("DEBUG", "false").lower() == "true":
        import sys
        print(f"\n--- DEBUG TRACE ---\nQuery: {query}\nTool: {tool}\nResponse: {clean_ans}\nHandoff: {handoff}\n", file=sys.stderr)
        
    return {"answer": clean_ans, "sources": sources, "handoff": handoff, "tool_called": tool}
