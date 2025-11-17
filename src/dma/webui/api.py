import asyncio
from typing import AsyncGenerator, Generator
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import pathlib

from dma.pipeline import Pipeline, PipelineUpdate, PipelineStatus
from dma.core import Conversation, Message, Role, RetrievalStep, RetrievalQuery, Source, SourceType
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
    user_token: str | None = None
    
    def to_message(self) -> Message:
        return Message(role=Role.USER, content=self.message)
    
class UserAuthRequest(BaseModel):
    user_token: str
    
class HistoryRequest(BaseModel):
    user_token: str | None = None
    
class StreamingResponseChunk(BaseModel):
    type: str # "query" | "retrieval" | "thought" | "response" | "error" | "status"
    content: str | None = None
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
        self._conversations = {}
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

        self.app.post("/api/history", response_model=list[ChatMessage])(self.get_history)
        self.app.post("/api/clear_history")(self.clear_history)
        self.app.post("/api/chat")(self.chat)
        self.app.get("/", response_class=FileResponse)(self.get_index)
        
    def get_conversation(self, user_token: str) -> Conversation:
        """
        Get the conversation for a given user token.
        """
        if user_token not in self._conversations:
            self._conversations[user_token] = Conversation()
        return self._conversations[user_token]

    async def get_history(self, request: HistoryRequest) -> list[ChatMessage]:
        """
        Returns the chat history as a list of ChatMessage objects.
        """
        
        return [
            ChatMessage.from_message(msg) for msg in self.get_conversation(request.user_token).messages if msg.role in [Role.USER, Role.ASSISTANT] and msg.message_text
        ]
        
    async def clear_history(self, request: UserAuthRequest):
        """
        Clears the chat history for the given user token.
        """
        if request.user_token in self._conversations:
            del self._conversations[request.user_token]
        return {"status": "success"}

            
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
                        
                        s = "Querying database...  \n"
                        queries = []
                        for query in step.queries:
                            temp = ""
                            q_text = query.embedding_query.query_text if query.embedding_query else ""
                            entities = [e.entity for e in query.entity_queries]
                            if q_text:
                                temp += f"Q: {q_text}  \n"
                            if len(entities) > 0:
                                temp += "E: *" + ", ".join(entities) + "*"
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
                                s += q_lines[0] + "  \n"
                                for line in q_lines[1:]:
                                    s += "    " + line + "  \n"
                            else:
                                s += f"{q}\n"
                        yield StreamingResponseChunk(type="query", content=s)
                    case PipelineStatus.RETRIEVAL_UPDATE:
                        s = "Retrieving information...  \n"
                        step: RetrievalStep = update.retrieval_step
                        if step is None or len(step.results) == 0:
                            yield StreamingResponseChunk(type="retrieval", content="No results found.\n")
                            continue
                        for result in step.results:
                            s += f"- "
                            # add indent to all lines except first
                            r_lines = result.memory.memory.split("\n")
                            s += r_lines[0] + "  \n"
                            for line in r_lines[1:]:
                                s += "    " + line + "  \n"
                        yield StreamingResponseChunk(type="retrieval", content=s)
                    case _:
                        # for other statuses, just send status if message is present
                        if update.message:
                            yield StreamingResponseChunk(type="status", content=None, status=update.message)
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
        if response.source_memories:
            source_list = [m.source for m in response.source_memories if m.source]
            # only include unique sources
            unique_sources = list(set(source_list))
            if len(unique_sources) > 0:
                source_entries = []
                for src in unique_sources:
                    if src.source_type == SourceType.WEB:
                        # markdown link
                        entry = f"- [{src.source}](https://{src.full_source})"
                        source_entries.append(entry)
                    elif src.source_type == SourceType.DOCUMENT:
                        entry = f"- {src.full_source}"
                        source_entries.append(entry)
                    else:
                        entry = f"- {src.full_source}"
                        source_entries.append(entry)
                sources_md = "\n\n### Sources:\n" + "\n".join(source_entries)
                yield StreamingResponseChunk(type="response", content=sources_md)

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
            conversation = self.get_conversation(chat_request.user_token)
            queue = asyncio.Queue()
            conversation.add_message(chat_request.to_message())

            # run generate in executor to avoid blocking
            loop = asyncio.get_event_loop()
            main_future = loop.run_in_executor(None, self.pipeline.generate, conversation, lambda update: queue.put_nowait(update))
            main_task = asyncio.ensure_future(main_future)
            
            async for update in self._handle_pipeline_updates(queue):
                yield update
                
            response = await main_task


            for chunk in self._handle_pipeline_response(response):
                yield chunk
                
            conversation.add_message(response)


        except Exception as e:
            # print stack trace
            import traceback
            traceback.print_exc()
            yield StreamingResponseChunk(type="error", content=f"An error occurred during response generation: {str(e)}")

        finally:
            self._generating_response = False
            

    async def yield_word_by_word_wrapper(self, inner_generator, time_per_chunk=2.0, messages_per_second=6.0)->AsyncGenerator[StreamingResponseChunk, None]:
        """
        Wraps an async generator to yield its output word by word with a delay.
        """
        async for chunk in inner_generator:
            content = chunk.content
            if not content:
                yield chunk
                continue
            
            # calculate n of words and delay
            delay = 1.0 / messages_per_second
            words = content.split(" ")
            words_per_chunk = max(1, int(len(words) * delay / time_per_chunk))
            for i in range(0, len(words), words_per_chunk):
                sub_content = " ".join(words[i:i+words_per_chunk]) + " "
                #if (i + 1) * words_per_chunk < len(words):
                #    # add trailing space if not last chunk
                #    sub_content += " "
                yield StreamingResponseChunk(type=chunk.type, content=sub_content)
                await asyncio.sleep(delay)
                
    async def chunks_to_json_stream(self, chunk_generator: AsyncGenerator[StreamingResponseChunk, None]) -> AsyncGenerator[bytes, None]:
        """
        Converts StreamingResponseChunk objects to JSON bytes for streaming.
        """
        async for chunk in chunk_generator:
            # print("Sending chunk:", chunk.content)
            json_bytes = (json.dumps(chunk.model_dump(mode="json")) + "\n").encode("utf-8")
            yield json_bytes

    async def chat(self, request: ChatRequest):
        """
        Receives a user message and returns a streaming response.
        """
        
        # output ip and request message to console
        print(f"Received chat request: {request.message}")
        print(f"User token: {request.user_token}")
        
        if not request.user_token or len(request.user_token.strip()) < 5:
            return "{\"type\": \"error\", \"content\": \"Error: Invalid user token.\"}"

        return StreamingResponse(
            self.chunks_to_json_stream(self.yield_word_by_word_wrapper(self.generate_response(request))),
            media_type="application/json"
        )

    # --- Static File Serving ---
    async def get_index(self):
        return FileResponse(self.static_dir / "index.html", media_type="text/html")

def launch_webui(host: str = "0.0.0.0", port: int = 8000):
    """
    Launch the FastAPI web UI for the Dynamic Memory Agent.
    """
    import uvicorn
    logging.basicConfig(level=logging.DEBUG)
    app_instance = DMAWebUI()
    app = app_instance.app
    uvicorn.run(app, host=host, port=port)

# --- Run the App ---
if __name__ == "__main__":
    launch_webui()
    

