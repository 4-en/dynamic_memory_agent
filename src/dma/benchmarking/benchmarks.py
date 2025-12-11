from deepeval.synthesizer import Synthesizer
from deepeval.synthesizer.config import ContextConstructionConfig, EvolutionConfig
from deepeval.simulator import ConversationSimulator
from deepeval.test_case import LLMTestCase, ConversationalTestCase, Turn, LLMTestCaseParams, TurnParams
from deepeval.dataset import EvaluationDataset
from deepeval import evaluate
from deepeval.evaluate import AsyncConfig
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, HallucinationMetric, ContextualRecallMetric, TurnRelevancyMetric, ConversationCompletenessMetric
from deepeval.models import GeminiModel
from deepeval.metrics import GEval, ConversationalGEval

from dma.core import Conversation, Message, Role
from dma.benchmarking.deep_eval_models import LocalEmbeddingModel
from dma.utils import get_cache_dir, get_env_variable
import os
import time

TEST_MODEL = GeminiModel(model_name="gemini-2.5-flash", api_key=get_env_variable("GENAI_API_KEY"), temperature=0.5)



class SingleTurnBenchmark:
    def __init__(self, document_paths: list[str]):
        """
        Initialize with paths to your text files.
        """
        self.eval_model = TEST_MODEL
        
        self.document_paths = document_paths
        evolution_config = EvolutionConfig(
            num_evolutions=0
        )
        self.synthesizer = Synthesizer(model=self.eval_model, max_concurrent=2, async_mode=False, evolution_config=evolution_config)
        self.goldens = []
        

    def generate_test_data(self, num_questions: int = 2):
        
        # try to use cached goldens if they exist
        cache_dir = get_cache_dir() / "benchmarks"
        cached_goldens_path = cache_dir / "single_turn_goldens.json"
        if cached_goldens_path.exists():
            dataset = EvaluationDataset()
            dataset.add_goldens_from_json_file(cached_goldens_path)
            self.goldens = dataset.goldens
            print(f"Loaded {len(self.goldens)} cached goldens from {cached_goldens_path}.")
            return
        
        """
        Step 1: Read text files and generate QA pairs (Goldens) ONCE.
        """
        print(f"Generating {num_questions} questions from {len(self.document_paths)} documents...")
        emb_model = LocalEmbeddingModel()
        config = ContextConstructionConfig(
            embedder=emb_model,
            critic_model=self.eval_model
        )
        self.goldens = self.synthesizer.generate_goldens_from_docs(
            document_paths=self.document_paths,
            max_goldens_per_context=num_questions,
            context_construction_config=config
        )
        print(f"Generated {len(self.goldens)} goldens.")
        
        # cache the goldens to disk for inspection
        cache_dir = get_cache_dir() / "benchmarks"
        os.makedirs(cache_dir, exist_ok=True)
        # self.synthesizer.save_as("json", cache_dir / "single_turn_goldens.json")

    def run(self, llms: list[object]):
        """
        Step 2: Test every LLM against the generated questions.
        """
        if not self.goldens:
            raise ValueError("No test data found. Run generate_test_data() first.")

        results = {}
        
        

        for llm in llms:
            model_name = llm.get_model_name()
            print(f"\n--- Testing Model: {model_name} ---")
            
            test_cases = []
            generation_time = 0.0
            
            metrics = {
                "correctness": GEval(
                    name="Correctness",
                    model=self.eval_model,
                    evaluation_params=[
                        LLMTestCaseParams.INPUT,
                        LLMTestCaseParams.ACTUAL_OUTPUT],
                    evaluation_steps=[
                        "Check whether the facts in 'actual output' contradict any facts in 'expected output'",
                        "Lightly penalize omissions of detail, focusing on the main idea",
                        "Vague language or contradicting opinions are permissible"
                    ],
                ),
                "answer_relevancy": AnswerRelevancyMetric(threshold=0.5, model=self.eval_model, async_mode=False),
                "faithfulness": FaithfulnessMetric(threshold=0.5, model=self.eval_model, async_mode=False),
                "hallucination": HallucinationMetric(threshold=0.5, model=self.eval_model, async_mode=False),
                "contextual_recall": ContextualRecallMetric(threshold=0.5, model=self.eval_model, async_mode=False)
            }
            
            
            results[model_name] = {}
            # results[model_name]["test_cases"] = []
            for metric_name in metrics.keys():
                results[model_name][metric_name] = []
            
            # Loop through the pre-generated questions
            for golden in self.goldens:
                # 1. Ask the specific LLM
                start_time = time.time()
                actual_output, context = llm.generate_with_context(golden.input)
                answer_generation_duration = time.time() - start_time
                
                # 2. Create the Test Case
                test_case = LLMTestCase(
                    input=golden.input,
                    actual_output=actual_output,
                    context=golden.context,
                    retrieval_context=context,
                    expected_output=golden.expected_output
                )
                
                
                try:
                    for metric_name, metric in metrics.items():
                        metric.measure(test_case)
                        score = metric.score
                        print(f"Metric: {metric_name}, Score: {score}")
                        results[model_name][metric_name].append(score)
                except Exception as e:
                    print(f"Error measuring metric {metric_name} for model {model_name}: {e}")
                    time.sleep(10)  # brief pause before continuing
                    continue
                
                test_cases.append(test_case)
                #results[model_name]["test_cases"].append(test_case)
                generation_time += answer_generation_duration
            print(f"Average generation time for {model_name}: {generation_time / len(self.goldens):.2f} seconds per case.")
            results[model_name]["average_generation_time"] = generation_time / len(self.goldens)
            results[model_name]["total_cases"] = len(self.goldens)
            results[model_name]["total_generation_time"] = generation_time

            # 3. Evaluate this LLM
            #metrics = [AnswerRelevancyMetric(threshold=0.5, model=self.eval_model, async_mode=False), FaithfulnessMetric(threshold=0.5, model=self.eval_model, async_mode=False), HallucinationMetric(threshold=0.5, model=self.eval_model, async_mode=False)]
            #print(f"Running evaluation for {model_name}...")
            
            # evaluate() returns a list of TestResult objects
            #async_config = AsyncConfig(max_concurrent=1, throttle_value=5, run_async=False)
            #eval_results = evaluate(test_cases=test_cases, metrics=metrics, async_config=async_config)
            #results[model_name] = eval_results

        return results

