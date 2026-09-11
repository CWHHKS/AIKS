import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r"C:\Users\chang\.gemini\antigravity\brain\061de39c-9792-4678-86e7-324dde520280\.system_generated\logs\transcript_full.jsonl"

print("Reading the very beginning of the transcript...")
if os.path.exists(transcript_path):
    with open(transcript_path, "r", encoding="utf-8") as f:
        count = 0
        for line in f:
            try:
                data = json.loads(line)
                if data.get("type") == "USER_INPUT":
                    content = data.get("content", "")
                    step_idx = data.get("step_index")
                    print(f"\n[Step {step_idx}] User Input:")
                    print(content)
                    count += 1
                    if count >= 10:
                        break
            except Exception as e:
                pass
else:
    print("Transcript not found.")
