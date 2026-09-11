import google.generativeai as genai
from google.generativeai.types import content_types

# Let's inspect content_types Tool helper
try:
    print("content_types.Tool fields:")
    # We can inspect the protobuf class or the Tool type
    import google.ai.generativelanguage_v1beta as glm
    print(dir(glm.Tool))
    print(glm.Tool()._pb)
except Exception as e:
    print(e)
