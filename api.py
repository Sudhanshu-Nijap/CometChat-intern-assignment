from fastapi import FastAPI
from pydantic import BaseModel
from app.agent import answer_question
import uvicorn

app = FastAPI()

class QueryRequest(BaseModel):
    user_phone: str
    user_message: str

@app.post("/api/chat")
def chat_endpoint(request: QueryRequest):
    try:
        # Format it exactly as the backend expects (a list of session messages)
        session_messages = [{"role": "user", "content": request.user_message}]
        
        # Call the existing backend logic
        result = answer_question(session_messages)
        
        return {
            "status": "success",
            "reply": result["answer"]
        }
    except Exception as e:
        return {
            "status": "error",
            "reply": f"Sorry, there was an error processing your request: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
