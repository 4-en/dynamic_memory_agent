import json
from typing import Any, Type, List, Dict
from pydantic import BaseModel, ValidationError

# --- Mock LLM Class (to simulate your model) ---
# This class mimics the interface you described:
# model.generate(messages: list, stop_strings: list[str])

class MockLLM:
    """
    A mock LLM to simulate generative calls.
    It returns predefined values in sequence.
    """
    def __init__(self, responses: List[str]):
        self.responses = responses
        self.call_count = 0

    def generate(self, messages: List[Dict[str, str]], stop_strings: List[str]) -> str:
        """Simulates the LLM generating text."""
        
        # This mock just returns the next response in the list
        # A real LLM would generate text based on 'messages'
        # and stop when it hits a string in 'stop_strings'.
        
        if self.call_count >= len(self.responses):
            raise Exception("MockLLM ran out of responses.")
            
        # Get the response and increment the counter
        response = self.responses[self.call_count]
        self.call_count += 1
        
        # print(f"[Debug LLM Call {self.call_count}]")
        # print(f"  Prompt (last msg): {messages[-1]['content']}")
        # print(f"  Stop on: {stop_strings}")
        # print(f"  Generated: '{response}'")
        
        return response

# --- The Pydantic-Forcing Function ---

def generate_structured_json(
    llm_model: Any, 
    pydantic_model: Type[BaseModel], 
    messages: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Forces an LLM to generate JSON output matching a Pydantic model
    by iteratively generating *only* the values.

    Args:
        llm_model: An object with a `.generate(messages, stop_strings)` method.
        pydantic_model: The Pydantic model class to use as the schema.
        messages: The initial list of messages for the conversation.

    Returns:
        A dictionary with the validated data.
        
    Raises:
        ValueError: If the LLM output cannot be parsed as a valid JSON value.
        pydantic.ValidationError: If the final dictionary fails model validation.
    """
    
    # 1. Get the schema and field names from the Pydantic model
    schema = pydantic_model.model_json_schema()
    properties = schema.get('properties', {})
    field_names = list(properties.keys())
    
    output_dict = {}
    
    # 2. Create a *copy* of the messages to avoid modifying the original
    current_messages = list(messages)
    
    # 3. Add the *start* of the assistant's JSON response.
    # We will build this single assistant message incrementally.
    assistant_message_content = "{"
    current_messages.append({"role": "assistant", "content": assistant_message_content})

    # 4. Loop through each field in the Pydantic model
    for i, field_name in enumerate(field_names):
        
        # 5. Add the predefined JSON key and colon to the prompt
        # We are modifying the *last* message in the list (the assistant's)
        key_prompt = f'"{field_name}": '
        current_messages[-1]["content"] += key_prompt
        
        # 6. Determine the correct stop string
        # If it's the last field, stop at "}"; otherwise, stop at ","
        is_last_field = (i == len(field_names) - 1)
        stop_string = "}" if is_last_field else ","
        
        # 7. Call the LLM to generate *only* the value
        # The LLM's prompt is the entire conversation so far,
        # including the JSON structure we've built.
        generated_value_str = llm_model.generate(
            messages=current_messages,
            stop_strings=[stop_string]
        )
        
        # 8. Clean and parse the LLM's output
        generated_value_str = generated_value_str.strip()
        try:
            # Use json.loads() to parse the value string.
            # This correctly handles "strings", numbers, booleans, etc.
            # e.g., json.loads('"Hello"') -> "Hello"
            # e.g., json.loads(' 123 ')   -> 123
            # e.g., json.loads(' true ')  -> True
            parsed_value = json.loads(generated_value_str)
        except json.JSONDecodeError:
            raise ValueError(
                f"LLM output was not valid JSON for field '{field_name}': "
                f"'{generated_value_str}'"
            )
        
        # 9. Store the parsed value
        output_dict[field_name] = parsed_value
        
        # 10. Update the assistant message content for the next iteration
        # It now includes the key, the generated value, and the stop string
        current_messages[-1]["content"] += generated_value_str + stop_string
    
    # 11. After the loop, validate the complete dictionary
    try:
        final_model_instance = pydantic_model(**output_dict)
        # Return the dictionary representation
        return final_model_instance.model_dump()
    except ValidationError as e:
        print(f"--- Validation Failed ---")
        print(f"Final dictionary: {output_dict}")
        print(f"Error: {e}")
        raise e

# --- Example Usage ---

if __name__ == "__main__":
    
    # 1. Define our Pydantic model (the desired structure)
    class UserProfile(BaseModel):
        name: str
        age: int
        is_active: bool
        location: str

    # 2. Define the initial prompt
    initial_prompt = [
        {
            "role": "user",
            "content": "Extract user info from this text: "
                       "'John Doe is 42, lives in New York, and is an active member.'"
        }
    ]

    # 3. Set up the Mock LLM with the *exact* values we expect it
    #    to generate, *including quotes for strings*.
    mock_responses = [
        ' "John Doe"',  # For "name":
        ' 42',          # For "age":
        ' true',        # For "is_active":
        ' "New York"'   # For "location":
    ]
    
    mock_llm = MockLLM(responses=mock_responses)

    # 4. Run the function
    print("🚀 Calling generative function...\n")
    try:
        structured_output = generate_structured_json(
            llm_model=mock_llm,
            pydantic_model=UserProfile,
            messages=initial_prompt
        )
        
        print("✅ Success! Generated structured JSON:")
        import pprint
        pprint.pprint(structured_output)

    except (ValueError, ValidationError) as e:
        print(f"\n❌ Error during generation: {e}")