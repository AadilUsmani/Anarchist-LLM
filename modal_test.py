# modal_test.py
import modal

app = modal.App("gpt1900-test")
image = (
    modal.Image.debian_slim()
    .apt_install("git")
    .uv_pip_install(
        "torch",
        "huggingface_hub",
        "rustbpe",
        "uv",
        "gitpython",
        "tokenizers",
        "transformers",
        "safetensors",
        "accelerate",
        "numpy",
        "tiktoken",
    )
    .run_commands(
        "git clone https://github.com/michaelhla/gpt1900.git /gpt1900",
    )
)

@app.function(
    gpu="A100",  # ← CHANGE FROM A10G
    image=image,
    timeout=600,
    volumes={"/models": modal.Volume.from_name("gpt1900-weights", create_if_missing=True)},
    env={
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        "CUDA_LAUNCH_BLOCKING": "1"
    }
)
def run_prompt(prompt: str) -> str:
    import subprocess, os, sys
    sys.path.insert(0, "/gpt1900")
    os.chdir("/gpt1900")
    os.environ["PYTHONPATH"] = "/gpt1900"
    
    if not os.path.exists("/models/gpt1900-instruct-v3-sft/model_000075.pt"):
        subprocess.run([
            "hf", "download", 
            "mhla/gpt1900-instruct-v3-sft",
            "--local-dir", "/models/gpt1900-instruct-v3-sft",
            "--exclude", "optim_*"
        ], check=True)  
    
    result = subprocess.run([
        "python", "-m", "scripts.chat_cli",
        "--model-dir", "/models/gpt1900-instruct-v3-sft",
        "--single-turn",
        "--temperature", "0.65",
        "--prompt", prompt,
    ], capture_output=True, text=True, cwd="/gpt1900",
       env={**os.environ, "PYTHONPATH": "/gpt1900"})
    
    # Debug output
    print(f"Return code: {result.returncode}")
    print(f"STDOUT length: {len(result.stdout)}")
    print(f"STDERR length: {len(result.stderr)}")
    
    if result.returncode != 0:
        print(f"Error output:\n{result.stderr}")
        return f"ERROR: {result.stderr}"

    output = result.stdout or result.stderr

    # chat_cli prints a banner and labels turns with "A:" (assistant) and "Q:" (user).
    # In --single-turn mode the last "A:" block is the model's actual response.
    # Extract everything after the final "A:" marker and strip surrounding whitespace.
    parts = output.split("A:")
    if len(parts) > 1:
        response = parts[-1].strip()
    else:
        # Fallback: drop known banner lines and return whatever is left.
        skip = {
            "Autodetected device type: cuda",
            "NanoChat Interactive Mode",
            "Type 'quit' or 'exit' to end the conversation",
            "Type 'clear' to start a new conversation",
        }
        lines = [
            l for l in output.splitlines()
            if l.strip() and l.strip("-") and l.strip() not in skip
        ]
        response = "\n".join(lines).strip()

    if not response:
        return "No output captured from inference"

    return response

@app.local_entrypoint()
def main():
    prompt = """You are a consulting scholar retained by the Royal Statistical Society. 
You have read widely across all published works of science, history, 
commerce, and natural philosophy available as of 1899.

A clerk at the General Register Office must arrange 10,000 parish 
ledgers by surname across 50 counties. Each ledger contains hundreds 
of names in no particular order. Describe the most efficient procedure 
for arranging them so any name can be found quickly."""

    print("Running inference on Modal A10G...")
    response = run_prompt.remote(prompt)
    print("\n--- GPT-1900 RESPONSE ---")
    print(response)