import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import pathlib

from dma.pipeline import Pipeline, PipelineUpdate, PipelineStatus
from dma.core import Conversation, Message, Role, RetrievalStep, RetrievalQuery
import logging

logging.basicConfig(level=logging.DEBUG)

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
    
    async def _handle_pipeline_updates(self, queue: asyncio.Queue):
        """
        Asynchronously consumes updates from the queue, sends them to a server,
        and stops once the main_task completes.
        """
        

        
        print("Starting to monitor generation task and queue...")

        completed = False
        while not completed:
            try:
                # get PipelineUpdate from queue until status is COMPLETED or ERROR
                update: PipelineUpdate = await queue.get()
                if update.status in [PipelineStatus.COMPLETED, PipelineStatus.ERROR]:
                    completed = True
                
                print("Received pipeline update:", update.message)
                    
                match update.status:
                    case PipelineStatus.QUERY_UPDATE:
                        s = "[QUERY]Querying database...\n"
                        step: RetrievalStep = update.retrieval_step
                        if step is None or len(step.queries) == 0:
                            continue
                        for query in step.queries:
                            s += f" - {query.embedding_query.query_text}\n"
                        yield s
                    case PipelineStatus.RETRIEVAL_UPDATE:
                        s = "[RETRIEVAL]Retrieving information...\n"
                        step: RetrievalStep = update.retrieval_step
                        if step is None or len(step.results) == 0:
                            yield "[RETRIEVAL]No results found.\n"
                            continue
                        for result in step.results:
                            s += f" - {result.memory.memory}\n"
                        yield s
                    case _:
                        # for other statuses, we don't yield anything for now
                        continue
            except Exception as e:
                yield f"[ERROR]An error occurred while processing pipeline updates: {str(e)}"
                completed = True
        
                        
        
    def _handle_pipeline_response(self, response:Message)->str:
        """
        Process the final response from the pipeline.
        Currently a placeholder for future implementation.
        """
        if response is None:
            return "Error: No response generated."
        
        full_text = ""
        thought_text = response.reasoning_text or ""
        if thought_text:
            full_text += f"[THOUGHT]{thought_text}\n"
        content = response.message_text or ""
        if content:
            full_text += f"[RESPONSE]{content}\n"
            self.conversation.add_message(response)
        else:
            return "Error: Empty response."
        
        # add metadata info if available
        if response.source_ids:
            full_text += "\n**Sources:**\n"
            full_text += "\n".join(f" - {source_id}" for source_id in response.source_ids)

        return full_text
            
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
            
            async for update in self._handle_pipeline_updates(queue):
                print(update)
                yield update
                
            response = await main_task


            yield self._handle_pipeline_response(response)


        except Exception as e:
            yield f"[ERROR]An error occurred during response generation: {str(e)}"

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
    

