# This module is responsible for generating queries based on user input and context.
# The generated queries can then be used to retrieve relevant memories from the memory database.
# Therefore, the queries should be relevant to the user's intent and the current conversation context.
# Besides the user prompt, the context can include:
# - Recent conversation history
# - Relevant entities mentioned in the conversation
# - Previous retrieval results (iterative query refinement)
# - Any other relevant information that can help in formulating effective queries.

from dma.generator import BaseGenerator, LowLevelLlamaCppGenerator
from dma.core import Conversation, Message, Retrieval, TimeRelevance, Role, RetrievalStep, RetrievalQuery, EntityQuery
from dma.utils import parse_timestamp

import logging
from pydantic import BaseModel
import json


class ContextQuery(BaseModel):
    """
    A ContextQuery represents a query generated based on the conversation context.
    """
    query: str # a query in form of a question to retrieve relevant memories
    topic: str = None # the topic or entity the query is focused on
    entities: list[str] # a list of named entities, such as people, places
    time_relevance: TimeRelevance = TimeRelevance.UNKNOWN
    time_point: str = "UNKNOWN" # a specific time point or period the query is focused on
    
class QueryResponseModel(BaseModel):
    """
    A QueryResponseModel represents the response from the query generator.
    It contains a list of ContextQuery objects.
    """
    clarification_needed: bool
    queries: list[ContextQuery]