class MultiTurnBenchmark:
    def __init__(self, document_paths: list[str]):
        self.document_paths = document_paths
        self.eval_model = TEST_MODEL
        self.synthesizer = Synthesizer(model=self.eval_model, max_concurrent=1, async_mode=False)
        self.scenarios = []

    def generate_scenarios(self, num_scenarios: int = 3):
        """
        Generates high-level conversation topics (Goldens) from the text files.
        """
        print(f"Generating {num_scenarios} conversation scenarios...")
        emb_model = LocalEmbeddingModel()
        config = ContextConstructionConfig(
            embedder=emb_model,
            critic_model=self.eval_model
        )
        self.scenarios = self.synthesizer.generate_conversational_goldens_from_docs(
            document_paths=self.document_paths,
            max_goldens_per_context=num_scenarios,
            context_construction_config=config
        )
        
        print(f"Generated {len(self.scenarios)} scenarios.")

    def run(self, llms: list[object]):
        """
        Simulates a full conversation for each LLM using the scenarios.
        """
        if not self.scenarios:
            raise ValueError("No scenarios found. Run generate_scenarios() first.")
        
        for scenario in self.scenarios:
            scenario.scenario += "\nEnsure the conversation flows naturally. Use pronouns like 'it' to refer to entities mentioned in previous messages and try to work towards the goal in multiple turns. For example, if your previous prompt mentioned an entity like 'Saturn', follow-up questions can refer to it as 'it' or 'the planet'. Start by using a basic initial question (e.g., 'Do you know about X?') and then build on the conversation from there, using only a pronoun to refer to previously mentioned entities."

        results = {}

        for llm in llms:
            conversation_store = {} # used to track custom conversation objects per thread
            model_name = llm.get_model_name()
            
            #generation_time = 0.0
            
            _ = {
                "conversation_completeness": ConversationCompletenessMetric(threshold=0.5, model=self.eval_model, async_mode=False),
                "answer_relevancy": TurnRelevancyMetric(threshold=0.5, model=self.eval_model, async_mode=False),
                
                "faithfulness": ConversationalGEval(
                    name="Faithfulness",
                    model=self.eval_model,
                    evaluation_params=[
                        TurnParams.CONTENT,
                        TurnParams.EXPECTED_OUTCOME,
                        TurnParams.ROLE,
                        TurnParams.RETRIEVAL_CONTEXT
                    ],
                    criteria="Identify if the assistent's content matches the retrieval context and expected outcome without introducing unverified information.",
                ),
            }
            
            metrics = {
                "correctness": GEval(
                    name="Correctness",
                    model=self.eval_model,
                    evaluation_params=[
                        LLMTestCaseParams.INPUT,
                        LLMTestCaseParams.ACTUAL_OUTPUT,
                        LLMTestCaseParams.EXPECTED_OUTPUT,
                        LLMTestCaseParams.CONTEXT
                    ],
                    evaluation_steps=[
                        "The test case contains a single turn from a multi-turn interaction between a user and an assistant. Check whether the assistant's response ('actual output') contradicts any facts in the 'expected output' or the provided 'context'. ",
                        "Only consider the information that was actually asked for in the user's input, even if the 'expected output' or 'context' contains additional information.",
                        "Lightly penalize omissions of detail, focusing on the main idea",
                        "Pronouns refer to entities mentioned in previous turns and in the context, so an answer is expected even if the entity is not explicitly named.",
                    ],
                ),
                "answer_relevancy": AnswerRelevancyMetric(threshold=0.5, model=self.eval_model, async_mode=False)
            }
            
            print(f"\n--- Simulating Conversations for: {model_name} ---")

            # Define the callback that connects the Simulator to THIS specific LLM
            def chatbot_callback(input: str, turns: list[Turn], thread_id: str) -> Turn:
                
                if thread_id not in conversation_store:
                    conversation_store[thread_id] = Conversation()
                    
                conversation = conversation_store[thread_id]
                conversation.add_message(Message(role=Role.USER, content=input))
                response = None
                attempts = 0
                while response is None and attempts < 3:
                    attempts += 1
                    try:
                        response = llm.generate_message(conversation)
                    except Exception as e:
                        print(f"Error generating message for model {model_name}: {e}")
                        time.sleep(2)  # brief pause before continuing
                        response = None
                        
                if response is None:
                    return Turn(role="assistant", content="Sorry, I am unable to provide a response at this time.", retrieval_context=[])
                
                print(f"[{len(conversation_store)}:{len(conversation.messages)}] Q: {input}\nA: {response.message_text[:50]}\n")
                conversation.add_message(response)
                return Turn(role="assistant", content=response.message_text, retrieval_context=[mem.memory for mem in response.source_memories])

            # Initialize Simulator with this LLM's callback
            simulator = ConversationSimulator(model_callback=chatbot_callback, simulator_model=self.eval_model, max_concurrent=1, async_mode=False)
            
            # Simulate conversations
            # The simulator acts as the user, asking context-aware questions (pronouns, etc.)
            conversational_test_cases = simulator.simulate(
                conversational_goldens=self.scenarios,
                max_user_simulations=5
            )
            
            model_results = {}
            #model_results["average_generation_time"] = generation_time / len(conversational_test_cases)
            #model_results["total_generation_time"] = generation_time
            model_results["total_cases"] = len(conversational_test_cases)
            model_results["total_turns"] = sum(len(c_test_case.turns) for c_test_case in conversational_test_cases) / 2  # each turn pair is user+assistant
            
            for c_test_case in conversational_test_cases:
                
                for i in range(0, len(c_test_case.turns), 2):
                    user_turn = c_test_case.turns[i]
                    assistant_turn = c_test_case.turns[i+1] if i+1 < len(c_test_case.turns) else None
                    if assistant_turn is None:
                        continue
                    
                    turn_test_case = LLMTestCase(
                        input=user_turn.content,
                        actual_output=assistant_turn.content,
                        expected_output=c_test_case.expected_outcome,
                        context=c_test_case.context
                    )
                
                    try:
                        for metric_name, metric in metrics.items():
                            metric.measure(turn_test_case)
                            score = metric.score
                            if metric_name not in model_results:
                                model_results[metric_name] = []
                            model_results[metric_name].append(score)
                            print(f"Metric: {metric_name}, Score: {score}")
                    except Exception as e:
                        print(f"Error measuring metric {metric_name} for model {model_name}: {e}")
                        time.sleep(10)  # brief pause before continuing
                        continue
                
            results[model_name] = model_results
            

        return results