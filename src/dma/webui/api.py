import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import pathlib

from dma.pipeline import Pipeline
from dma.core import Conversation, Message, Role

# --- Pydantic Models ---
# Model for a single message in the chat history
class Message(BaseModel):
    role: str
    content: str

# Model for the user's chat request
class ChatRequest(BaseModel):
    message: str

class DMAWebUI:
    def __init__(self):
        # --- App Setup ---
        
        script_dir = pathlib.Path(__file__).parent.resolve()
        static_dir = script_dir / "static"
        self.static_dir = static_dir
        
        app = FastAPI()
        self.app = app
        
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        # Add CORS middleware for development (allows frontend to talk to backend)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allows all origins
            allow_credentials=True,
            allow_methods=["*"],  # Allows all methods
            allow_headers=["*"],  # Allows all headers
        )

        # --- Connect API Endpoints ---

        self.app.get("/api/history", response_model=list[Message])(self.get_history)
        self.app.post("/api/chat")(self.chat)
        self.app.get("/", response_class=FileResponse)(self.get_index)

    async def get_history(self):
        """
        Returns a mock chat history.
        In a real app, you'd fetch this from a database.
        """
        # Placeholder: Just return a welcome message
        return [
            {"role": "assistant", "content": "Hi! I'm a demo assistant. How can I help?"}
        ]

    async def dummy_llm_responder(self, user_message: str):
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


    async def chat(self,request: ChatRequest):
        """
        Receives a user message and returns a streaming response.
        """
        return StreamingResponse(
            self.dummy_llm_responder(request.message),
            media_type="text/plain"
        )

    # --- Static File Serving ---
    async def get_index(self):
        return FileResponse(self.static_dir / "index.html", media_type="text/html")

def launch_webui():
    """
    Launch the FastAPI web UI for the Dynamic Memory Agent.
    """
    import uvicorn
    app_instance = DMAWebUI()
    app = app_instance.app
    uvicorn.run(app, host="0.0.0.0", port=8000)

# --- Run the App ---
if __name__ == "__main__":
    launch_webui()
    

