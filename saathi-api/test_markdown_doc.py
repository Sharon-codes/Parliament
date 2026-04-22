import asyncio
import os
import sys

# Ensure we can import from saathi-api
sys.path.append(os.path.join(os.getcwd(), "saathi-api"))

def test_absolute_purifier_v126():
    print("TESTING SAATHI ABSOLUTE PURIFIER (v126.0)...")
    from google_workspace import _parse_markdown_to_blocks
    
    test_content = """# Omlette
================
**Introduction**
----------------

An omelette is a dish...

**Ingredients**
=======

* 2 large eggs
* 1 tablespoon butter
"""
    
    blocks = _parse_markdown_to_blocks(test_content)
    
    for i, b in enumerate(blocks):
        print(f"Block {i}: Type={b.get('paragraphStyle')}, Text='{b['text']}'")
    
    # Assertions
    # 1. No ===== lines should exist as separate blocks
    texts = [b['text'] for b in blocks]
    for t in texts:
        assert not t.startswith("==")
        assert not t.startswith("--")
        assert "**" not in t
        assert "*" not in t
        
    assert blocks[0]['text'] == "1. Omlette"
    assert blocks[1]['text'] == "Introduction" # Marker stripped
    assert blocks[2]['text'] == "An omelette is a dish..."
    assert blocks[3]['text'] == "Ingredients" # Marker stripped
    assert blocks[4]['text'] == "2 large eggs" # Bullet marker stripped
    
    print("\n✅ PURIFIER V126.0 VERIFIED: All Setext lines discarded, all makers and technical noise annihilated.")

if __name__ == "__main__":
    test_absolute_purifier_v126()
