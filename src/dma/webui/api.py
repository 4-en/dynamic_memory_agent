import asyncio
from typing import AsyncGenerator, Generator
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import pathlib

from dma.pipeline import Pipeline, PipelineUpdate, PipelineStatus
from dma.core import Conversation, Message, Role, RetrievalStep, RetrievalQuery
import logging
import json



# --- Pydantic Models ---
# Model for a single message in the chat history
class ChatMessage(BaseModel):
    role: str # "USER" | "ASSISTANT"
    content: str
    
    def from_message(msg: Message) -> "ChatMessage":
        return ChatMessage(role=msg.role.value.lower(), content=msg.message_text or "")

# Model for the user's chat request
class ChatRequest(BaseModel):
    message: str
    
    def to_message(self) -> Message:
        return Message(role=Role.USER, content=self.message)
    
class StreamingResponseChunk(BaseModel):
    type: str # "THOUGHT" | "RESPONSE" | "QUERY" | "RETRIEVAL" | "ERROR"
    content: str
    status: str | None = None

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
            ChatMessage.from_message(msg) for msg in self.conversation.messages if msg.role in [Role.USER, Role.ASSISTANT] and msg.message_text
        ]

            
    def convert_pipeline_update(self, update: PipelineUpdate)->str:
        """
        Handle updates from the pipeline during response generation.
        This is a placeholder for future implementation.
        """
        return ""
    
    async def _handle_pipeline_updates(self, queue: asyncio.Queue)->AsyncGenerator[StreamingResponseChunk, None]:
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
                
                # print("Received pipeline update:", update.message)
                
                # format updates based on status as markdown strings
                match update.status:
                    case PipelineStatus.QUERY_UPDATE:
                        step: RetrievalStep = update.retrieval_step
                        if step is None or len(step.queries) == 0:
                            continue
                        
                        if step.clarification_needed:
                            yield StreamingResponseChunk(
                                type="query",
                                content="User clarification needed."
                            )
                            continue
                        
                        s = "Querying database...\n"
                        queries = []
                        for query in step.queries:
                            temp = ""
                            q_text = query.embedding_query.query_text if query.embedding_query else ""
                            entities = [e.entity for e in query.entity_queries]
                            if q_text:
                                temp += f"Q: {q_text}\n"
                            if len(entities) > 0:
                                temp += "E: **" + ", ".join(entities) + "**\n"
                            queries.append(temp)

                        queries = [q.strip() for q in queries if q.strip() != ""]
                        if len(queries) == 0:
                            continue
                        with_index = len(step.queries) > 1
                        for i, q in enumerate(queries):
                            if with_index:
                                s += f"{i+1}. "
                                # add indent to all lines except first
                                q_lines = q.split("\n")
                                s += q_lines[0] + "\n"
                                for line in q_lines[1:]:
                                    s += "    " + line + "\n"
                            else:
                                s += f"{q}\n"
                        yield StreamingResponseChunk(type="query", content=s)
                    case PipelineStatus.RETRIEVAL_UPDATE:
                        s = "Retrieving information...\n"
                        step: RetrievalStep = update.retrieval_step
                        if step is None or len(step.results) == 0:
                            yield StreamingResponseChunk(type="retrieval", content="No results found.\n")
                            continue
                        for result in step.results:
                            s += f"- "
                            # add indent to all lines except first
                            r_lines = result.content.split("\n")
                            s += r_lines[0] + "\n"
                            for line in r_lines[1:]:
                                s += "    " + line + "\n"
                        yield StreamingResponseChunk(type="retrieval", content=s)
                    case _:
                        # for other statuses, we don't yield anything for now
                        continue
            except Exception as e:
                yield StreamingResponseChunk(type="error", content=f"An error occurred while processing pipeline updates: {str(e)}")
                completed = True
        
                        
        
    def _handle_pipeline_response(self, response:Message)->Generator[StreamingResponseChunk, None, None]:
        """
        Process the final response from the pipeline.
        Currently a placeholder for future implementation.
        """
        if response is None:
            return "Error: No response generated."
        

        thought_text = response.reasoning_text or ""
        content = response.message_text or ""
        if not content:
            yield StreamingResponseChunk(type="error", content="Error: Empty response.")
            return
        if thought_text:
            yield StreamingResponseChunk(type="thought", content=thought_text)
        yield StreamingResponseChunk(type="response", content=content)

        # add metadata info if available
        if response.source_ids:
            sources = "\n**Sources:**\n"
            sources += "\n".join(f" - {source_id}" for source_id in response.source_ids)
            yield StreamingResponseChunk(type="response", content=sources)

        return
            
    async def generate_response(self, chat_request: ChatRequest) -> AsyncGenerator[StreamingResponseChunk, None]:
        # for nowm only allow one response at a time
        # we can handle this better later
        if self._generating_response:
            yield StreamingResponseChunk(type="error", content="Error: Already generating a response. Please wait.")
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
                yield update
                
            response = await main_task


            for chunk in self._handle_pipeline_response(response):
                yield chunk


        except Exception as e:
            yield StreamingResponseChunk(type="error", content=f"An error occurred during response generation: {str(e)}")

        finally:
            self._generating_response = False
            

    async def yield_word_by_word_wrapper(self, inner_generator, word_delay=0.01)->AsyncGenerator[StreamingResponseChunk, None]:
        """
        Wraps an async generator to yield its output word by word with a delay.
        """
        async for chunk in inner_generator:
            content = chunk.content
            if not content:
                yield chunk
                continue
            words = content.split(" ")
            for word in words:
                yield StreamingResponseChunk(type=chunk.type, content=word + " ")
                await asyncio.sleep(word_delay)
                
    async def chunks_to_json_stream(self, chunk_generator: AsyncGenerator[StreamingResponseChunk, None]) -> AsyncGenerator[bytes, None]:
        """
        Converts StreamingResponseChunk objects to JSON bytes for streaming.
        """
        async for chunk in chunk_generator:
            # print("Sending chunk:", chunk.content)
            json_bytes = (json.dumps(chunk.model_dump(mode="json")) + "\n").encode("utf-8")
            yield json_bytes

    async def chat(self,request: ChatRequest):
        """
        Receives a user message and returns a streaming response.
        """
        return StreamingResponse(
            self.chunks_to_json_stream(self.generate_response(request)),
            media_type="application/json"
        )

    # --- Static File Serving ---
    async def get_index(self):
        return FileResponse(self.static_dir / "index.html", media_type="text/html")

def launch_webui():
    """
    Launch the FastAPI web UI for the Dynamic Memory Agent.
    """
    import uvicorn
    logging.basicConfig(level=logging.DEBUG)
    app_instance = DMAWebUI()
    app = app_instance.app
    uvicorn.run(app, host="0.0.0.0", port=8000)

# --- Run the App ---
if __name__ == "__main__":
    launch_webui()
    

