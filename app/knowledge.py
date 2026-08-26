# Aster & Row Support Agent - Knowledge Base Parser

import os
import re

def load_knowledge_base(kb_dir="knowledge-base"):
    """Load policy markdown files, parse frontmatter, and split by '##' headings."""
    chunks = []
    if not os.path.exists(kb_dir):
        # Fallback to absolute or search upwards if called from elsewhere
        # (e.g., when running evaluate.py from a parent directory)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        kb_dir = os.path.join(os.path.dirname(current_dir), "knowledge-base")
        if not os.path.exists(kb_dir):
            kb_dir = os.path.abspath("knowledge-base")

    for filename in os.listdir(kb_dir):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(kb_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse frontmatter
        frontmatter = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                body = parts[2]
                # Simple YAML parser for frontmatter
                for line in fm_text.strip().split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        frontmatter[k.strip()] = v.strip()

        # Parse Title
        title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        doc_title = title_match.group(1).strip() if title_match else filename.replace(".md", "")

        # Split into sections based on '##' headings
        # Regex split that keeps the heading in the output
        sections = re.split(r"^(##\s+.+)$", body, flags=re.MULTILINE)
        
        # If there's text before the first heading, capture it as "Introduction"
        intro_text = sections[0].strip()
        # Remove the main title from the introduction text
        if title_match:
            intro_text = re.sub(r"^#\s+.+$", "", intro_text, flags=re.MULTILINE).strip()
            
        if intro_text:
            chunks.append({
                "text": intro_text,
                "source": filename,
                "heading": "Introduction",
                "title": doc_title,
                "metadata": frontmatter,
                "status": frontmatter.get("status", "active"),
                "policy_authority": frontmatter.get("policy_authority", "official")
            })

        # Process each heading and its content
        for i in range(1, len(sections), 2):
            heading_line = sections[i]
            section_content = sections[i+1].strip() if i+1 < len(sections) else ""
            
            heading = re.sub(r"^##\s+", "", heading_line).strip()
            
            chunks.append({
                "text": section_content,
                "source": filename,
                "heading": heading,
                "title": doc_title,
                "metadata": frontmatter,
                "status": frontmatter.get("status", "active"),
                "policy_authority": frontmatter.get("policy_authority", "official")
            })

    return chunks

if __name__ == "__main__":
    kb = load_knowledge_base()
    print(f"Loaded {len(kb)} chunks from knowledge base.")
    if kb:
        print("Example chunk:")
        print(kb[0])
