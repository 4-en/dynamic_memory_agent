# main entry point
# by default, this will launch a basic command-line interface to interact with
# the memory agent via multi turn conversations.

from dma.core import Pipeline
from dma.core import Conversation, Message, Role
import logging


def main():
    
    print("Sanity check: DMA main entry point.")
    
    logging.basicConfig(level=logging.INFO)
    
    print("Dynamic Memory Agent CLI")
    print("Type 'exit' to quit.")
    
    pipeline = Pipeline()
    conversation = Conversation()
    
    input_text = None
    while input_text != "exit":
        input_text = input("You: ")
        if input_text.strip().lower() == "exit":
            break
        
        think_injection = None
        if "<think>" in input_text:
            parts = input_text.split("<think>", 1)
            input_text = parts[0].strip()
            think_injection = parts[1].strip()
        
        input_message = Message(input_text, role=Role.USER)
        conversation.add_message(input_message)
        
        if think_injection:
            # add a system message with the think injection
            system_message = Message(role=Role.ASSISTANT)
            system_message.add_thought(think_injection)
            conversation.add_message(system_message)
        
        response: Message = pipeline(conversation)
        
        if response:
            reasoning = response.reasoning_text
            reply = response.message_text
            print(f"<Agent>\n<think>{reasoning}\n</think>\n{reply}\n")
            conversation.add_message(response)
        else:
            print("Agent: No response generated.")

if __name__ == "__main__":
    main()