import os

cli_dir = r"c:\Users\mssak\OneDrive\Desktop\Network Route Optimizer\AI-Based-Smart-Network-Routing-System\src\nroute\cli"

for root, _dirs, files in os.walk(cli_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, encoding="utf-8") as f:
                content = f.read()

            # Replace unicode symbols
            new_content = content.replace("✓", "+").replace("✗", "x")

            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Fixed unicode symbols in {file}")
