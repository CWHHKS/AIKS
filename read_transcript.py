import os
import json

transcript_path = r"C:\Users\chang\.gemini\antigravity\brain\061de39c-9792-4678-86e7-324dde520280\.system_generated\logs\transcript.jsonl"

print("Checking transcript file existence...")
if os.path.exists(transcript_path):
    print("Found transcript. Reading first few user inputs...")
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("type") == "USER_INPUT":
                    content = data.get("content", "")
                    print(f"\n[Step {data.get('step_index')}] User Input Summary:")
                    print("-" * 50)
                    print(content[:800])
                    print("-" * 50)
            except Exception as e:
                pass
else:
    print("Transcript file not found at:", transcript_path)
