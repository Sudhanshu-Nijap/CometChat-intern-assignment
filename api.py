from fastapi import FastAPI
from pydantic import BaseModel
from app.agent import answer_question
import uvicorn

app = FastAPI()

# Temporary in-memory dictionary to store conversation history by phone number
sessions = {}

import re
def format_for_whatsapp(text: str) -> str:
    # Convert standard markdown bold **text** to WhatsApp bold *text*
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    # Convert markdown headers # Header to WhatsApp bold *Header*
    text = re.sub(r'^#+\s*(.*?)$', r'*\1*', text, flags=re.MULTILINE)
    # Convert markdown links [text](url) to "text (url)"
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1 (\2)', text)
    return text

class QueryRequest(BaseModel):
    user_phone: str
    user_message: str

@app.post("/api/chat")
def chat_endpoint(request: QueryRequest):
    try:
        phone = request.user_phone
        
        # 1. Initialize empty history if this is a new user
        if phone not in sessions:
            sessions[phone] = []
            
        # 2. Append the new user message to their history
        sessions[phone].append({"role": "user", "content": request.user_message})
        
        # 3. Only keep the last 10 messages to prevent context window overload
        if len(sessions[phone]) > 10:
            sessions[phone] = sessions[phone][-10:]
            
        # 4. Call your existing backend logic with the full conversation history
        result = answer_question(sessions[phone])
        
        # 5. Append the AI's answer to the history so it remembers what it said
        sessions[phone].append({"role": "assistant", "content": result["answer"]})
        
        # 6. Format the reply specifically for WhatsApp
        whatsapp_reply = format_for_whatsapp(result["answer"])
        
        return {
            "status": "success",
            "reply": whatsapp_reply,
            "handoff": result.get("handoff", False)
        }
    except Exception as e:
        return {
            "status": "error",
            "reply": f"Sorry, there was an error processing your request: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
