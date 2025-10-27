import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import pathlib

from dma.pipeline import Pipeline, PipelineUpdate, PipelineStatus
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
            
    def convert_pipeline_update(self, update: PipelineUpdate)->str:
        """
        Handle updates from the pipeline during response generation.
        This is a placeholder for future implementation.
        """
        return ""
    
    async def consume_and_send_updates(self, queue: asyncio.Queue, main_task: asyncio.Future):
        """
        Asynchronously consumes updates from the queue, sends them to a server,
        and stops once the main_task completes.
        """
        
        # 1. Wrap the concurrent.futures.Future in an awaitable Task
        main_task_awaitable = asyncio.ensure_future(main_task)

        
        print("Starting to monitor generation task and queue...")

        while True:
            try:
                # 2. Create a task to wait for the next queue item
                queue_get_task = asyncio.ensure_future(queue.get())

                # 3. Concurrently wait for either a queue item or the main task to finish
                done, pending = await asyncio.wait(
                    [queue_get_task, main_task_awaitable],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # --- A. Check Task Completion ---
                if main_task_awaitable in done:
                    # The main generation task has finished.
                    print("Generation task finished. Draining remaining queue items...")
                    
                    # Cancel the pending queue_get_task
                    if queue_get_task in pending:
                        queue_get_task.cancel()
                    
                    # Drain and process any remaining items the producer might have put
                    # just before finishing.
                    while not queue.empty():
                        update = queue.get_nowait()
                        result = self.convert_pipeline_update(update)
                        if result:
                            yield result
                        queue.task_done()
                    
                    # Check for and re-raise any exception from the main task
                    if main_task_awaitable.exception():
                        raise main_task_awaitable.exception()
                        
                    break  # Exit the loop

                # --- B. Process Queue Update ---
                if queue_get_task in done:
                    # An update arrived
                    update = queue_get_task.result()
                    queue.task_done()
                    
                    # ASYNCHRONOUSLY send the update to the server
                    result = self.convert_pipeline_update(update)
                    if result:
                        yield result
                    
                    # Continue the loop to wait for the next update or task completion
                
            except asyncio.CancelledError:
                # Handle cancellation if the consumer itself is cancelled
                print("Consumption task cancelled.")
                raise
            
        # return main task message
        response = main_task_awaitable.result()
        yield response.message_text
            
    async def generate_response(self, chat_request: ChatRequest):
        # for nowm only allow one response at a time
        # we can handle this better later
        if self._generating_response:
            yield "Error: Already generating a response. Please wait."
            return
        
        self._generating_response = True
        try:
            # create a new queue for updates
            queue = asyncio.Queue()
            self.conversation.add_message(chat_request.to_message())
            
            # run generate in executor to avoid blocking
            loop = asyncio.get_event_loop()
            main_future = loop.run_in_executor(None, self.pipeline.generate, self.conversation, lambda update: queue.put_nowait(update))
            main_task = asyncio.ensure_future(main_future)
            
            async for update in self.consume_and_send_updates(queue, main_task):
                yield update
                
            response = await main_task
            
            
            if response is None:
                yield "[RESPONSE]Error: No response generated."
                return
            
            thought_text = response.reasoning_text or ""
            if thought_text:
                yield f"[THOUGHTS]{thought_text}"
            content = response.message_text or ""
            if content:
                yield f"[RESPONSE]{content}"
                self.conversation.add_message(response)
            else:
                yield "[RESPONSE]Error: Empty response."
            
            
            
        finally:
            self._generating_response = False
            

    async def yield_word_by_word_wrapper(self, inner_generator, word_delay=0.1):
        """
        Wraps an async generator to yield its output word by word with a delay.
        """
        async for text in inner_generator:
            for chunk in text.split(' '):
                yield chunk + ' '
                await asyncio.sleep(word_delay)

    async def chat(self,request: ChatRequest):
        """
        Receives a user message and returns a streaming response.
        """
        return StreamingResponse(
            self.yield_word_by_word_wrapper(self.generate_response(request), word_delay=0.05),
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
    

