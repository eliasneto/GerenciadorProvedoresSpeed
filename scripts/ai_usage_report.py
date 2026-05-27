from pathlib import Path
import re
from collections import Counter

LOG_PATH = Path("docs/AI_USAGE_LOG.md")

def main():
    if not LOG_PATH.exists():
        print("Arquivo docs/AI_USAGE_LOG.md não encontrado.")
        return

    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    rows = [line for line in lines if line.startswith("|") and not line.startswith("|---")]

    # Ignora cabeçalho
    data_rows = []
    for row in rows:
        if "Data" in row and "Agente" in row:
            continue
        cols = [c.strip() for c in row.strip("|").split("|")]
        if len(cols) >= 8 and not cols[0].startswith("AAAA"):
            data_rows.append(cols)

    agent_counter = Counter()
    level_counter = Counter()

    for cols in data_rows:
        agent = cols[1]
        level = cols[3]
        agent_counter[agent] += 1
        level_counter[level] += 1

    print("Uso estimado por agente:")
    for agent, count in agent_counter.most_common():
        print(f"- {agent}: {count}")

    print("\nUso estimado por nível:")
    for level, count in level_counter.most_common():
        print(f"- {level}: {count}")

if __name__ == "__main__":
    main()
