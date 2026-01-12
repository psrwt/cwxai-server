from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

def serialize_messages(messages):
    return [{
        'type': 'human' if isinstance(msg, HumanMessage) else 'ai',
        'content': msg.content,
        'timestamp': datetime.now().isoformat()
    } for msg in messages]

def deserialize_messages(messages_dict):
    messages = []
    for msg in messages_dict:
        if msg['type'] == 'human':
            messages.append(HumanMessage(content=msg['content']))
        elif msg['type'] == 'ai':
            messages.append(AIMessage(content=msg['content']))
    return messages