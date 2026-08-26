import sys
from app.agent import answer_question

def main():
    # Force stdout and stderr to use UTF-8 to prevent UnicodeEncodeError on Windows terminals
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 60)
    print("      Aster & Row Customer Support Agent (CLI)")
    print("=" * 60)
    print("Ask about policies (returns, shipping, warranty) or look up order status.")
    
    session_messages = []
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Goodbye!")
            break
            
        if not user_input:
            continue
            
        if user_input.lower() in ["quit", "exit"]:
            print("Session ended. Goodbye!")
            break
            
        session_messages.append({"role": "user", "content": user_input})
        
        if len(session_messages) == 1:
            print("Assistant: (Thinking...)", end="\r")
            
        try:
            result = answer_question(session_messages)
        except Exception as e:
            print(f"\nAssistant error: {e}")
            continue
            
        # Clear thinking line
        print(" " * 30, end="\r")
        
        session_messages.append({"role": "assistant", "content": result["answer"]})
        
        print(f"Assistant: {result['answer']}")
        if result.get("sources"):
            print(f"Citations: {', '.join(result['sources'])}")
        if result.get("handoff"):
            print("\n>>> [Human Assistance Recommended]")
            
        print("-" * 60)

if __name__ == "__main__":
    main()
