from dma.pipeline import Pipeline
from dma.core import Message, Conversation

pipe = Pipeline()

message = Message("What's the distance between Earth and Mars?")
conversation = Conversation([message])

response = pipe.generate(conversation)

print(response.message_text[:100]+"..." )

