import json
import sys
import openai
import jsonlines

from .utils import (extract_answer,
                   read_jsonl,
                   import_llm_and_tokenizer,
                   TaskConfig,
                   ModelConfig,
                   MODEL_MAPPING,
                   TASK_MAPPING,
                   )

class ChainofThoughtRun:
    def __init__(self, model_id, task, llm_type, test_data, access_token=None, top_p=0.01, temperature=0.001, max_tokens=None):
        self.model_id = model_id
        self.model_config : ModelConfig = MODEL_MAPPING.get(model_id, None)
        if self.model_config is None:
            raise ValueError(f"Model with id {model_id} is not supported.")
        self.task = task
        self.task_config : TaskConfig = TASK_MAPPING.get(task, None)
        if self.task_config is None:
            raise ValueError(f"Task with id {task} is not supported.")
        self.llm_type = llm_type
        if self.llm_type not in ["llama", "gpt"]:
            raise ValueError(f"llm_type {llm_type} is not supported.")
        elif self.llm_type == "llama":
            self.llm_config = self.task_config.llama_config
        elif self.llm_type == "gpt":
            self.llm_config = self.task_config.gpt_config
        
        self.test_data = test_data
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        
        if self.llm_type == "llama":
            self.llm, self.tokenizer = import_llm_and_tokenizer(self.model_config, access_token)
            
    def process_prompt(self, question, command=None):
        if self.model_config.is_llama:
            prompt = self.llm_config.prompt + "\n\nQ: {}\n".format(question)
            prompt = self.model_config.prompt_format.format(prompt=prompt, command=self.llm_config.command)
        elif self.model_config.is_gpt:
            prompt = self.model_config.prompt_format.format(prompt=self.llm_config.prompt, question=question)
        return prompt
        
    def get_answer_from_llm(self, question, model=None, tokenizer=None, model_config: ModelConfig = None):
        if self.model_config.is_llama and model is not None and tokenizer is not None:
            llama_prompt = self.process_prompt(question)
            input_ids = tokenizer(llama_prompt, return_tensors="pt", truncation=True).input_ids.cuda()
            outputs = model.generate(input_ids=input_ids,
                             max_new_tokens=self.max_tokens,
                             do_sample=True,
                             top_p=0.01,
                             temperature=0.001,
                             )
            tokens = tokenizer.batch_decode(outputs.detach().cpu().numpy(), skip_special_tokens=True)[0][len(llama_prompt)-1:]
    
            # if tokens.split("[/INST]")[1]:
            #     tokens = tokens.split("[/INST]")[1]
            # else:
            #     tokens=tokens
    
            return tokens
        elif self.model_config.is_gpt:
            gpt_prompt = self.process_prompt(question)
            response = openai.Completion.create(
            engine=self.model_config.id,
            prompt=gpt_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            stop=["Q:"],
        )
            return response['choices'][0]['text'].strip()
        
    def run(self):
        #result = dict()
        model_type = self.model_config.id.replace("/", "_")
        file_name = "./result/gsm8k.{}.sample_{}_{}.jsonl".format(model_type, len(self.test_data), self.task)
        writer = jsonlines.open(file_name, mode='w')
        for question, answer in self.test_data:
            result = dict()
            result['question'] = question
            result['answer'] = answer
            result[self.model_config.id] = self.get_answer_from_llm(question, model=self.llm, tokenizer=self.tokenizer, model_config=self.model_config)
            writer.write(result)
        writer.write(self.llm_config.prompt)
        writer.close()
            
    
    
            
            