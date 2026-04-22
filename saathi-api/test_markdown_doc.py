import asyncio
import os
import sys

# Ensure we can import from saathi-api
sys.path.append(os.path.join(os.getcwd(), "saathi-api"))

def test_parser_v124():
    print("TESTING SAATHI MARKDOWN PARSER (v124.0)...")
    from google_workspace import _parse_markdown_to_blocks
    
    test_content = """# Title 1
## Title 2
### Title 3
#### Title 4

- Bullet 1
* Bullet 2

This is a **Bold** and *Italic* text with ~~Strikethrough~~.
Even mixed **_Bold-Italic_** should be clean.
"""
    
    blocks = _parse_markdown_to_blocks(test_content)
    
    for i, b in enumerate(blocks):
        print(f"Block {i}: Type={b.get('paragraphStyle')}, Text='{b['text']}'")
    
    # Assertions
    assert blocks[0]['paragraphStyle'] == "HEADING_1"
    assert blocks[3]['paragraphStyle'] == "HEADING_4"
    assert blocks[3]['text'] == "Title 4"
    
    assert blocks[4]['bulletPreset'] == "BULLET_DISC_CIRCLE_SQUARE"
    assert blocks[5]['bulletPreset'] == "BULLET_DISC_CIRCLE_SQUARE"
    
    # Check cleaning
    assert "Bold" in blocks[6]['text']
    assert "**" not in blocks[6]['text']
    assert "*" not in blocks[6]['text']
    assert "~~" not in blocks[6]['text']
    assert "_" not in blocks[7]['text']
    
    print("\n✅ PARSER V124.0 VERIFIED: All markers stripped, structural fidelity maintained.")

if __name__ == "__main__":
    test_parser_v124()
