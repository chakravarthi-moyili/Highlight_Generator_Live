from openai import OpenAI
import json
import yaml
from pathlib import Path
import os
from src.core.config import OPENAI_API_KEY
from src.core.logging_config import get_logger
# from src.gpt.prompt_templates.yaml import prompts

logger = get_logger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

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
        logger.info("OpenAI response: %s", content)
        parsed = json.loads(content)
        return parsed.get("highlight", False), parsed.get("title", ""), parsed.get("description", "")
    except json.JSONDecodeError as e:
        # The model occasionally wraps JSON in prose; log what came back so the
        # cause is visible instead of silently reporting "no highlight".
        logger.error("OpenAI returned non-JSON content (%s): %r", e, content)
        return False, "", ""
    except Exception as e:
        logger.error("OpenAI error: %s", e)
        return False, "", ""



















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
