import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

# --- App Setup ---
app = FastAPI()

# Add CORS middleware for development (allows frontend to talk to backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Pydantic Models ---
# Model for a single message in the chat history
class Message(BaseModel):
    role: str
    content: str

# Model for the user's chat request
class ChatRequest(BaseModel):
    message: str

# --- API Endpoints ---

@app.get("/api/history", response_model=list[Message])
async def get_history():
    """
    Returns a mock chat history.
    In a real app, you'd fetch this from a database.
    """
    # Placeholder: Just return a welcome message
    return [
        {"role": "assistant", "content": "Hi! I'm a demo assistant. How can I help?"}
    ]

async def dummy_llm_responder(user_message: str):
    """
    This is your placeholder for the actual LLM logic.
    It now simulates sending "thought" messages before the final response.
    The protocol is:
    - [THOUGHT]Some thought...\n
    - [RESPONSE]The final streamed response...
    """
    # 1. Simulate thought process (memory retrieval, planning etc.)
    t1 = "[THOUGHT]The user is asking for a streaming protocol demo. I should first show some debug/memory output as a 'thought'.\n"
    t2 = f"[THOUGHT]User's message was: '{user_message}'. I'll formulate a response that acknowledges this.\n"
    
    t1t2 = t1 + t2
    # split after each whitespace to simulate streaming
    for chunk in t1t2.split(' '):
        yield chunk + ' '
        await asyncio.sleep(0.05) # Simulate network/compute delay

    # 2. Signal the start of the final answer
    yield "[RESPONSE]"

    # 3. Stream the final answer
    response_chunks = [
        "Okay, ", "this ", "is ", "the ", "final, ", "streamed ", "response. ",
        "As ", "you ", "can ", "see, ", "my ", "'thoughts' ", "were ",
        "displayed ", "first ", "in ", "a ", "different ", "style."
    ]

    for chunk in response_chunks:
        yield chunk
        await asyncio.sleep(0.05) # Simulate network/compute delay

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Receives a user message and returns a streaming response.
    """
    return StreamingResponse(
        dummy_llm_responder(request.message),
        media_type="text/plain"
    )

# --- Static File Serving ---
@app.get("/")
async def get_index():
    return FileResponse("index.html")

@app.get("/style.css")
async def get_css():
    return FileResponse("style.css", media_type="text/css")

# --- Run the App ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

