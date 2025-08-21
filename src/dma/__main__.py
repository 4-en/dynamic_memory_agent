# main entry point
# by default, this will launch a basic command-line interface to interact with
# the memory agent via multi turn conversations.

from dma.core import Pipeline
import logging


def main():
    
    logging.basicConfig(level=logging.INFO)
    
    print("Dynamic Memory Agent CLI")
    print("Type 'exit' to quit.")
    
    pipeline = Pipeline()
    
    input_text = None
    while input_text != "exit":
        input_text = input("You: ")
        if input_text.strip().lower() == "exit":
            break
        
        response = pipeline(input_text)
        
        if response:
            print(f"Agent: {response}")
        else:
            print("Agent: No response generated.")

if __name__ == "__main__":
    main()