class QueryGenerator:
    """
    A QueryGenerator generates queries based on user input and context.
    The generated queries can then be used to retrieve relevant memories from the memory database.
    """
    def __init__(self, generator:BaseGenerator):
        self.generator = generator
        
    def generate_queries(self, conversation:Conversation, retrieval:Retrieval=None) -> Retrieval:
        """
        Generate queries based on the conversation and previous retrieval results.
        
        Parameters
        ----------
        conversation : Conversation
            The current conversation context.
        retrieval : Retrieval, optional
            The previous retrieval results, by default None.
        
        Returns
        -------
        Retrieval
            The updated retrieval with generated queries.
        """
        # Prepare the prompt for the generator
        prompt: Conversation = self._prepare_prompt(conversation, retrieval)
        beginning: str | None = self._get_reply_beginning()
        
        if not retrieval:
            user_prompt = conversation.messages[-1] if conversation.messages else None
            if not user_prompt or user_prompt.role != Role.USER:
                raise ValueError("The last message in the conversation must be a user message.")
            retrieval = Retrieval(
                conversation=conversation,
                user_prompt=user_prompt,
                steps=[]
            )
            
        attempts = 0
        max_attempts = 3
        success = False
        step: RetrievalStep | None = None
        
        while not success and attempts < max_attempts:
            try:
                # Generate the queries using the generator
                response = self.generator.generate(prompt, context=beginning)

                # Parse the response to extract queries
                step = self._parse_response(response)
                success = True
                
            except Exception as e:
                logging.error(f"Error generating queries: {e}")
                attempts += 1
                continue

        
        if step and success:
            retrieval.add_step(step)
            if len(step.queries) == 0:
                retrieval.mark_satisfactory()
        else:
            logging.error("Failed to generate queries after multiple attempts.")
            retrieval.done = True
            retrieval.satisfactory = False
        
        return retrieval
    
    def _get_instructions(self) -> str:
        """
        Get the instructions for the query generator.
        
        Returns
        -------
        str
            The instructions for the query generator.
        """
        #TODO: add max queries to config
        MAX_QUERIES = 5
        
        # TODO: keep instructions in a separate file
        instructions = (
            "You are a query generator. Your task is to generate relevant queries based on the user's input and context.\n"
            "The generated queries should be in the form of questions that can help retrieve relevant memories from a database.\n"
            "Consider the following when generating queries:\n"
            "- The user's intent and the current conversation context.\n"
            "- Recent conversation history.\n"
            "- Relevant entities mentioned in the conversation.\n"
            "- Previous retrieval results (if any).\n"
            "- Any other relevant information that can help in formulating effective queries.\n"
            "Make sure the queries are clear, concise, and relevant to the user's needs.\n"
            "Focus on new information that has not been covered in previous queries or replies from the assistant.\n"
            "Avoid overly broad or vague queries, as well as using any relative time expressions like 'yesterday' or 'last week'.\n"
            "Names for places, people, events, or other entities should be as specific as possible, avoiding pronouns or generic terms.\n"
            f"Provide multiple queries if necessary, up to {MAX_QUERIES}, each focusing on different aspects of the user's input and context.\n"
            "If no additional information is required, either due to being already clarified in previous retrievals or assistent messages, or "
            "the prompt not being complex enough to require any, leave the list empty.\n"
            "If the user's prompt is unclear or ambiguous, think about what they would have to clarify and leave the list empty.\n"
            "For each query, also provide:\n"
            "- The topic or entity the query is focused on (if applicable).\n"
            "- The time relevance of the query (e.g., DAY, WEEK, MONTH, YEAR, DECADE, CENTURY, ALWAYS, UNKNOWN).\n"
            "- A specific time point or period the query is focused on (if applicable).\n"
            "Format your response as a JSON object with a 'queries' field containing a list of queries.\n"
            "After the reasoning step (inside <think></think> tags), immediately provide the JSON response without any additional text.\n"
        )
        
        return instructions
    
    def _get_format(self) -> str:
        """
        Get the response format for the query generator.
        
        Returns
        -------
        str
            The response format for the query generator.
        """
        formats = (
            "The response should be a JSON object with the following structure:\n"
            "{\n"
            "  \"clarification_needed\": bool, # true if the user's prompt is unclear and needs clarification, false otherwise\n"
            "  \"queries\": [\n"
            "    {\n"
            "      \"query\": str, # a query in form of a question to retrieve relevant memories, as verbose as possible\n"
            "      \"topic\": str or null, # the topic or entity the query is focused on\n"
            "      \"entities\": [str, ...], # a list of relevant entities, such as people, places, concepts, organizations, technologies etc.\n"
            "      \"time_relevance\": str, # a time frame the query is focused on, one of ['UNKNOWN', 'DAY', 'WEEK', 'MONTH', 'YEAR', 'DECADE', 'CENTURY', 'ALWAYS']\n"
            "      \"time_point\": str or null, # a specific time point or period the query is focused on, formatted as one of: "
            "#d (number of days ago), #w (number of weeks ago), #m (number of months ago), #y (number of years ago), 'YYYY-MM-DD' (specific date), "
            "'YYYY-MM' (specific month), 'YYYY' (specific year), 'DD' (specific day of this month), 'NAME_OF_MONTH' (specific month of this year), "
            "'NAME_OF_WEEKDAY' (specific day of this week), 'UNKNOWN' (if not applicable)\n"
            "    },\n"
            "    ...\n"
            "  ]\n"
            "}\n"
            "Ensure the JSON is properly formatted."
        )
        
        return formats
    
    def _get_example(self) -> str:
        """
        Get an example for the query generator.
        
        Returns
        -------
        str
            An example for the query generator.
        """
        example = (
            "Example:\n"
            "User input: 'I want to know about the project we discussed last week and any updates on the budget.'\n"
            "Conversation context: Recent messages about project discussions and budget considerations.\n"
            "Previous retrieval: Memories related to project timelines and financial reports.\n"
            "Generated response:\n"
            "{\n"
            "  \"clarification_needed\": false,\n"
            "  \"queries\": [\n"
            "    {\n"
            "      \"query\": \"What were the key points discussed about the EEG project MiniEEG in the meeting last week?\",\n"
            "      \"topic\": \"MiniEEG Project Discussion\",\n"
            "      \"entities\": [\"EEG\", \"MiniEEG\"],\n"
            "      \"time_relevance\": \"WEEK\",\n"
            "      \"time_point\": \"#1w\"\n"
            "    },\n"
            "    {\n"
            "      \"query\": \"Are there any recent updates on the budget for the MiniEEG project?\",\n"
            "      \"topic\": \"MiniEEG Project Budget\",\n"
            "      \"entities\": [\"MiniEEG\"],\n"
            "      \"time_relevance\": \"MONTH\",\n"
            "      \"time_point\": \"#1m\"\n"
            "    }\n"
            "  ]\n"
            "}\n"
        )
        
        return example

    def _prepare_prompt(self, conversation:Conversation, retrieval:Retrieval=None) -> Conversation:
        """
        Prepare the prompt for the query generator.
        
        Parameters
        ----------
        conversation : Conversation
            The current conversation context.
        retrieval : Retrieval, optional
            The previous retrieval results, by default None.
        
        Returns
        -------
        Conversation
            The prepared prompt for the query generator.
        """
        instructions = self._get_instructions()
        format_instructions = self._get_format()
        example = self._get_example()
        
        system_message = Message(
            role="system",
            content=f"{instructions}\n{format_instructions}\n{example}"
        )
        
        messages = [system_message]
        
        user_prompt = conversation.messages[-1] if conversation.messages else None
        
        if not user_prompt or user_prompt.role != Role.USER:
            raise ValueError("The last message in the conversation must be a user message.")
        
        for msg in conversation.messages:
            if msg.role != Role.SYSTEM:
                messages.append(msg)
                
        if retrieval and len(retrieval.steps) > 0:
            # add previous queries and results to the prompt for context
            for step in retrieval.steps:
                self._add_retrieval_step_to_prompt(step, messages)
                

        return Conversation(messages=messages)
    
    def _get_reply_beginning(self) -> str | None:
        """
        Return a standard beginning for the assistant's reply.
        Useful to prime the model to think before answering.
        
        Returns
        -------
        str | None
            The reply beginning to add.
        """
        beginning = "Okay, first I should think if the user's prompt has enough context to generate relevant queries, and if so, I will generate them in JSON format as specified."
        if self.generator is LowLevelLlamaCppGenerator:
            # only the low level model supports custom beginnings
            return beginning
        return None
        
    
    def _add_retrieval_step_to_prompt(self, step, messages):
        """
        Add a retrieved information to the prompt messages.
        
        Parameters
        ----------
        step : RetrievalStep
            The retrieval step containing queries and results.
        messages : list[Message]
            The list of messages to update.
        """
        
        # results should already be in order, best first, but just in case, sort by score
        step.results.sort(key=lambda r: r.score, reverse=True)
        
        # add reasoning from previous step?
        # could help the model understand why certain queries were made
        # and potentially avoid repeating the same queries
        message_content = []
        if step.reasoning:
            message_content.append(f"<think>{step.reasoning}</think>")

        message_content.append("Retrieved Context:")
        for memory_result in step.results:
            memory = memory_result.memory
            memory_content = memory.memory
            if not memory_content:
                continue
            memory_source = memory.source or "unknown"
            part = memory_content
            if memory_source:
                part += f" (source: {memory_source})"
            message_content.append(f"- {part}")

        messages.append(Message(
            role=Role.ASSISTANT,
            content="\n".join(message_content)
        ))
        
    def _parse_response(self, response:Message) -> RetrievalStep:
        """
        Parse the response from the query generator to extract queries
        and update the retrieval object.
        
        Parameters
        ----------
        response : Message
            The response message from the query generator.
        retrieval : Retrieval
            
        Returns
        -------
        RetrievalStep
            The updated retrieval step with new queries.
        """
            
        # Create a new retrieval step
        new_step = RetrievalStep(queries=[], results=[])
        
        try:
            reasoning, queries, clarification_needed = self._parse_reasoning_and_json(response)
        except ValueError as e:
            # If parsing fails, return the retrieval unchanged
            raise Exception(f"Failed to parse query generator response: {e}")
        
        new_step.reasoning = reasoning
        new_step.clarification_needed = clarification_needed
        
        if len(queries) == 0:
            # No queries generated
            return new_step
        
        for query in queries:
            try:
                retrieval_query = RetrievalQuery.from_text(
                    query_text=query.query,
                    entity_queries=EntityQuery.from_entities(query.entities),
                    weight=1.0,
                    time_relevance=query.time_relevance,
                    timestamp=query.time_point
                )
                logging.debug(f"Generated RetrievalQuery: {retrieval_query.embedding_query.query_text}")
                new_step.queries.append(retrieval_query)
            except Exception as e:
                logging.warning(f"Failed to create RetrievalQuery from ContextQuery: {e}")
                continue
            
        if len(new_step.queries) == 0 and len(queries) > 0:
            raise Exception("All generated queries failed to parse into RetrievalQuery objects.")
            
        return new_step
        
        
        
    def _parse_reasoning_and_json(self, response: Message) -> tuple[str, list[ContextQuery]]:
        """
        Parse the response message to extract reasoning and JSON content.
        
        Parameters
        ----------
        response : Message
            The response message from the query generator.
        
        Returns
        -------
        tuple[str, list[ContextQuery]]
            A tuple containing the reasoning string and the parsed list of queries.
        """
        
        # Extract reasoning if present
        reasoning = response.reasoning_text.strip() if response.reasoning_text else ""
        content = response.message_text.strip()
        
        # we are expecting a JSON object in the content, specifically a list of queries
        if not content.startswith("{"):
            # try to fix it by finding the first '{' and last '}' and extracting that part
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                content = content[start:end+1]
            else:
                raise ValueError("Response does not contain a valid JSON object.")
            
        try:
            json_content = json.loads(content)
        except json.JSONDecodeError as e:
            logging.debug(f"Failed to decode JSON content: {content}")
            raise ValueError(f"Failed to parse JSON content: {e}")
        
        if not ("queries" in json_content or "clarification_needed" in json_content):
            logging.debug(f"JSON content contains no 'queries' or 'clarification_needed' field: {json_content}")
            raise ValueError("JSON content does not contain 'queries' or 'clarification_needed' field.")
        
        clarification_needed = json_content.get("clarification_needed", False)
        queries = []
        if not isinstance(json_content, dict):
            logging.debug(f"JSON content of type {type(json_content)} is not a dict: {json_content}")
            raise ValueError("Failed to parse query dict.")

        for d in json_content.get("queries", []):
            if not isinstance(d, dict):
                raise ValueError("Each query must be a JSON object.")
            
            query = d.get("query", None)
            if not query or not isinstance(query, str):
                continue
            topic = d.get("topic", None)
            entities = d.get("entities", [])
            time_relevance_str = d.get("time_relevance", "UNKNOWN")
            time_point_str = d.get("time_point", "UNKNOWN") or "UNKNOWN"
            
            time_relevance = TimeRelevance.from_string(time_relevance_str)
            time_point = parse_timestamp(time_point_str) if time_point_str != "UNKNOWN" else -1
            
            # if time_point is -1, set time_relevance to UNKNOWN if it's not ALWAYS
            if time_point == -1 and time_relevance != TimeRelevance.ALWAYS:
                time_relevance = TimeRelevance.UNKNOWN
                
            context_query = ContextQuery(
                query=query,
                topic=topic,
                entities=entities if isinstance(entities, list) else [],
                time_relevance=time_relevance,
                time_point=time_point_str
            )
            queries.append(context_query)
            
            logging.debug(f"Parsed ContextQuery: {context_query.query} with entities {context_query.entities} "
                          f"and time_relevance {context_query.time_relevance}, time_point {context_query.time_point}")
            
            
        return reasoning, queries, clarification_needed
            

        