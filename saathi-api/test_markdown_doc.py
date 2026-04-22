import asyncio
import os
import sys

# Ensure we can import from saathi-api
sys.path.append(os.path.join(os.getcwd(), "saathi-api"))

def test_parser_v125():
    print("TESTING SAATHI OUTLINE PARSER (v125.0)...")
    from google_workspace import _parse_markdown_to_blocks
    
    test_content = """# First Topic
## Second Level
### Third Level
# Next Topic
- Point A
- Point B
"""
    
    blocks = _parse_markdown_to_blocks(test_content)
    
    for i, b in enumerate(blocks):
        print(f"Block {i}: Type={b.get('paragraphStyle')}, Text='{b['text']}', Bullet={b.get('bulletPreset')}")
    
    # Assertions
    assert blocks[0]['text'] == "1. First Topic"
    assert blocks[1]['text'] == "1.1 Second Level"
    assert blocks[2]['text'] == "1.1.1 Third Level"
    assert blocks[3]['text'] == "2. Next Topic" # Sequential check
    
    assert blocks[4]['bulletPreset'] == "NUMBERED_DECIMAL_ALPHA_ROMAN"
    
    print("\n✅ PARSER V125.0 VERIFIED: Outline numbering and numbered bullet presets are active.")

if __name__ == "__main__":
    test_parser_v125()
