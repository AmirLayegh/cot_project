from src.utils import (extract_answer,
                     read_jsonl,
)
import jsonlines
import openai
import json
import numpy as np
from src.cot import ChainofThoughtRun

NUM_TEST = 400
SEED=1357
DATASET_PATH = "./dataset/gsm8k/test.jsonl"

model_id = "llama_2_7b"
task = "NO_COHERENCE"
llm_type = "llama"

test_indices = "./dataset/gsm8k/test_indices.jsonl"
access_token = "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"
top_p=0.01
temperature=0.001
max_tokens=400

test_data = read_jsonl(DATASET_PATH)
qa_pairs = [(instance['question'], instance['answer']) for instance in test_data]

if test_indices is not None:
    with open(test_indices, "r") as f:
        test_indices = json.load(f)
    #qa_pairs = read_jsonl(DATASET_PATH)
    qa_pairs_test = [qa_pairs[idx] for idx in test_indices]
    #qa_pairs_test = qa_pairs_test[:3]
    print(f" Testing on {len(qa_pairs_test)} QA pairs")
    print(f"Total number of QA pairs: {len(qa_pairs)}")
else:
    file_name = "./indices/test_indices_{}.jsonl".format(NUM_TEST)
    writer = jsonlines.open(file_name, mode='w')
    np.random.seed(SEED)
    rand_indices= np.random.choice(len(qa_pairs), NUM_TEST, replace=False)
    writer.write(rand_indices.tolist())
    writer.close()
    qa_pairs_test = [qa_pairs[idx] for idx in rand_indices]
    print(f" Testing on {len(qa_pairs_test)} QA pairs")

chain_of_thought = ChainofThoughtRun(
    test_data = qa_pairs_test,
    model_id = model_id,
    task = task,
    llm_type = llm_type,
    access_token = access_token,
    top_p = top_p,
    temperature = temperature,
    max_tokens = max_tokens,
    )
chain_of_thought.run()