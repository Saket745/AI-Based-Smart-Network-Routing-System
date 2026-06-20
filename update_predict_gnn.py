with open('src/nroute/cli/predict_cmd.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'def predict_gnn(' in line:
        # Add allow_unsafe parameter
        line = line.replace('threshold: float', 'threshold: float, allow_unsafe: bool')
    if i > 0 and 'def predict_gnn(' in lines[i-1]:
        pass # already handled

    if 'help="Congestion probability threshold for flagging.",' in line and i < 173:
        new_lines.append(line)
        new_lines.append(')\n')
        new_lines.append('@click.option(\n')
        new_lines.append('    "--allow-unsafe",\n')
        new_lines.append('    is_flag=True,\n')
        new_lines.append('    default=False,\n')
        new_lines.append('    help="Allow loading insecure model files (joblib/pickle).",\n')
        continue

    if 'store.load_model(model, name=model_type.lower(), version=version)' in line:
        line = line.replace('version=version)', 'version=version, allow_unsafe=allow_unsafe)')

    new_lines.append(line)

with open('src/nroute/cli/predict_cmd.py', 'w') as f:
    f.writelines(new_lines)
