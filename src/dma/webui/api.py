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
import google.genai as genai
from dma.utils import get_env_variable, get_data_dir
import random
import time



# --- Pydantic Models ---
# Model for a single message in the chat history
class ChatMessage(BaseModel):
    role: str # "USER" | "ASSISTANT"
    content: str
    source: str = "default" # used to identify llm source. default or "#:name", with # being the index of the alternative llm
    
    def from_message(msg: Message) -> "ChatMessage":
        return ChatMessage(role=msg.role.value.lower(), content=msg.message_text or "")

# Model for the user's chat request
class ChatRequest(BaseModel):
    message: str
    user_token: str | None = None
    mode: str = "default" # default for single llm, compare for multiple llms
    
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
    source: str = "default" # used to identify llm source. default or "#:name", with # being the index of the alternative llm
    
class BlindTestAnswer(BaseModel):
    model_id: str
    content: str
    
class BlindTestResponse(BaseModel):
    answers: list[BlindTestAnswer]
    
class BlindTestRatingRequest(BaseModel):
    user_token: str | None = None
    best_model_id: str | None = None
    
class BlindTestRatingResponse(BaseModel):
    content: str

class DMAWebUI:
    def __init__(self):
        # --- App Setup ---
        
        script_dir = pathlib.Path(__file__).parent.resolve()
        static_dir = script_dir / "static"
        self.static_dir = static_dir
        
        print("Loading pipeline...")
        self.pipeline = Pipeline()
        print("Pipeline loaded.")
        self._user_data = {}
        self._generating_response = False
        
        # setup gemini if key is set
        GEMINI_API_KEY_NAME = "GENAI_API_KEY"
        gemini_api_key = get_env_variable(GEMINI_API_KEY_NAME)
        self._gemini = None
        if gemini_api_key:
            print("Setting up Google Gemini API...")
            self._gemini = genai.Client(api_key=gemini_api_key)
        
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
        self.app.get("/index.html", response_class=FileResponse)(self.get_index)
        self.app.get("/blind_test", response_class=FileResponse)(lambda: FileResponse(static_dir / "blind_test.html", media_type="text/html"))
        self.app.post("/api/blind_test", response_model=BlindTestResponse)(self.blind_test)
        self.app.post("/api/rate_blind_test", response_model=BlindTestRatingResponse)(self.rate_blind_test)
        
    def get_conversation(self, user_token: str, key: str = "conversation") -> Conversation:
        """
        Get the conversation for a given user token.
        """
        if user_token not in self._user_data:
            self._user_data[user_token] = {}
        if key not in self._user_data[user_token]:
            self._user_data[user_token][key] = Conversation()
        return self._user_data[user_token][key]

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
        if request.user_token in self._user_data:
            del self._user_data[request.user_token]
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
                        
                        if step.clarification_needed and len(step.queries) == 0:
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
                    case PipelineStatus.MEMORY_UPDATE:
                        if update.message:
                            yield StreamingResponseChunk(type="status", content=None, status=update.message)
                    case PipelineStatus.SUMMARY_UPDATE:
                        if update.message:
                            yield StreamingResponseChunk(type="status", content=None, status=update.message)
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
            
            # if mode is compare, run alternative llms
            if chat_request.mode == "compare":
                gemini_response_task = self._generate_gemini_response(chat_request)
                # first alt is just the default llm
                local_llm = self.pipeline.generator
                alt_conversation_1 = self.get_conversation(chat_request.user_token, key="alt_conversation_1")
                alt_conversation_1.add_message(chat_request.to_message())
                alt_response_1 = await loop.run_in_executor(None, local_llm.generate, alt_conversation_1)
                for chunk in self._handle_pipeline_response(alt_response_1):
                    # set source to "1:#name"
                    chunk.source = f"1:Local LLM"
                    yield chunk
                alt_conversation_1.add_message(alt_response_1)
                
                gemini_message = await gemini_response_task
                for chunk in self._handle_pipeline_response(gemini_message):
                    # set source to "2:Gemini"
                    chunk.source = f"2:Gemini-2.5-flash"
                    yield chunk


        except Exception as e:
            # print stack trace
            import traceback
            traceback.print_exc()
            yield StreamingResponseChunk(type="error", content=f"An error occurred during response generation: {str(e)}")

        finally:
            self._generating_response = False
            
    async def _generate_gemini_response(self, chat_request: ChatRequest) -> Message:
        """
        Generate a response using Google Gemini LLM.
        """
        if self._gemini is None:
            logging.error("Gemini client not configured.")
            return Message(role=Role.ASSISTANT, content="Error: Gemini LLM not configured.")
        
        conversation = self.get_conversation(chat_request.user_token, key="gemini_conversation")
        prompt = chat_request.to_message()
        conversation.add_message(prompt)
        
        gemini_messages = []
        for msg in conversation.messages:
            role = "user" if msg.role == Role.USER else "model"
            gemini_messages.append({
                "role": role,
                "parts": [
                    {
                        "text": msg.message_text or ""
                    }
                ]
            }
            )
        def generate_response():
            response = self._gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=gemini_messages,
            )
            return response
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, generate_response)
        
        response_message = Message(role=Role.ASSISTANT, content=response.text)
        conversation.add_message(response_message)
        return response_message
        
            

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
                yield StreamingResponseChunk(type=chunk.type, content=sub_content, status=chunk.status, source=chunk.source)
                await asyncio.sleep(delay)
                
    async def chunks_to_json_stream(self, chunk_generator: AsyncGenerator[StreamingResponseChunk, None]) -> AsyncGenerator[bytes, None]:
        """
        Converts StreamingResponseChunk objects to JSON bytes for streaming.
        """
        async for chunk in chunk_generator:
            # print("Sending chunk:", chunk.content)
            json_bytes = (json.dumps(chunk.model_dump(mode="json")) + "\n").encode("utf-8")
            yield json_bytes
            
    async def blind_test(self, request: ChatRequest) -> BlindTestResponse:
        """
        Receives a user message and returns a selection of responses from multiple LLMs without identifying them.
        """
        
        blind_history = self.get_conversation(request.user_token, key="blind_test_conversation")
        blind_history.add_message(request.to_message())
        test_llms = {
            "dynmem": lambda conv: self.pipeline.generate(conv),
            "local": lambda conv: self.pipeline.generator.generate(conv)
        }
        answers = {}
        for model_id, llm_func in test_llms.items():
            answer = llm_func(blind_history.copy())
            secret_id = str(random.randint(1000, 999999))
            answers[secret_id] = {"model_id": model_id, "message": answer}
            
        client_answers = []
        for secret_id, answer in answers.items():
            client_answers.append(BlindTestAnswer(model_id=secret_id, content=answer["message"].message_text or ""))
            
        self._user_data[request.user_token]["blind_test_answers"] = answers
            
        # shuffle answers
        random.shuffle(client_answers)
        return BlindTestResponse(answers=client_answers)
    
    def _log_blind_test_rating(self, user_token: str, best_model_id: str):
        """
        Logs the blind test rating for analysis.
        """
        answers = self._user_data[user_token]["blind_test_answers"]
        conversation = self.get_conversation(user_token, key="blind_test_conversation")
        
        best_model_name = answers[best_model_id].get("model_id", None)
        
        print("Logging blind test rating: User token:", user_token, "Best model ID:", best_model_id, "Best model name:", best_model_name)
        
        log_answers = []
        for answer in answers.values():
            log_answers.append({
                "model_id": answer["model_id"],
                "message": answer["message"].to_dict()
            })
        
        entry = {
            "user_token": user_token,
            "preferred_model": best_model_name,
            "conversation": [msg.to_dict() for msg in conversation.messages],
            "answers": log_answers,
            "timestamp": int(time.time())
        }
        
        try:
            data_dir = get_data_dir()
            log_dir = data_dir / "blind_test_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "blind_test_ratings.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.error(f"Failed to log blind test rating: {str(e)}")
    
    async def rate_blind_test(self, request: BlindTestRatingRequest):
        """
        Receives the user's rating of the best blind test answer.
        """
        # check if there is an open blind test
        if request.user_token not in self._user_data or "blind_test_answers" not in self._user_data[request.user_token]:
            return BlindTestRatingResponse(content="Error: No blind test found for this user token.")
        answers = self._user_data[request.user_token]["blind_test_answers"]
        best_model_id = request.best_model_id
        try:
            self._log_blind_test_rating(request.user_token, best_model_id)
        except Exception as e:
            logging.error(f"Failed to log blind test rating: {str(e)}")
        if request.best_model_id not in answers:
            # treat as no selection, return dynmem as default
            best_model_id = [k for k, v in answers.items() if v["model_id"] == "dynmem"][0]
        else:
            best_model_id = request.best_model_id
            
        # get the message content
        best_message = answers[best_model_id]["message"].message_text or ""
        
        # delete the blind test data
        del self._user_data[request.user_token]["blind_test_answers"]
        
        # add the message to the blind test conversation
        blind_history = self.get_conversation(request.user_token, key="blind_test_conversation")
        blind_history.add_message(answers[best_model_id]["message"])
        return BlindTestRatingResponse(content=best_message)

    async def chat(self, request: ChatRequest):
        """
        Receives a user message and returns a streaming response.
        """
        
        # output ip and request message to console
        print(f"Received chat request: {request.message}")
        print(f"User token: {request.user_token}")
        print(f"Mode: {request.mode}")
        
        
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
    

