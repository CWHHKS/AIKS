import json

with open("data/local_backup/GV-FIN-20260804-01.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Batch ID:", data.get("batch_id"))
candidates = data.get("candidates", [])
print(f"Number of candidates: {len(candidates)}")

if candidates:
    first = candidates[0]
    print("\nKeys in first candidate:")
    for k, v in first.items():
        print(f"  {k}: {str(v)[:100]}")
