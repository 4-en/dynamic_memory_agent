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
class ChatMessage(BaseModel):
    role: str # "USER" | "ASSISTANT"
    content: str
    
    def from_message(msg: Message) -> "ChatMessage":
        return ChatMessage(role=msg.role.value, content=msg.message_text)

# Model for the user's chat request
class ChatRequest(BaseModel):
    message: str
    
    def to_message(self) -> Message:
        return Message(role=Role.USER, content=self.message)

class DMAWebUI:
    def __init__(self):
        # --- App Setup ---
        
        script_dir = pathlib.Path(__file__).parent.resolve()
        static_dir = script_dir / "static"
        self.static_dir = static_dir
        
        print("Loading pipeline...")
        self.pipeline = Pipeline()
        print("Pipeline loaded.")
        self.conversation = Conversation()
        self._generating_response = False
        
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

        self.app.get("/api/history", response_model=list[ChatMessage])(self.get_history)
        self.app.post("/api/chat")(self.chat)
        self.app.get("/", response_class=FileResponse)(self.get_index)

    async def get_history(self):
        """
        Returns the chat history as a list of ChatMessage objects.
        """
        
        return [
            ChatMessage.from_message(msg) for msg in self.conversation.messages if msg.role in [Role.USER, Role.ASSISTANT]
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
            
    async def generate_response(self, chat_request: ChatRequest):
        # for nowm only allow one response at a time
        # we can handle this better later
        if self._generating_response:
            yield "Error: Already generating a response. Please wait."
            return
        
        self._generating_response = True
        try:
            self.conversation.add_message(chat_request.to_message())
            response = self.pipeline.generate(self.conversation)
            if response is None:
                yield "Error: No response generated."
                return
            self.conversation.add_message(response)
            all_responses = []
            thought_text = response.reasoning_text or ""
            if thought_text:
                all_responses.append(f"[THOUGHT]{thought_text}\n")
            all_responses.append(f"[RESPONSE]{response.message_text}")
            full_response = "\n".join(all_responses)
            # stream the response word by word
            for chunk in full_response.split(' '):
                yield chunk + ' '
                await asyncio.sleep(0.05) # Simulate network/compute delay
        finally:
            self._generating_response = False
            


    async def chat(self,request: ChatRequest):
        """
        Receives a user message and returns a streaming response.
        """
        return StreamingResponse(
            self.generate_response(request),
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
    

