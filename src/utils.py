import json
import numpy as np
import re
from copy import deepcopy
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
from huggingface_hub import login
import openai
import dataclasses
from .prompts import (NO_COHERENCE_PROMPT,
                     GPT_PROMPT_NO_COHERENCE,)

def read_jsonl(path: str):
    with open(path, "r", encoding='utf-8') as fh:
        return [json.loads(line) for line in fh.readlines() if line]
    
def extract_answer(completion):
    ANS_RE = re.compile(r"#### (\-?[0-9\.\,]+)")
    match = ANS_RE.search(completion)
    if match:
        match_str = match.group(1).strip()
        match_str = match_str.replace(",", "")
        return match_str
    else:
        assert False
        
def import_model_and_tokenizer(model_config: dict, access_token: str = None):
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    
    if access_token is None:
        raise ValueError("Access token must be provided for protected models.")
    elif access_token is not None:
        login(token=access_token)
        language_model = AutoModelForCausalLM.from_pretrained(model_config["id"],
                                                              quantization_config=bnb_config,
                                                              use_cache=True,
                                                              device_map='auto',
                                                              token=access_token)
    tokenizer = AutoTokenizer.from_pretrained(model_config["id"])
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return language_model, tokenizer


def get_answer_from_gpt(prompt, question, gpt_config,
                        max_tokens,
                        temperature,
                        ):
    response = openai.Completion.create(
        engine=gpt_config["id"],
        prompt=prompt + "\n\nQ: {}\nA:".format(question),
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        stop=["Q:"],
    )
    return response['choices'][0]['text'].strip()

def get_answer_from_llama(prompt, question, model, tokenizer, max_tokens=500):
    prompt = prompt + "\n\nQ: {}\n".format(question)
    command = "A:"
    llama_prompt = LLAMA_PROMPT_FORMAT.format(prompt=prompt, command=command)
    input_ids = tokenizer(llama_prompt, return_tensors="pt", truncation=True).input_ids.cuda()
    outputs = model.generate(input_ids=input_ids,
                             max_new_tokens=max_tokens,
                             do_sample=True,
                             top_p=0.01,
                             temperature=0.001,
                             )
    tokens = tokenizer.batch_decode(outputs.detach().cpu().numpy(), skip_special_tokens=True)[0][len(prompt):]
    
    if tokens.split("[/INST]")[1]:
        tokens = tokens.split("[/INST]")[1]
    else:
        tokens=tokens
    
    return tokens


@dataclasses.dataclass
class ModelConfig:
    id: str
    prompt_format: str
    is_llama: bool
    is_gpt: bool
    max_tokens: int

LLAMA_PROMPT_FORMAT = (
    """<s>[INST] <<SYS>>{prompt}\n<</SYS>>\n{command} [/INST]"""
)
GPT_PROMPT_FORMAT = (
    """{prompt}\n\nQ: {question}\nA:"""
)

MODEL_MAPPING = {
    "llama_2_7b": ModelConfig(
        id="meta-llama/Llama-2-7b-chat-hf",
        prompt_format=LLAMA_PROMPT_FORMAT,
        is_llama=True,
        is_gpt=False,
        max_tokens=500,
    ),
    "llama_2_13b": ModelConfig(
        id="meta-llama/Llama-2-13b-chat-hf",
        prompt_format=LLAMA_PROMPT_FORMAT,
        is_llama=True,
        is_gpt=False,
        max_tokens=500,
    ),
    "llama_2_70b": ModelConfig(
        id="meta-llama/Llama-2-70b-chat-hf",
        prompt_format=LLAMA_PROMPT_FORMAT,
        is_llama=True,
        is_gpt=False,
        max_tokens=500,
    ),
    "gpt": ModelConfig(
        id="gpt-3.5-turbo-instruct",
        prompt_format=GPT_PROMPT_FORMAT,
        is_llama=False,
        is_gpt=True,
        max_tokens=400,
    ),
}

def import_llm_and_tokenizer(model: ModelConfig, access_token: str = None):
    if model.is_llama and access_token is not None:
        bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        )
        language_model = AutoModelForCausalLM.from_pretrained(model.id,
                                                              quantization_config=bnb_config,
                                                              use_cache=True,
                                                              device_map='auto',
                                                              token=access_token)
        tokenizer = AutoTokenizer.from_pretrained(model.id)
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"
        return language_model, tokenizer
    
    if model.is_llama and access_token is None:
        raise ValueError("Access token must be provided for protected models.")
    if model.is_gpt:
        print(f"The model is a {model.id} model.")
        
    # def get_answer_from_llm(prompt, question, model=None, tokenizer=None, model_config: ModelConfig = None):
    #     if model_config.is_llama and model is not None and tokenizer is not None:
    #         prompt = prompt + "\n\nQ: {}\n".format(question)
    #         command = "A:"
    #         llama_prompt = model_config.prompt_format.format(prompt=prompt, command=command)
    #         input_ids = tokenizer(llama_prompt, return_tensors="pt", truncation=True).input_ids.cuda()
            
@dataclasses.dataclass
class GptConfig:
    id: str
    prompt: str

@dataclasses.dataclass
class LlamaConfig:
    id: str
    prompt: str
    command: str

@dataclasses.dataclass
class TaskConfig:
    id: str
    gpt_config: GptConfig
    llama_config: LlamaConfig
    

TASK_MAPPING = {
    "NO_COHERENCE": TaskConfig(
        id="NO_COHERENCE",
        gpt_config=GptConfig(
            id="gpt-3.5-turbo-instruct",
            prompt=GPT_PROMPT_NO_COHERENCE,
        ),
        llama_config=LlamaConfig(
            id="meta-llama/Llama-2-70b-chat-hf",
            prompt=NO_COHERENCE_PROMPT,
            command=" A:",
        ),
        
    ),
}
        
