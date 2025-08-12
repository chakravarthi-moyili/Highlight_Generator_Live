import openai
import json
import yaml
from pathlib import Path
import os
from src.core.config import OPENAI_API_KEY
# from src.gpt.prompt_templates.yaml import prompts

openai.api_key = OPENAI_API_KEY
client = openai

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

def load_yaml_file(file_path: str) -> dict:
    """Reads and returns the contents of a YAML file as dictionary"""
    return yaml.safe_load(open_file(file_path))

def load_yaml_prompt(file_path):
    """Load YAML prompt file"""
    _here = Path(__file__).parent
    _absolute_path = (_here / '..' / file_path).resolve()
    json_template = load_yaml_file(str(_absolute_path))
    return json_template['chat_prompt'], json_template['system_prompt']

def is_highlight(transcript):
    chat_prompt, system_prompt = load_yaml_prompt('gpt/prompt_templates.yaml')
    assert "<<TRANSCRIPTION>>" in chat_prompt, "Placeholder not found in chat_prompt"
    chat_prompt = chat_prompt.replace("<<TRANSCRIPTION>>", f"{transcript.strip()}")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chat_prompt}
            ],
            temperature=0.3
        )
        content = response.choices[0].message.content
        print(f"OpenAI response: {content}")
        parsed = json.loads(content)
        return parsed.get("highlight", False), parsed.get("title", ""), parsed.get("description", "")
    except Exception as e:
        print(f"OpenAI error: {e}")
        return False, ""



















# import openai
# import json
# from core.config import OPENAI_API_KEY
# from src.gpt.prompt_templates.yaml as prompts

# openai.api_key = OPENAI_API_KEY
# client = openai

# def is_highlight(transcript: str):
#     prompt = prompts(transcript)
#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.3
#         )
#         content = response.choices[0].message.content
#         print(f"OpenAI response: {content}")
#         parsed = json.loads(content)
#         return parsed.get("highlight", False), parsed.get("title", "")
#     except Exception as e:
#         print(f"OpenAI error: {e}")
#         return False, ""
