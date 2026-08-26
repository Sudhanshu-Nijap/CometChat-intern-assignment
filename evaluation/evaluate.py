import os, sys, json
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path: sys.path.append(project_root)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent import answer_question

CASES = [
    {
        "id": "cancellation-outside-30m",
        "message": "Can I cancel my order ORD-1002? I placed it about 45 minutes ago.",
        "must_include": ["30"],          # mentions 30-minute window
        "must_not_include": ["successfully cancelled"],
        "expect_tool": "order_lookup",
        "expect_handoff": True,
    },
    {
        "id": "cancellation-not-pending",
        "message": "Please cancel my order ORD-1007.",
        "must_include": ["cancel"],      # explains it cannot be cancelled
        "must_not_include": ["successfully cancelled", "refund issued"],
        "expect_tool": "order_lookup",
        "expect_handoff": True,
    },
    {
        "id": "final-sale-no-return",
        "message": "I bought a Ridge Daypack marked as FINAL SALE. I changed my mind. Can I return it?",
        "must_include": ["final"],  # references final sale policy
        "must_not_include": ["return approved", "refund"],
        "expect_tool": "not_called",
        "expect_handoff": None,          # don't assert handoff
    },
    {
        "id": "fraud-escalation",
        "message": "I noticed a charge on my card that I didn't authorize. My account might have been hacked!",
        "must_include": ["specialist"],  # escalates to human
        "must_not_include": [],
        "expect_tool": "not_called",
        "expect_handoff": True,
    },
    {
        "id": "weather-delay",
        "message": "Where is my order ORD-1005 and why is it delayed?",
        "must_include": ["weather"],     # mentions weather delay
        "must_not_include": ["coupon", "risk score"],
        "expect_tool": "order_lookup",
        "expect_handoff": False,
    },
]

def run_case(case):
    messages = [{"role": "user", "content": case["message"]}]
    res = answer_question(messages)
    ans = res.get("answer", "")
    tool = res.get("tool_called", "not_called")
    handoff = res.get("handoff", False)
    failures = []

    for term in case["must_include"]:
        if term.lower() not in ans.lower():
            failures.append(f"Missing: '{term}'")
    for term in case["must_not_include"]:
        if term.lower() in ans.lower():
            failures.append(f"Forbidden term found: '{term}'")
    if case["expect_tool"] and tool != case["expect_tool"]:
        failures.append(f"Tool: expected '{case['expect_tool']}', got '{tool}'")
    if case["expect_handoff"] is not None and handoff != case["expect_handoff"]:
        failures.append(f"Handoff: expected {case['expect_handoff']}, got {handoff}")

    return failures

def main():
    print("=" * 50)
    print("     Aster & Row - Custom Evaluation (5 cases)")
    print("=" * 50)
    failed = []
    for i, case in enumerate(CASES, 1):
        print(f"[{i}/5] {case['id']} ...", end=" ", flush=True)
        failures = run_case(case)
        if failures:
            print("FAILED")
            for f in failures:
                print(f"  - {f}")
            failed.append(case["id"])
        else:
            print("PASSED")
    print("-" * 50)
    if failed:
        print(f"FAILED: {len(failed)}/5 cases failed.")
        sys.exit(1)
    else:
        print("All 5 cases PASSED!")

if __name__ == "__main__":
    main()
