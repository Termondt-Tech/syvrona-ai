import logging
from openai import OpenAI

from app.models import create_message
from app.handler.conversation_handler import get_conversation_messages

logger = logging.getLogger(__name__)


class OpenAIStreamer:
    def __init__(self):
        self.client = OpenAI()

    def chat(self, message, user_id, conversation_id, model):
        logger.info(f"Current User ID: {user_id}")
        logger.info(f"Current Conversation ID: {conversation_id}")
        logger.info(f"User message: {message}")

        messages = [{"role": "system", "content": "You are an intelligent assistant."}]

        conversation_history = get_conversation_messages(conversation_id)

        for msg in conversation_history:
            messages.append({"role": msg.role, "content": msg.content})

        logger.info(f"Messages: {messages}")

        if message:
            # create new user message in the database
            user_message = create_message(conversation_id, "user", message)
            logger.info(f"User message created with ID: {user_message.id}")

            collected_chunks = []
            messages.append({"role": "user", "content": message})
            stream = self.client.chat.completions.create(
                model=model, messages=messages, stream=True
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                if chunk.choices[0].delta.content is not None:
                    collected_chunks.append(chunk.choices[0].delta.content)
                    yield (chunk.choices[0].delta.content)

        collected_string = "".join(collected_chunks)
        logger.info(f"Current User ID: {user_id}")

        # create new assistant message in the database
        assistant_message = create_message(
            conversation_id, "assistant", collected_string
        )
        logger.info(f"Assistant message created with ID: {assistant_message.id}")


if __name__ == "__main__":
    openai_streamer = OpenAIStreamer()
    while True:
        message = input("User : ")
        if message:
            openai_streamer.chat(message)
