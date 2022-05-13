import sys
import time
from dataclasses import dataclass

import openai
from rl.common import Colorize
from rl.lm import LM
from transformers import GPT2TokenizerFast

OPENAI_MODELS = ["code-davinci-002", "text-davinci-002", "gpt3"]


MAX_TOKENS_ACCEPTED_BY_LM = 4000


@dataclass
class GPT3(LM):
    def __post_init__(self):
        self.tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        self.start_time = time.time()
        if self.wait_time is None:
            if self.model_name == "code-davinci-002":
                self.wait_time = 4
            elif self.model_name in ["text-davinci-002", "gpt3"]:
                self.wait_time = 0
            else:
                raise ValueError(f"Unknown model {self.model_name}")
        assert self.logprobs <= 5

    def get_full_completion(
        self, prompt: str, stop: list[str], temperature: float, use_cache: bool = True
    ):
        if self.debug >= 0:
            print("<", end="")

        prompt = self.clip_prompt(prompt)

        if use_cache:
            completions = self.get_completions(
                prompt, stop=stop, temperature=temperature
            )
            if completions:
                completion, *_ = completions
                # print("Completion:")
                # print(value)
                if self.debug >= 0:
                    print(">", end="")
                return completion
            elif self.require_cache:
                print(prompt)
                Colorize.print_warning("No completions found in cache for this prompt.")
                breakpoint()
                exit()

        self.print("Prompt:")
        self.print(prompt)
        if self.debug >= 5:
            breakpoint()
        wait_time = self.wait_time
        while True:
            # print("Prompt:", prompt.split("\n")[-1])
            wait_time = min(wait_time, 60)
            sys.stdout.flush()
            try:
                time.sleep(wait_time)
                tick = time.time()
                choice, *_ = openai.Completion.create(
                    engine="text-davinci-002"
                    if self.model_name == "gpt3"
                    else self.model_name,
                    max_tokens=self.max_tokens_in_completion,
                    prompt=prompt,
                    logprobs=self.logprobs,
                    temperature=0.1,
                    stop=stop,
                ).choices

                if self.logger.run_id is not None:
                    self.logger.log(
                        **{
                            "hours": (time.time() - self.start_time) / 3600,
                            "run ID": self.logger.run_id,
                            "seconds per query": time.time() - tick,
                        },
                    )
                # if not choice.text:
                #     print(prompt)
                #     Colorize.print_warning("Empty completion!")
                #     breakpoint()
            except openai.error.RateLimitError as e:
                print("Rate limit error:")
                print(e)
                sys.stdout.flush()
                wait_time *= 2
                continue
            except openai.error.InvalidRequestError as e:
                print("Invalid request error:")
                print(e)
                breakpoint()
                continue

            top_logprobs = [l.to_dict() for l in choice.logprobs.top_logprobs]
            completion = choice.text.lstrip()
            response = self.post_completion(
                completion=completion,
                prompt=prompt,
                stop=stop,
                temperature=temperature,
                top_logprobs=top_logprobs,
            )["insert_completions_one"]["completion"]
            if response != completion:
                breakpoint()
            if self.debug >= 0:
                print(">", end="")
            self.print("Completion:", completion.split("\n")[0])
            if self.debug >= 6:
                breakpoint()
            return dict(
                prompt=prompt,
                completion=completion,
                top_logprobs=top_logprobs,
            )

    def max_prompt_tokens(self) -> int:
        return MAX_TOKENS_ACCEPTED_BY_LM - self.max_tokens_in_completion - 100

    def print(self, *args, **kwargs):
        if self.debug >= 5:
            print(*args, **kwargs)
